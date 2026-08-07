"""Typed contracts for scoped evidence, grounded claims, and risk briefs."""

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ScopeStatus(StrEnum):
    IN_SCOPE = "IN_SCOPE"
    PARTIALLY_IN_SCOPE = "PARTIALLY_IN_SCOPE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class SufficiencyStatus(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    LIMITED = "LIMITED"
    INSUFFICIENT = "INSUFFICIENT"


class ClaimType(StrEnum):
    OBLIGATION = "obligation"
    PROHIBITION = "prohibition"
    TRANSPARENCY_REQUIREMENT = "transparency_requirement"
    DOCUMENTATION_REQUIREMENT = "documentation_requirement"
    DATA_QUALITY_REQUIREMENT = "data_quality_requirement"
    COPYRIGHT_REQUIREMENT = "copyright_requirement"
    PERSONAL_DATA_REQUIREMENT = "personal_data_requirement"
    SECURITY_REQUIREMENT = "security_requirement"
    COMPARISON = "comparison"
    IMPLICATION = "implication"
    UNCERTAINTY = "uncertainty"


class InferenceLevel(StrEnum):
    DIRECT = "DIRECT"
    SYNTHESIS = "SYNTHESIS"
    INTERPRETIVE = "INTERPRETIVE"


class RiskSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class TopicEvidence(BaseModel):
    """An exact human-labelled source chunk with complete provenance."""

    model_config = ConfigDict(str_strip_whitespace=True)

    chunk_id: UUID
    document_id: UUID
    title: str = Field(min_length=1)
    issuer: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=1)
    publication_date: date
    language: str = Field(min_length=2)
    local_file_path: str = Field(min_length=1)
    source_url: str | None = None
    page_reference: str | None = None
    section_reference: str | None = None
    text: str = Field(min_length=1, max_length=20_000)
    human_label: int = Field(ge=1, le=2)
    reviewer_note: str | None = None

    @model_validator(mode="after")
    def require_core_note(self) -> "TopicEvidence":
        if self.human_label == 2 and not self.reviewer_note:
            raise ValueError("label-2 evidence requires a reviewer note")
        return self


class EvidenceBudget(BaseModel):
    maximum_chunks: int = Field(default=8, ge=1, le=20)
    maximum_core_chunks: int = Field(default=6, ge=1, le=20)
    maximum_supporting_chunks: int = Field(default=3, ge=0, le=20)
    minimum_core_chunks: int = Field(default=1, ge=1, le=20)


class ScopeAssessment(BaseModel):
    status: ScopeStatus
    explanation: str = Field(min_length=1)
    matched_topics: list[str] = Field(default_factory=list)


class EvidenceSelection(BaseModel):
    question: str
    evidence: list[TopicEvidence]
    comparison_requested: bool = False
    retrieval_scores: dict[UUID, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class SufficiencyAssessment(BaseModel):
    status: SufficiencyStatus
    explanation: str = Field(min_length=1)
    supported_aspects: list[str] = Field(default_factory=list)
    missing_aspects: list[str] = Field(default_factory=list)


class AnalysisClaim(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    claim_id: str = Field(pattern=r"^C[0-9]{2,}$")
    claim_text: str = Field(min_length=1)
    claim_type: ClaimType
    jurisdiction: str = Field(min_length=1)
    citation_chunk_ids: list[UUID] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    qualification: str | None = None
    inference_level: InferenceLevel

    @field_validator("citation_chunk_ids")
    @classmethod
    def reject_duplicate_citations(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("citation_chunk_ids must not contain duplicates")
        return value

    @model_validator(mode="after")
    def require_interpretive_qualification(self) -> "AnalysisClaim":
        if self.inference_level is InferenceLevel.INTERPRETIVE and not self.qualification:
            raise ValueError("interpretive claims require a qualification")
        return self


class GroundedAnalysis(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1)
    scope_status: ScopeStatus
    scope_explanation: str = Field(min_length=1)
    sufficiency_status: SufficiencyStatus
    short_answer: str = Field(min_length=1)
    claims: list[AnalysisClaim] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evidence_set_version: str = Field(min_length=1)
    model_identifier: str = Field(min_length=1)
    disclaimer: str = "Policy research output; not legal advice."


class VerificationIssue(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    claim_id: str | None = None


class VerificationResult(BaseModel):
    passed: bool
    errors: list[VerificationIssue] = Field(default_factory=list)
    warnings: list[VerificationIssue] = Field(default_factory=list)
    verified_claim_count: int = Field(ge=0)
    rejected_claim_count: int = Field(ge=0)
    evidence_coverage: float = Field(ge=0.0, le=1.0)


class DueDiligenceQuestion(BaseModel):
    question_id: str = Field(pattern=r"^D[0-9]{2,}$")
    question: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=1)
    evidence_chunk_ids: list[UUID] = Field(min_length=1)


class TrainingDataRiskFactor(BaseModel):
    risk_id: str = Field(pattern=r"^R[0-9]{2,}$")
    category: ClaimType
    jurisdiction: str = Field(min_length=1)
    description: str = Field(min_length=1)
    business_relevance: str = Field(min_length=1)
    severity: RiskSeverity
    evidence_chunk_ids: list[UUID] = Field(min_length=1)
    mitigation_question: str = Field(min_length=1)
    inference_level: InferenceLevel
    high_severity_justification: str | None = None

    @model_validator(mode="after")
    def require_high_severity_details(self) -> "TrainingDataRiskFactor":
        if self.severity is RiskSeverity.HIGH and not self.high_severity_justification:
            raise ValueError("HIGH risk requires a written justification")
        return self


class TrainingDataRiskBrief(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1)
    executive_summary: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    china_findings: list[AnalysisClaim] = Field(default_factory=list)
    eu_findings: list[AnalysisClaim] = Field(default_factory=list)
    comparative_findings: list[AnalysisClaim] = Field(default_factory=list)
    risk_factors: list[TrainingDataRiskFactor] = Field(default_factory=list)
    recommended_due_diligence_questions: list[DueDiligenceQuestion] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    citations: list[UUID] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evidence_set_version: str = Field(min_length=1)
    model_identifier: str = Field(min_length=1)
    disclaimer: str = "Analytical prioritisation only; not legal advice."
