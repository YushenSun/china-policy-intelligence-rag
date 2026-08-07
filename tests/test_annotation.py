"""Tests for deterministic human-annotation candidate export."""

import csv
import json
from pathlib import Path

from china_policy_rag.annotation import export_candidates, materialize_topic_annotations
from tests.test_retrieval import build_synthetic_service


def test_export_candidates_writes_bom_csv(tmp_path: Path) -> None:
    seeds = tmp_path / "seeds.yaml"
    seeds.write_text(
        "queries:\n"
        "  - query_id: Q1\n"
        "    text: synthetic local text\n"
        "    language: en\n"
        "    query_type: direct\n"
        "    expected_files: [sample.txt]\n",
        encoding="utf-8",
    )
    output = tmp_path / "candidates.csv"

    assert export_candidates(build_synthetic_service(tmp_path), seeds, output, 1) == 1
    assert output.read_bytes().startswith(b"\xef\xbb\xbf")
    with output.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["query_id"] == "Q1"
    assert rows[0]["human_label"] == ""
    assert rows[0]["lexical_rank"] == "1"


def test_materialize_topic_annotations_deduplicates_and_validates(tmp_path: Path) -> None:
    source = tmp_path / "annotated.csv"
    source.write_text(
        "chunk_id,human_label,reviewer_note,query_id\n"
        "chunk-a,2,Core evidence,Q1\n"
        "chunk-a,2,Core evidence,Q2\n"
        "chunk-b,1,Supporting context,Q1\n"
        "chunk-c,0,,Q1\n",
        encoding="utf-8-sig",
    )
    # Supply the remaining exported-candidate columns with blank values.
    with source.open(encoding="utf-8-sig", newline="") as handle:
        short_rows = list(csv.DictReader(handle))
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["chunk_id", *[name for name in _CANDIDATE_FIELDS]]
        )
        writer.writeheader()
        for row in short_rows:
            writer.writerow({"chunk_id": row["chunk_id"], **row})
    relevant = tmp_path / "relevant.csv"
    core = tmp_path / "core.csv"
    summary = tmp_path / "summary.json"
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "sources:\n  - file_path: ''\n    publication_date: 2025-01-01\n",
        encoding="utf-8",
    )

    counts = materialize_topic_annotations(
        source, relevant, core, summary, "Focused policy topic", manifest
    )

    assert counts == {"relevant": 2, "core": 1}
    assert len(list(csv.DictReader(relevant.open(encoding="utf-8-sig", newline="")))) == 2
    assert json.loads(summary.read_text(encoding="utf-8"))["unique_chunks"] == 3


_CANDIDATE_FIELDS = [
    "query_id",
    "query_text",
    "query_language",
    "query_type",
    "expected_files",
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
