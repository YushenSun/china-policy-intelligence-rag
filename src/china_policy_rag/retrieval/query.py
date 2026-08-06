"""Conservative query normalization that preserves bilingual identifiers."""

import re
import unicodedata


def normalize_query(text: str) -> str:
    """NFC-normalize and collapse whitespace without translation or lowercasing."""
    normalized = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        raise ValueError("query text must not be empty")
    return normalized
