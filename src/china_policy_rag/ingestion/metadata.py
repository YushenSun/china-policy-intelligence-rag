"""YAML manifest loading and path-safe metadata validation."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .base import SUPPORTED_EXTENSIONS, ManifestEntry, ManifestValidationError


def _safe_relative_path(raw_path: Path) -> Path:
    """Validate a manifest path without relying on the current working directory."""
    if raw_path.is_absolute() or ".." in raw_path.parts:
        raise ManifestValidationError(
            "file_path must be a relative path inside the raw-data directory"
        )
    return Path(*raw_path.parts)


def load_manifest(manifest_path: Path, raw_data_dir: Path) -> list[ManifestEntry]:
    """Load entries, reject duplicates, and require each declared file to exist."""
    try:
        raw_content: Any = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ManifestValidationError(f"Cannot read manifest: {manifest_path}") from error
    except yaml.YAMLError as error:
        raise ManifestValidationError(f"Invalid YAML manifest: {error}") from error

    entries_data = raw_content.get("sources") if isinstance(raw_content, dict) else None
    if not isinstance(entries_data, list):
        raise ManifestValidationError("Manifest must contain a 'sources' list")

    entries: list[ManifestEntry] = []
    seen_paths: set[Path] = set()
    for index, entry_data in enumerate(entries_data, start=1):
        try:
            entry = ManifestEntry.model_validate(entry_data)
        except ValidationError as error:
            raise ManifestValidationError(f"Invalid manifest entry {index}: {error}") from error
        relative_path = _safe_relative_path(entry.file_path)
        if relative_path in seen_paths:
            raise ManifestValidationError(
                f"Duplicate manifest file_path: {relative_path.as_posix()}"
            )
        if relative_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ManifestValidationError(
                f"Unsupported manifest file type: {relative_path.suffix or '(none)'}"
            )
        resolved_raw = raw_data_dir.resolve()
        resolved_source = (raw_data_dir / relative_path).resolve()
        if not resolved_source.is_relative_to(resolved_raw):
            raise ManifestValidationError("file_path must not escape the raw-data directory")
        if not resolved_source.is_file():
            raise ManifestValidationError(
                f"Manifest source file does not exist: {relative_path.as_posix()}"
            )
        seen_paths.add(relative_path)
        entries.append(entry.model_copy(update={"file_path": relative_path}))
    return entries
