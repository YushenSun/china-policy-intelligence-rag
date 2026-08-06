"""Atomic JSONL and JSON output for processed local data."""

import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

from .base import OutputExistsError


def ensure_output_paths(output_dir: Path, overwrite: bool) -> dict[str, Path]:
    """Return output paths while protecting non-empty existing artifacts."""
    paths = {
        "documents": output_dir / "documents.jsonl",
        "chunks": output_dir / "chunks.jsonl",
        "report": output_dir / "ingestion_report.json",
    }
    existing = [path for path in paths.values() if path.exists() and path.stat().st_size > 0]
    if existing and not overwrite:
        names = ", ".join(path.name for path in existing)
        raise OutputExistsError(f"Refusing to overwrite existing output: {names}")
    return paths


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", text=True
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        temporary_path.replace(path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def write_jsonl(path: Path, records: Iterable[BaseModel]) -> None:
    """Atomically write typed records as one JSON object per line."""
    content = "".join(f"{record.model_dump_json()}\n" for record in records)
    _atomic_write(path, content)


def write_json(path: Path, record: BaseModel) -> None:
    """Atomically write a typed record as formatted JSON."""
    content = json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    _atomic_write(path, content)
