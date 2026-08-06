"""Tests for the argparse ingestion entry point."""

from pathlib import Path

import pytest
from pytest import CaptureFixture

from china_policy_rag.cli import main


def test_cli_help_and_successful_run(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["ingest", "--help"])
    assert exit_info.value.code == 0
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "sample.txt").write_text("Synthetic test text.", encoding="utf-8")
    manifest = raw / "manifest.yaml"
    manifest.write_text(
        "sources:\n  - file_path: sample.txt\n    title: Synthetic\n    issuer: Test\n"
        "    publication_date: 2025-01-01\n    jurisdiction: Test\n    language: en\n"
        "    document_type: policy\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "ingest",
                "--input-dir",
                str(raw),
                "--manifest",
                str(manifest),
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )
        == 0
    )
    assert "Processed 1 document" in capsys.readouterr().out


def test_cli_returns_nonzero_for_manifest_failure(tmp_path: Path) -> None:
    assert (
        main(
            [
                "ingest",
                "--input-dir",
                str(tmp_path),
                "--manifest",
                str(tmp_path / "missing.yaml"),
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )
        == 1
    )


def test_cli_refuses_then_allows_overwrite(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "sample.txt").write_text("Synthetic test text.", encoding="utf-8")
    manifest = raw / "manifest.yaml"
    manifest.write_text(
        "sources:\n  - file_path: sample.txt\n    title: Synthetic\n    issuer: Test\n"
        "    publication_date: 2025-01-01\n    jurisdiction: Test\n    language: en\n"
        "    document_type: policy\n",
        encoding="utf-8",
    )
    arguments = [
        "ingest",
        "--input-dir",
        str(raw),
        "--manifest",
        str(manifest),
        "--output-dir",
        str(tmp_path / "out"),
    ]

    assert main(arguments) == 0
    assert main(arguments) == 1
    assert main([*arguments, "--overwrite"]) == 0
