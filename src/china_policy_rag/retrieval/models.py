"""Typed query, filtering, score, and evidence contracts."""

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from china_policy_rag.models import DocumentType, Language, SourceChunk


class RetrievalMode(StrEnum):
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class MetadataFilters(BaseModel):
    """Inclusive AND-across-field / OR-within-field retrieval filters."""

    model_config = ConfigDict(str_strip_whitespace=True)

    languages: list[Language] = Field(default_factory=list)
    jurisdictions: list[str] = Field(default_factory=list)
    document_types: list[DocumentType] = Field(default_factory=list)
    issuers: list[str] = Field(default_factory=list)
    sector_tags: list[str] = Field(default_factory=list)
    publication_date_from: date | None = None
    publication_date_to: date | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "MetadataFilters":
        if (
            self.publication_date_from is not None
            and self.publication_date_to is not None
            and self.publication_date_from > self.publication_date_to
        ):
            raise ValueError("publication_date_from must not be after publication_date_to")
        return self


class RetrievalQuery(BaseModel):
    """Validated query and retrieval settings; original text remains unmodified."""

    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1)
    top_k: int = Field(default=5, gt=0)
    candidate_k: int = Field(default=20, gt=0)
    mode: RetrievalMode = RetrievalMode.HYBRID
    filters: MetadataFilters = Field(default_factory=MetadataFilters)
    lexical_weight: float = Field(default=1.0, ge=0.0)
    semantic_weight: float = Field(default=1.0, ge=0.0)

    @model_validator(mode="after")
    def validate_retrieval_settings(self) -> "RetrievalQuery":
        if self.candidate_k < self.top_k:
            raise ValueError("candidate_k must be greater than or equal to top_k")
        if self.mode is RetrievalMode.HYBRID and not (self.lexical_weight or self.semantic_weight):
            raise ValueError("at least one hybrid retrieval weight must be enabled")
        return self


class RetrievalScores(BaseModel):
    lexical_score: float | None = None
    semantic_score: float | None = None
    fused_score: float | None = None
    lexical_rank: int | None = Field(default=None, ge=1)
    semantic_rank: int | None = Field(default=None, ge=1)


class EvidenceItem(BaseModel):
    """A citation-ready exact source chunk with metadata and retrieval scores."""

    rank: int = Field(ge=1)
    chunk_id: UUID
    document_id: UUID
    title: str
    issuer: str
    publication_date: date
    language: Language
    jurisdiction: str
    source_url: str | None = None
    local_file_path: Path | None = None
    page_reference: str | None = None
    section_reference: str | None = None
    text: str
    scores: RetrievalScores


class EvidenceBundle(BaseModel):
    """A retrieval artefact, not a generated answer or a factual conclusion."""

    original_query: str
    normalized_query: str
    retrieval_mode: RetrievalMode
    filters: MetadataFilters
    index_version: str
    generated_at: datetime
    evidence: list[EvidenceItem]
    warnings: list[str] = Field(default_factory=list)
    retrieval_configuration: dict[str, str | int | float | bool]


class IndexedCorpus(BaseModel):
    chunks: list[SourceChunk]
    documents: dict[UUID, dict[str, object]]
