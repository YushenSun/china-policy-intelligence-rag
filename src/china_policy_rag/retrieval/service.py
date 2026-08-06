"""Deterministic lexical, vector, RRF fusion, filtering, and evidence assembly."""

from datetime import UTC, datetime
from math import log
from pathlib import Path

import numpy as np

from .embeddings import EmbeddingProvider, _tokens
from .indexes import load_indexes
from .models import EvidenceBundle, EvidenceItem, RetrievalMode, RetrievalQuery, RetrievalScores
from .query import normalize_query


class RetrievalService:
    """Search a validated, non-stale local index without generating claims."""

    def __init__(self, index_dir: str, provider: EmbeddingProvider) -> None:
        self.chunks, self.documents, self.manifest, self.tokens, self.vectors = load_indexes(
            Path(index_dir), provider
        )
        self.provider = provider

    def search(self, query: RetrievalQuery) -> EvidenceBundle:
        normalized = normalize_query(query.text)
        allowed = [
            i for i, chunk in enumerate(self.chunks) if self._matches(chunk.document_id, query)
        ]
        lexical = self._lexical(_tokens(normalized), allowed)
        semantic = self._semantic(normalized, allowed)
        scores = self._fuse(lexical, semantic, query)
        evidence: list[EvidenceItem] = []
        seen_text: set[str] = set()
        for index, values in sorted(
            scores.items(), key=lambda item: (-item[1][2], str(self.chunks[item[0]].chunk_id))
        ):
            chunk = self.chunks[index]
            text_key = " ".join(chunk.text.split())
            if text_key in seen_text:
                continue
            seen_text.add(text_key)
            document = self.documents[str(chunk.document_id)]
            evidence.append(
                EvidenceItem(
                    rank=len(evidence) + 1,
                    chunk_id=chunk.chunk_id,
                    document_id=document.document_id,
                    title=document.title,
                    issuer=document.issuer,
                    publication_date=document.publication_date,
                    language=document.language,
                    jurisdiction=document.jurisdiction,
                    source_url=str(document.source_url) if document.source_url else None,
                    local_file_path=document.local_file_path,
                    page_reference=chunk.page_reference,
                    section_reference=chunk.section_reference,
                    text=chunk.text,
                    scores=RetrievalScores(
                        lexical_score=values[0],
                        semantic_score=values[1],
                        fused_score=values[2],
                        lexical_rank=values[3],
                        semantic_rank=values[4],
                    ),
                )
            )
            if len(evidence) == query.top_k:
                break
        return EvidenceBundle(
            original_query=query.text,
            normalized_query=normalized,
            retrieval_mode=query.mode,
            filters=query.filters,
            index_version=str(self.manifest["index_version"]),
            generated_at=datetime.now(UTC),
            evidence=evidence,
            warnings=["No matching evidence"] if not evidence else [],
            retrieval_configuration={"embedding_model": self.provider.model_id, "rrf_k": 60},
        )

    def _matches(self, document_id: object, query: RetrievalQuery) -> bool:
        document = self.documents[str(document_id)]
        filters = query.filters
        return (
            (not filters.languages or document.language in filters.languages)
            and (not filters.jurisdictions or document.jurisdiction in filters.jurisdictions)
            and (not filters.issuers or document.issuer in filters.issuers)
            and (not filters.document_types or document.document_type in filters.document_types)
            and (
                not filters.sector_tags
                or bool(set(document.sector_tags).intersection(filters.sector_tags))
            )
            and (
                filters.publication_date_from is None
                or document.publication_date >= filters.publication_date_from
            )
            and (
                filters.publication_date_to is None
                or document.publication_date <= filters.publication_date_to
            )
        )

    def _lexical(self, tokens: list[str], allowed: list[int]) -> list[tuple[int, float]]:
        count = max(len(self.tokens), 1)
        frequency = {token: sum(token in item for item in self.tokens) for token in set(tokens)}
        results = []
        for index in allowed:
            score = sum(
                (1 + log((count - frequency[token] + 0.5) / (frequency[token] + 0.5)))
                * self.tokens[index].count(token)
                for token in tokens
            )
            results.append((index, score))
        return sorted(results, key=lambda item: (-item[1], str(self.chunks[item[0]].chunk_id)))

    def _semantic(self, text: str, allowed: list[int]) -> list[tuple[int, float]]:
        vector = self.provider.embed_query(text)
        results = [(index, float(np.dot(self.vectors[index], vector))) for index in allowed]
        return sorted(results, key=lambda item: (-item[1], str(self.chunks[item[0]].chunk_id)))

    def _fuse(
        self,
        lexical: list[tuple[int, float]],
        semantic: list[tuple[int, float]],
        query: RetrievalQuery,
    ) -> dict[int, tuple[float | None, float | None, float, int | None, int | None]]:
        if query.mode is RetrievalMode.LEXICAL:
            return {
                index: (score, None, score, rank, None)
                for rank, (index, score) in enumerate(lexical[: query.candidate_k], 1)
            }
        if query.mode is RetrievalMode.SEMANTIC:
            return {
                index: (None, score, score, None, rank)
                for rank, (index, score) in enumerate(semantic[: query.candidate_k], 1)
            }
        values: dict[int, tuple[float | None, float | None, float, int | None, int | None]] = {}
        for rank, (index, score) in enumerate(lexical[: query.candidate_k], 1):
            values[index] = (score, None, query.lexical_weight / (60 + rank), rank, None)
        for rank, (index, score) in enumerate(semantic[: query.candidate_k], 1):
            previous = values.get(index, (None, None, 0.0, None, None))
            values[index] = (
                previous[0],
                score,
                previous[2] + query.semantic_weight / (60 + rank),
                previous[3],
                rank,
            )
        return values
