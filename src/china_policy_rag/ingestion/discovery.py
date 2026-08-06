"""Safe discovery of supported local source files."""

from pathlib import Path

from .base import SUPPORTED_EXTENSIONS


def discover_source_files(input_dir: Path) -> set[Path]:
    """Return normalized relative paths for supported files under an input directory."""
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    return {
        path.relative_to(input_dir)
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    }
