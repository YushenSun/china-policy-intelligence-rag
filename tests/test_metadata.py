"""Tests for human-authored local source manifests."""

from pathlib import Path

import pytest

from china_policy_rag.ingestion.base import ManifestValidationError
from china_policy_rag.ingestion.metadata import load_manifest


def write_manifest(path: Path, source_lines: str) -> None:
    path.write_text(f"sources:\n{source_lines}", encoding="utf-8")


def valid_source(file_path: str = "sample.txt") -> str:
    return (
        f"  - file_path: {file_path}\n"
        "    title: Synthetic test source\n"
        "    issuer: Test issuer\n"
        "    publication_date: 2025-01-01\n"
        "    jurisdiction: Test jurisdiction\n"
        "    language: en\n"
        "    document_type: policy\n"
    )


def test_load_manifest_accepts_valid_local_source(tmp_path: Path) -> None:
    (tmp_path / "sample.txt").write_text("Synthetic test text.", encoding="utf-8")
    manifest = tmp_path / "manifest.yaml"
    write_manifest(manifest, valid_source())

    entries = load_manifest(manifest, tmp_path)

    assert entries[0].file_path == Path("sample.txt")


@pytest.mark.parametrize("path", ["../outside.txt", "sub/../../outside.txt", "C:/outside.txt"])
def test_load_manifest_rejects_path_escapes(tmp_path: Path, path: str) -> None:
    manifest = tmp_path / "manifest.yaml"
    write_manifest(manifest, valid_source(path))

    with pytest.raises(ManifestValidationError, match="relative path"):
        load_manifest(manifest, tmp_path)


def test_load_manifest_rejects_duplicate_paths(tmp_path: Path) -> None:
    (tmp_path / "sample.txt").write_text("Synthetic test text.", encoding="utf-8")
    manifest = tmp_path / "manifest.yaml"
    write_manifest(manifest, valid_source() + valid_source())

    with pytest.raises(ManifestValidationError, match="Duplicate"):
        load_manifest(manifest, tmp_path)


@pytest.mark.parametrize("field, value", [("language", "fr"), ("document_type", "unknown")])
def test_load_manifest_rejects_invalid_enums(tmp_path: Path, field: str, value: str) -> None:
    (tmp_path / "sample.txt").write_text("Synthetic test text.", encoding="utf-8")
    manifest = tmp_path / "manifest.yaml"
    write_manifest(
        manifest,
        valid_source().replace(
            f"    {field}: en" if field == "language" else "    document_type: policy",
            f"    {field}: {value}",
        ),
    )

    with pytest.raises(ManifestValidationError, match="Invalid manifest entry"):
        load_manifest(manifest, tmp_path)


def test_load_manifest_rejects_missing_file_and_unsupported_extension(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    write_manifest(manifest, valid_source("missing.docx"))

    with pytest.raises(ManifestValidationError, match="Unsupported"):
        load_manifest(manifest, tmp_path)


def test_load_manifest_rejects_missing_required_field_and_missing_source(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    write_manifest(manifest, "  - file_path: missing.txt\n    title: Synthetic\n")

    with pytest.raises(ManifestValidationError, match="Invalid manifest entry"):
        load_manifest(manifest, tmp_path)

    write_manifest(manifest, valid_source("missing.txt"))
    with pytest.raises(ManifestValidationError, match="does not exist"):
        load_manifest(manifest, tmp_path)
