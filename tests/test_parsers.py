"""Tests for offline local parsers using only synthetic fixture content."""

from pathlib import Path

import pytest
from pypdf import PdfWriter

from china_policy_rag.ingestion.base import EmptyDocumentError
from china_policy_rag.ingestion.parsers import HtmlParser, MarkdownParser, PdfParser, TextParser


def write_text_pdf(path: Path, text: str) -> None:
    """Write a minimal synthetic text PDF without adding a PDF-generation dependency."""
    encoded = text.encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length "
        + str(len(b"BT /F1 12 Tf 72 720 Td (" + encoded + b") Tj ET")).encode()
        + b" >>\nstream\nBT /F1 12 Tf 72 720 Td ("
        + encoded
        + b") Tj ET\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, object_data in enumerate(objects, start=1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode() + object_data + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    data.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    data.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    path.write_bytes(data)


def test_text_parser_handles_utf8_bom_and_mixed_language(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("Synthetic 中文。\n\nEnglish paragraph.", encoding="utf-8-sig")

    document = TextParser().parse(path, Path("sample.txt"))

    assert document.sections[0].text == "Synthetic 中文。\n\nEnglish paragraph."


def test_markdown_parser_preserves_heading_reference(tmp_path: Path) -> None:
    path = tmp_path / "sample.md"
    path.write_text("---\ntitle: ignored\n---\n# Heading\nSynthetic body.", encoding="utf-8")

    document = MarkdownParser().parse(path, Path("sample.md"))

    assert document.sections[0].section_reference == "Heading"
    assert document.sections[0].text == "Synthetic body."


def test_html_parser_removes_script_and_style(tmp_path: Path) -> None:
    path = tmp_path / "sample.html"
    path.write_text(
        "<title>Synthetic title</title><style>hidden</style><h1>Heading</h1>"
        "<script>bad()</script><p>中文。</p>",
        encoding="utf-8",
    )

    document = HtmlParser().parse(path, Path("sample.html"))

    assert "bad" not in document.sections[0].text
    assert "hidden" not in document.sections[0].text
    assert "Heading" in document.sections[0].text
    assert document.sections[0].section_reference == "Synthetic title"


def test_pdf_parser_preserves_one_indexed_page_reference(tmp_path: Path) -> None:
    path = tmp_path / "sample.pdf"
    write_text_pdf(path, "Synthetic PDF text")

    document = PdfParser().parse(path, Path("sample.pdf"))

    assert document.sections[0].page_number == 1
    assert "Synthetic PDF text" in document.sections[0].text


def test_pdf_parser_rejects_textless_pdf(tmp_path: Path) -> None:
    path = tmp_path / "empty.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with path.open("wb") as handle:
        writer.write(handle)

    with pytest.raises(EmptyDocumentError, match="require OCR"):
        PdfParser().parse(path, Path("empty.pdf"))
