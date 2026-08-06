"""Deterministic paragraph-aware character chunking."""

import re
from dataclasses import dataclass

from .base import ChunkingConfig

SENTENCE_BOUNDARY = re.compile(r"[。！？；.!?;](?:\s|$)")


@dataclass(frozen=True)
class ChunkSpan:
    """A chunk and its half-open character offsets within one normalized section."""

    text: str
    start: int
    end: int


def _best_end(text: str, start: int, maximum: int) -> int:
    limit = min(start + maximum, len(text))
    if limit == len(text):
        return limit
    candidate = max(text.rfind("\n\n", start, limit), text.rfind("\n", start, limit))
    if candidate > start:
        return candidate
    boundaries = [match.end() for match in SENTENCE_BOUNDARY.finditer(text, start, limit)]
    if boundaries:
        return boundaries[-1]
    return limit


def chunk_section(text: str, config: ChunkingConfig) -> list[ChunkSpan]:
    """Split one normalized section without loss, using overlap after each chunk."""
    if not text:
        return []
    chunks: list[ChunkSpan] = []
    start = 0
    while start < len(text):
        end = _best_end(text, start, config.max_chars)
        if end <= start:
            end = min(start + config.max_chars, len(text))
        chunks.append(ChunkSpan(text=text[start:end], start=start, end=end))
        if end == len(text):
            break
        start = max(end - config.overlap_chars, start + 1)
    if len(chunks) > 1 and len(chunks[-1].text) < config.min_chars:
        previous = chunks[-2]
        merged_end = chunks[-1].end
        if merged_end - previous.start <= config.max_chars:
            chunks[-2] = ChunkSpan(
                text=text[previous.start : merged_end], start=previous.start, end=merged_end
            )
            chunks.pop()
    return chunks
