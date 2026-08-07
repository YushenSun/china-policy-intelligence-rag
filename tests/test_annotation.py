"""Tests for deterministic human-annotation candidate export."""

import csv
from pathlib import Path

from china_policy_rag.annotation import export_candidates
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
