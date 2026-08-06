"""Tests for deterministic bilingual paragraph-aware chunking."""

import pytest
from pydantic import ValidationError

from china_policy_rag.ingestion.base import ChunkingConfig
from china_policy_rag.ingestion.chunking import chunk_section


def test_chunking_is_deterministic_preserves_text_and_overlap() -> None:
    text = "First sentence. Second sentence.\n\n中文第一句。中文第二句。"
    config = ChunkingConfig(max_chars=28, overlap_chars=6, min_chars=1)

    first = chunk_section(text, config)
    second = chunk_section(text, config)

    assert first == second
    assert first[0].text in text
    assert first[-1].end == len(text)
    assert first[1].start == first[0].end - 6


def test_chunking_handles_single_long_paragraph_and_short_text() -> None:
    long_chunks = chunk_section(
        "x" * 40, ChunkingConfig(max_chars=12, overlap_chars=2, min_chars=1)
    )
    short_chunks = chunk_section(
        "短文。", ChunkingConfig(max_chars=12, overlap_chars=2, min_chars=1)
    )

    assert len(long_chunks) > 1
    assert short_chunks[0].text == "短文。"


def test_chunking_rejects_invalid_overlap() -> None:
    with pytest.raises(ValidationError, match="overlap_chars"):
        ChunkingConfig(max_chars=10, overlap_chars=10)
