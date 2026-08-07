"""Export human-reviewable retrieval candidates from approved query seeds."""

import csv
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from .retrieval.models import RetrievalMode, RetrievalQuery
from .retrieval.service import RetrievalService

_FIELDNAMES = [
    "query_id",
    "query_text",
    "query_language",
    "query_type",
    "expected_files",
    "chunk_id",
    "document_id",
    "title",
    "issuer",
    "jurisdiction",
    "language",
    "local_file_path",
    "source_url",
    "page_reference",
    "section_reference",
    "lexical_rank",
    "semantic_rank",
    "hybrid_rank",
    "chunk_text",
    "human_label",
    "reviewer_note",
]


def export_candidates(
    service: RetrievalService, query_seeds: Path, output: Path, top_k: int
) -> int:
    """Merge top results from every retrieval mode into a BOM CSV for human review."""
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    data = _load_seeds(query_seeds)
    rows: list[dict[str, str]] = []
    for query in data["queries"]:
        candidates: dict[str, dict[str, str]] = {}
        for mode in RetrievalMode:
            evidence = service.search(
                RetrievalQuery(text=query["text"], mode=mode, top_k=top_k, candidate_k=top_k)
            ).evidence
            for rank, item in enumerate(evidence, 1):
                chunk_id = str(item.chunk_id)
                row = candidates.setdefault(
                    chunk_id,
                    {
                        "query_id": query["query_id"],
                        "query_text": query["text"],
                        "query_language": query["language"],
                        "query_type": query["query_type"],
                        "expected_files": "|".join(query["expected_files"]),
                        "chunk_id": chunk_id,
                        "document_id": str(item.document_id),
                        "title": item.title,
                        "issuer": item.issuer,
                        "jurisdiction": item.jurisdiction,
                        "language": str(item.language),
                        "local_file_path": str(item.local_file_path or ""),
                        "source_url": item.source_url or "",
                        "page_reference": item.page_reference or "",
                        "section_reference": item.section_reference or "",
                        "lexical_rank": "",
                        "semantic_rank": "",
                        "hybrid_rank": "",
                        "chunk_text": item.text,
                        "human_label": "",
                        "reviewer_note": "",
                    },
                )
                row[f"{mode.value}_rank"] = str(rank)
        rows.extend(_sorted_candidates(candidates.values()))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _load_seeds(path: Path) -> dict[str, list[dict[str, Any]]]:
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("queries"), list):
        raise ValueError("Query seeds must be a YAML mapping with a queries list")
    queries = data["queries"]
    required = {"query_id", "text", "language", "query_type", "expected_files"}
    if not all(isinstance(row, dict) and required.issubset(row) for row in queries):
        raise ValueError("Each query seed must provide identifiers, text, type, and expected files")
    return {"queries": queries}


def _sorted_candidates(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    def rank(row: dict[str, str]) -> tuple[int, str]:
        values = [
            int(row[name]) for name in ("lexical_rank", "semantic_rank", "hybrid_rank") if row[name]
        ]
        return (min(values), row["chunk_id"])

    return sorted(rows, key=rank)
