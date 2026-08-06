"""Tests for supported-file discovery."""

from pathlib import Path

from china_policy_rag.ingestion.discovery import discover_source_files


def test_discovery_returns_supported_relative_files(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "a.txt").write_text("Synthetic test text.", encoding="utf-8")
    (tmp_path / "nested" / "b.md").write_text("# Synthetic", encoding="utf-8")
    (tmp_path / "ignored.docx").write_text("not supported", encoding="utf-8")

    assert discover_source_files(tmp_path) == {Path("a.txt"), Path("nested/b.md")}
