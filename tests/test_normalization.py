"""Tests for conservative bilingual normalization."""

from china_policy_rag.ingestion.normalization import normalize_text


def test_normalization_preserves_chinese_punctuation_and_paragraphs() -> None:
    source = "Cafe\u0301\r\n中文。English!\x00\r\n\r\n\r\n第二段；still here?  \r\n"

    assert normalize_text(source) == "Café\n中文。English!\n\n第二段；still here?"
