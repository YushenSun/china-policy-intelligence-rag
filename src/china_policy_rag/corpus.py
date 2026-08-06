"""Validation for the fixed authoritative Phase 2.5 local corpus."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from .ingestion.metadata import load_manifest


def validate_corpus(raw_dir: Path, manifest: Path, output: Path) -> dict[str, object]:
    """Validate declared local files without exposing document text in the report."""
    entries = load_manifest(manifest, raw_dir)
    hashes: dict[str, str] = {}
    files: list[dict[str, object]] = []
    for entry in entries:
        path = raw_dir / entry.file_path
        payload = path.read_bytes()
        if not payload:
            raise ValueError(f"Empty source file: {entry.file_path}")
        if path.suffix.lower() == ".pdf" and not payload.startswith(b"%PDF"):
            raise ValueError(f"Invalid PDF magic bytes: {entry.file_path}")
        preview = payload[:20000].decode("utf-8", errors="ignore").lower()
        if path.suffix.lower() in {".html", ".htm"} and any(
            item in preview for item in ("captcha", "access denied", "not a robot")
        ):
            raise ValueError(f"Likely anti-bot HTML payload: {entry.file_path}")
        digest = hashlib.sha256(payload).hexdigest()
        if digest in hashes:
            raise ValueError(f"Duplicate content: {entry.file_path} and {hashes[digest]}")
        hashes[digest] = entry.file_path.as_posix()
        files.append(
            {"file_path": entry.file_path.as_posix(), "sha256": digest, "bytes": len(payload)}
        )
    report: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "valid_count": len(files),
        "files": files,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
