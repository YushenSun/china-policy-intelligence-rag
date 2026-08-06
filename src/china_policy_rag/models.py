"""Typed domain models shared by future project phases."""

from datetime import date
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class Language(StrEnum):
    """Languages supported by the planned MVP."""

    CHINESE = "zh"
    ENGLISH = "en"


class DocumentType(StrEnum):
    """High-level source document categories."""

    POLICY = "policy"
    INDUSTRY_REPORT = "industry_report"
    REGULATION = "regulation"
    LAW = "law"
    STRATEGY = "strategy"
    ACTION_PLAN = "action-plan"
    OTHER = "other"


class RiskCategory(StrEnum):
    """Categories used to group risk factors."""

    POLICY = "policy"
    REGULATORY = "regulatory"
    MARKET = "market"
    OPERATIONAL = "operational"
    GEOPOLITICAL = "geopolitical"
    TECHNOLOGY = "technology"
    OTHER = "other"


class PolicyDocument(BaseModel):
    """Metadata and text for one authorised source document."""

    model_config = ConfigDict(str_strip_whitespace=True)

    document_id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1)
    issuer: str = Field(min_length=1)
    publication_date: date
    jurisdiction: str = Field(min_length=1)
    language: Language
    document_type: DocumentType
    sector_tags: list[str] = Field(default_factory=list)
    source_url: HttpUrl | None = None
    local_file_path: Path | None = None
    text: str = Field(min_length=1)
    source_file_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    parser_name: str | None = Field(default=None, min_length=1)
    parser_version: str | None = Field(default=None, min_length=1)

    @field_validator("sector_tags")
    @classmethod
    def validate_sector_tags(cls, value: list[str]) -> list[str]:
        """Reject empty sector labels that would weaken filtering."""
        if any(not tag.strip() for tag in value):
            raise ValueError("sector_tags must not contain empty values")
        return value


class SourceChunk(BaseModel):
    """An evidence-addressable text segment from a policy document."""

    model_config = ConfigDict(str_strip_whitespace=True)

    chunk_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    page_reference: str | None = Field(default=None, min_length=1)
    section_reference: str | None = Field(default=None, min_length=1)
    character_start: int | None = Field(default=None, ge=0)
    character_end: int | None = Field(default=None, ge=0)
    source_file_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    chunking_version: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_character_range(self) -> "SourceChunk":
        """Ensure optional character offsets form a valid half-open range."""
        if (
            self.character_start is not None
            and self.character_end is not None
            and self.character_end < self.character_start
        ):
            raise ValueError("character_end must not be less than character_start")
        return self


class RetrievalHit(BaseModel):
    """A retrieved source chunk and its normalized relevance score."""

    chunk: SourceChunk
    score: float = Field(ge=0.0, le=1.0)
    retrieval_method: str = Field(min_length=1)
    lexical_score: float | None = None
    semantic_score: float | None = None
    fused_score: float | None = None
    lexical_rank: int | None = Field(default=None, ge=1)
    semantic_rank: int | None = Field(default=None, ge=1)


class Citation(BaseModel):
    """A precise reference to evidence supporting an analytical output."""

    model_config = ConfigDict(str_strip_whitespace=True)

    document_id: UUID
    source_title: str = Field(min_length=1)
    evidence_location: str = Field(min_length=1)
    quoted_evidence: str = Field(min_length=1)
    chunk_id: UUID | None = None


class GroundedAnswer(BaseModel):
    """An answer that must identify its supporting evidence."""

    model_config = ConfigDict(str_strip_whitespace=True)

    answer: str = Field(min_length=1)
    citations: list[Citation] = Field(min_length=1)
    uncertainty: str | None = Field(default=None, min_length=1)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class RiskFactor(BaseModel):
    """One evidence-supported risk or opportunity factor."""

    model_config = ConfigDict(str_strip_whitespace=True)

    category: RiskCategory
    description: str = Field(min_length=1)
    affected_sectors: list[str] = Field(min_length=1)
    opportunities: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    uncertainty: str | None = Field(default=None, min_length=1)

    @field_validator("affected_sectors", "opportunities", "risks")
    @classmethod
    def validate_nonempty_items(cls, value: list[str]) -> list[str]:
        """Prevent blank labels from entering structured outputs."""
        if any(not item.strip() for item in value):
            raise ValueError("list values must not contain empty strings")
        return value


class RiskBrief(BaseModel):
    """A structured, cited analytical brief for future generation workflows."""

    model_config = ConfigDict(str_strip_whitespace=True)

    brief_id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    risk_factors: list[RiskFactor] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(min_length=1)
    overall_uncertainty: str | None = Field(default=None, min_length=1)

    @field_validator("assumptions")
    @classmethod
    def validate_assumptions(cls, value: list[str]) -> list[str]:
        """Reject blank assumption statements."""
        if any(not assumption.strip() for assumption in value):
            raise ValueError("assumptions must not contain empty strings")
        return value

    @model_validator(mode="after")
    def require_cited_risk_factors(self) -> "RiskBrief":
        """Keep the brief-level citation requirement explicit in the contract."""
        if not self.citations:
            raise ValueError("risk briefs require at least one supporting citation")
        return self
