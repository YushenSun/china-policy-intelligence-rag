"""Shared types and domain-specific errors for local ingestion."""

from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from china_policy_rag.models import DocumentType, Language

PIPELINE_VERSION = "phase1-v1"
IDENTIFIER_VERSION = "document-id-v1"
CHUNKING_VERSION = "paragraph-chunker-v1"
SUPPORTED_EXTENSIONS = frozenset({".txt", ".md", ".html", ".htm", ".pdf"})


class IngestionError(Exception):
    """Base exception for expected ingestion failures."""


class ManifestValidationError(IngestionError):
    """Raised when a manifest cannot be validated against local inputs."""


class UnsupportedFileTypeError(IngestionError):
    """Raised when a source does not have a supported local file extension."""


class TextExtractionError(IngestionError):
    """Raised when a parser cannot reliably extract local text."""


class EmptyDocumentError(TextExtractionError):
    """Raised when no usable text can be extracted from a source."""


class OutputExistsError(IngestionError):
    """Raised when an ingestion run would overwrite existing output."""


class ManifestEntry(BaseModel):
    """Human-authored metadata attached to one local source file."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    file_path: Path
    title: str = Field(min_length=1)
    issuer: str = Field(min_length=1)
    publication_date: date
    jurisdiction: str = Field(min_length=1)
    language: Language
    document_type: DocumentType
    sector_tags: list[str] = Field(default_factory=list)
    source_url: HttpUrl | None = None
    access_date: date | None = None
    notes: str | None = None


class ExtractedSection(BaseModel):
    """Text from one source page or logical section before chunking."""

    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1)
    page_number: int | None = Field(default=None, ge=1)
    section_reference: str | None = Field(default=None, min_length=1)


class ExtractedDocument(BaseModel):
    """A parser-neutral representation of local extracted text."""

    relative_path: Path
    file_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    parser_name: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    sections: list[ExtractedSection] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)


class ChunkingConfig(BaseModel):
    """Character-based chunking parameters for deterministic Phase 1 output."""

    max_chars: int = Field(default=1200, gt=0)
    overlap_chars: int = Field(default=150, ge=0)
    min_chars: int = Field(default=100, ge=1)

    def model_post_init(self, __context: object) -> None:
        if self.overlap_chars >= self.max_chars:
            raise ValueError("overlap_chars must be smaller than max_chars")


class DocumentStatus(BaseModel):
    """Report-safe status for a single declared source file."""

    file_path: str
    status: str
    document_id: str | None = None
    file_sha256: str | None = None
    parser_name: str | None = None
    chunk_count: int = 0
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)


class IngestionReport(BaseModel):
    """Machine-readable summary that omits full document text."""

    pipeline_version: str = PIPELINE_VERSION
    started_at: datetime
    completed_at: datetime
    input_directory: str
    manifest_path: str
    manifest_entries: int
    discovered_files: int
    documents_processed: int
    documents_failed: int
    chunks_produced: int
    warnings: list[str] = Field(default_factory=list)
    documents: list[DocumentStatus] = Field(default_factory=list)
    output_paths: dict[str, str]
    chunking_configuration: ChunkingConfig
