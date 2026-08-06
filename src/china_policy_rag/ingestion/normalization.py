"""Conservative bilingual text normalization."""

import re
import unicodedata


def normalize_text(text: str) -> str:
    """Normalize safe formatting while retaining punctuation and paragraph structure."""
    normalized = unicodedata.normalize("NFC", text).replace("\x00", "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()
