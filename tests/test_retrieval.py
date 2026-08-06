"""Offline synthetic tests for persistent hybrid retrieval."""

from pathlib import Path

import pytest

from china_policy_rag.ingestion.pipeline import IngestionPipeline
from china_policy_rag.retrieval.embeddings import DeterministicHashEmbeddingProvider
from china_policy_rag.retrieval.indexes import build_indexes
from china_policy_rag.retrieval.models import MetadataFilters, RetrievalMode, RetrievalQuery
from china_policy_rag.retrieval.service import RetrievalService


def build_synthetic_service(tmp_path: Path) -> RetrievalService:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "source.txt").write_text(
        "Synthetic manufacturing investment measure.\n\n合成政策措施。", encoding="utf-8"
    )
    manifest = raw / "manifest.yaml"
    manifest.write_text(
        "sources:\n  - file_path: source.txt\n    title: Synthetic source\n"
        "    issuer: Test issuer\n    publication_date: 2025-01-01\n"
        "    jurisdiction: Test\n    language: en\n    document_type: policy\n"
        "    sector_tags: [manufacturing]\n",
        encoding="utf-8",
    )
    IngestionPipeline().run(raw, manifest, tmp_path / "processed")
    provider = DeterministicHashEmbeddingProvider()
    index_dir = tmp_path / "index"
    build_indexes(tmp_path / "processed" / "chunks.jsonl", index_dir, provider, False)
    return RetrievalService(str(index_dir), provider)


def test_hybrid_retrieval_preserves_exact_evidence_and_filters(tmp_path: Path) -> None:
    service = build_synthetic_service(tmp_path)
    bundle = service.search(RetrievalQuery(text="manufacturing", mode=RetrievalMode.HYBRID))
    assert (
        bundle.evidence[0].text == "Synthetic manufacturing investment measure.\n\n合成政策措施。"
    )
    assert bundle.evidence[0].scores.lexical_rank == 1
    filtered = service.search(
        RetrievalQuery(text="manufacturing", filters=MetadataFilters(languages=["zh"]))
    )
    assert filtered.evidence == []


def test_query_validation_and_stale_index_detection(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="candidate_k"):
        RetrievalQuery(text="x", top_k=2, candidate_k=1)
    service = build_synthetic_service(tmp_path)
    chunks_path = tmp_path / "processed" / "chunks.jsonl"
    chunks_path.write_bytes(chunks_path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="stale"):
        RetrievalService(str(tmp_path / "index"), service.provider)
