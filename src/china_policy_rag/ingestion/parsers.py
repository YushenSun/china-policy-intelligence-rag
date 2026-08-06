"""Format-specific local parsers that never fetch or execute external content."""

from hashlib import sha256
from pathlib import Path
from typing import Protocol

from bs4 import BeautifulSoup
from pypdf import PdfReader

from .base import EmptyDocumentError, ExtractedDocument, ExtractedSection, TextExtractionError
from .normalization import normalize_text


class DocumentParser(Protocol):
    """Protocol implemented by local format parsers."""

    name: str
    version: str

    def parse(self, path: Path, relative_path: Path) -> ExtractedDocument:
        """Extract text and source-local references from one path."""


def _file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _document(
    path: Path,
    relative_path: Path,
    name: str,
    sections: list[ExtractedSection],
    warnings: list[str] | None = None,
) -> ExtractedDocument:
    if not sections:
        raise EmptyDocumentError(f"No usable text extracted from {relative_path.as_posix()}")
    return ExtractedDocument(
        relative_path=relative_path,
        file_sha256=_file_hash(path),
        parser_name=name,
        parser_version="1",
        sections=sections,
        warnings=warnings or [],
    )


class TextParser:
    name = "text"
    version = "1"

    def parse(self, path: Path, relative_path: Path) -> ExtractedDocument:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as error:
            raise TextExtractionError(
                f"TXT file is not valid UTF-8: {relative_path.as_posix()}"
            ) from error
        normalized = normalize_text(text)
        return _document(
            path,
            relative_path,
            self.name,
            [ExtractedSection(text=normalized)] if normalized else [],
        )


class MarkdownParser:
    name = "markdown"
    version = "1"

    def parse(self, path: Path, relative_path: Path) -> ExtractedDocument:
        try:
            raw_text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as error:
            raise TextExtractionError(
                f"Markdown file is not valid UTF-8: {relative_path.as_posix()}"
            ) from error
        lines = raw_text.splitlines()
        if lines[:1] == ["---"]:
            try:
                closing_index = lines[1:].index("---") + 1
                lines = lines[closing_index + 1 :]
            except ValueError:
                pass
        sections: list[ExtractedSection] = []
        current_heading: str | None = None
        current_lines: list[str] = []
        for line in lines:
            if line.lstrip().startswith("#"):
                text = normalize_text("\n".join(current_lines))
                if text:
                    sections.append(ExtractedSection(text=text, section_reference=current_heading))
                current_heading = line.lstrip("#").strip() or None
                current_lines = []
            else:
                current_lines.append(line)
        text = normalize_text("\n".join(current_lines))
        if text:
            sections.append(ExtractedSection(text=text, section_reference=current_heading))
        return _document(path, relative_path, self.name, sections)


class HtmlParser:
    name = "html"
    version = "1"

    def parse(self, path: Path, relative_path: Path) -> ExtractedDocument:
        try:
            raw_html = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as error:
            raise TextExtractionError(
                f"HTML file is not valid UTF-8: {relative_path.as_posix()}"
            ) from error
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup(["script", "style", "nav", "noscript", "template"]):
            tag.decompose()
        title = normalize_text(soup.title.get_text(" ", strip=True)) if soup.title else None
        text = normalize_text(soup.get_text("\n", strip=True))
        return _document(
            path,
            relative_path,
            self.name,
            [ExtractedSection(text=text, section_reference=title)] if text else [],
        )


class PdfParser:
    name = "pypdf"
    version = "1"

    def parse(self, path: Path, relative_path: Path) -> ExtractedDocument:
        try:
            reader = PdfReader(path)
        except Exception as error:
            raise TextExtractionError(f"Cannot read PDF: {relative_path.as_posix()}") from error
        sections: list[ExtractedSection] = []
        warnings: list[str] = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                text = normalize_text(page.extract_text() or "")
            except Exception as error:
                raise TextExtractionError(
                    f"Failed to extract PDF page {page_number}: {relative_path.as_posix()}"
                ) from error
            if text:
                sections.append(ExtractedSection(text=text, page_number=page_number))
            else:
                warnings.append(f"No extractable text on PDF page {page_number}")
        if not sections:
            raise EmptyDocumentError(
                f"PDF has no usable text: {relative_path.as_posix()}. Scanned PDFs require OCR, "
                "which is not supported in Phase 1."
            )
        return _document(path, relative_path, self.name, sections, warnings)


def parser_for(path: Path) -> DocumentParser:
    """Choose a parser solely from a supported local file extension."""
    extension = path.suffix.lower()
    parsers: dict[str, DocumentParser] = {
        ".txt": TextParser(),
        ".md": MarkdownParser(),
        ".html": HtmlParser(),
        ".htm": HtmlParser(),
        ".pdf": PdfParser(),
    }
    try:
        return parsers[extension]
    except KeyError as error:
        raise TextExtractionError(f"Unsupported file type: {extension or '(none)'}") from error
