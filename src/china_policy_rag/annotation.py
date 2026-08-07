"""Export human-reviewable retrieval candidates from approved query seeds."""

import csv
import json
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

_TOPIC_FIELDNAMES = [*_FIELDNAMES, "origin_query_ids"]


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


def materialize_topic_annotations(
    annotated_csv: Path,
    relevant_output: Path,
    core_output: Path,
    summary_output: Path,
    topic: str,
) -> dict[str, int]:
    """Validate topic-level labels and write deduplicated evidence artefacts."""
    if not topic.strip():
        raise ValueError("topic must not be blank")
    with annotated_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not set(_FIELDNAMES).issubset(reader.fieldnames):
            raise ValueError("Annotated CSV does not contain the required candidate columns")
        rows = list(reader)
    if not rows:
        raise ValueError("Annotated CSV must contain at least one row")

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        label = row["human_label"].strip()
        if label not in {"0", "1", "2"}:
            raise ValueError(f"Invalid human_label for chunk {row['chunk_id']}: {label!r}")
        grouped.setdefault(row["chunk_id"], []).append(row)

    unique_rows: list[dict[str, str]] = []
    for chunk_id, group in grouped.items():
        labels = {row["human_label"].strip() for row in group}
        if len(labels) != 1:
            raise ValueError(f"Topic labels conflict for chunk {chunk_id}")
        label = next(iter(labels))
        notes = {row["reviewer_note"].strip() for row in group if row["reviewer_note"].strip()}
        if label == "2" and not notes:
            raise ValueError(f"Core chunk {chunk_id} requires a reviewer_note")
        canonical = dict(group[0])
        canonical["human_label"] = label
        canonical["reviewer_note"] = " | ".join(sorted(notes))
        canonical["origin_query_ids"] = "|".join(sorted({row["query_id"] for row in group}))
        unique_rows.append(canonical)

    unique_rows.sort(key=lambda row: (-int(row["human_label"]), row["chunk_id"]))
    relevant = [row for row in unique_rows if row["human_label"] in {"1", "2"}]
    core = [row for row in unique_rows if row["human_label"] == "2"]
    _write_csv(relevant_output, relevant)
    _write_csv(core_output, core)
    summary = {
        "schema_version": "1.0",
        "annotation_type": "human_topic_level",
        "topic": topic,
        "input_rows": len(rows),
        "unique_chunks": len(unique_rows),
        "unique_chunk_labels": {
            "0": sum(row["human_label"] == "0" for row in unique_rows),
            "1": sum(row["human_label"] == "1" for row in unique_rows),
            "2": len(core),
        },
        "relevant_unique_chunks": len(relevant),
        "core_unique_chunks": len(core),
        "source_files_for_core_chunks": sorted({row["local_file_path"] for row in core}),
        "limitations": [
            "Labels are topic-level evidence judgements, not query-level relevance labels.",
            "This artefact must not be used to report Recall@k, MRR, or other retrieval metrics.",
        ],
    }
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {"relevant": len(relevant), "core": len(core)}


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_TOPIC_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


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
