"""End-to-end tests for deterministic local ingestion and JSONL artifacts."""

import json
from pathlib import Path

import pytest

from china_policy_rag.ingestion.base import (
    ChunkingConfig,
    ManifestValidationError,
    OutputExistsError,
)
from china_policy_rag.ingestion.pipeline import IngestionPipeline
from china_policy_rag.models import PolicyDocument, SourceChunk


def make_manifest(raw: Path) -> Path:
    manifest = raw / "manifest.yaml"
    manifest.write_text(
        "sources:\n"
        "  - file_path: sample.txt\n"
        "    title: Synthetic test record\n"
        "    issuer: Test issuer\n"
        "    publication_date: 2025-01-01\n"
        "    jurisdiction: Test jurisdiction\n"
        "    language: en\n"
        "    document_type: policy\n",
        encoding="utf-8",
    )
    return manifest


def test_pipeline_writes_parseable_deterministic_jsonl(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "sample.txt").write_text(
        "Synthetic first paragraph.\n\nSynthetic second paragraph.", encoding="utf-8"
    )
    manifest = make_manifest(raw)
    config = ChunkingConfig(max_chars=30, overlap_chars=5, min_chars=1)
    first = IngestionPipeline(config).run(raw, manifest, tmp_path / "processed")
    second = IngestionPipeline(config).run(raw, manifest, tmp_path / "processed", overwrite=True)

    assert [item.document_id for item in first.documents] == [
        item.document_id for item in second.documents
    ]
    assert [item.chunk_id for item in first.chunks] == [item.chunk_id for item in second.chunks]
    document_line = (
        (tmp_path / "processed" / "documents.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    chunk_line = (
        (tmp_path / "processed" / "chunks.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert PolicyDocument.model_validate_json(document_line).source_file_sha256 is not None
    assert SourceChunk.model_validate_json(chunk_line).chunking_version == "paragraph-chunker-v1"
    report = json.loads(
        (tmp_path / "processed" / "ingestion_report.json").read_text(encoding="utf-8")
    )
    assert report["documents_processed"] == 1


def test_pipeline_reports_unlisted_files_and_protects_output(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "sample.txt").write_text("Synthetic test text.", encoding="utf-8")
    (raw / "unlisted.md").write_text("# Synthetic", encoding="utf-8")
    manifest = make_manifest(raw)
    pipeline = IngestionPipeline()
    result = pipeline.run(raw, manifest, tmp_path / "processed")

    assert result.report.warnings == ["Unlisted supported file: unlisted.md"]
    with pytest.raises(ManifestValidationError, match="without manifest entries"):
        pipeline.run(
            raw,
            manifest,
            tmp_path / "other-output",
            fail_on_unlisted_files=True,
        )
    with pytest.raises(OutputExistsError):
        pipeline.run(raw, manifest, tmp_path / "processed")


def test_pipeline_records_parser_failures(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "invalid.txt").write_bytes(b"\xff\xfe")
    manifest = raw / "manifest.yaml"
    manifest.write_text(
        "sources:\n  - file_path: invalid.txt\n    title: Synthetic\n    issuer: Test\n"
        "    publication_date: 2025-01-01\n    jurisdiction: Test\n    language: en\n"
        "    document_type: policy\n",
        encoding="utf-8",
    )

    result = IngestionPipeline().run(raw, manifest, tmp_path / "processed")

    assert result.report.documents_failed == 1
    assert result.report.documents[0].status == "failed"
    assert result.report.documents[0].error is not None
