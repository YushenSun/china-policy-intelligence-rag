"""Typed contracts for domain tools, agent runs, approval, and traces."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

from china_policy_rag.analysis.models import (
    GroundedAnalysis,
    ScopeAssessment,
    SufficiencyAssessment,
    TopicEvidence,
    TrainingDataRiskBrief,
    VerificationResult,
)

T = TypeVar("T")


class ToolErrorCode(StrEnum):
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    INVALID_CHUNK_ID = "INVALID_CHUNK_ID"
    EXCLUDED_EVIDENCE = "EXCLUDED_EVIDENCE"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    OUTPUT_PATH_REJECTED = "OUTPUT_PATH_REJECTED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    WORKFLOW_LIMIT_EXCEEDED = "WORKFLOW_LIMIT_EXCEEDED"
    REPEATED_TOOL_CALL = "REPEATED_TOOL_CALL"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class VerificationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ToolResult(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error_code: ToolErrorCode | None = None
    error_message: str | None = None
    warnings: list[str] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)
    verification_status: VerificationStatus = VerificationStatus.NOT_APPLICABLE


class TopicScopeSummary(BaseModel):
    topic: str
    jurisdictions: list[str]
    evidence_set_version: str
    allowed_dimensions: list[str]
    limitations: list[str]
    relevant_chunks: int
    core_chunks: int


class EvidenceHit(BaseModel):
    evidence: TopicEvidence
    retrieval_score: float


class EvidenceSearchResult(BaseModel):
    query: str
    hits: list[EvidenceHit]
    excluded_label_zero: bool = True


class QuestionAssessment(BaseModel):
    scope: ScopeAssessment
    sufficiency: SufficiencyAssessment
    evidence_gaps: list[str]
    relevant_jurisdictions: list[str]
    recommended_workflow: list[str]


class ValidatedArtifact(BaseModel):
    identifier: str
    kind: str
    content: GroundedAnalysis | TrainingDataRiskBrief
    verification: VerificationResult
    evidence_chunk_ids: list[UUID]


class EvidenceGapReport(BaseModel):
    evidence_set_version: str
    known_gaps: list[str]


class ApprovalDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NOT_REQUIRED = "NOT_REQUIRED"


class ExportReceipt(BaseModel):
    artifact_identifier: str
    output_path: str
    format: str
    approval: ApprovalDecision


class AgentLimits(BaseModel):
    maximum_turns: int = Field(default=8, ge=1, le=20)
    maximum_tool_calls: int = Field(default=10, ge=1, le=30)
    maximum_search_calls: int = Field(default=3, ge=1, le=10)
    maximum_generation_calls: int = Field(default=2, ge=1, le=5)
    maximum_export_calls: int = Field(default=1, ge=1, le=3)


class WorkflowStatus(StrEnum):
    COMPLETED = "COMPLETED"
    REFUSED = "REFUSED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"


class ToolCallRecord(BaseModel):
    sequence: int
    tool_name: str
    arguments: dict[str, object]
    duration_ms: float = Field(ge=0)
    success: bool
    error_code: str | None = None


class WorkflowTrace(BaseModel):
    run_id: UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    question_hash: str
    model_identifier: str
    tool_calls: list[ToolCallRecord]
    evidence_chunk_ids: list[UUID]
    verification_status: VerificationStatus
    refusal_status: WorkflowStatus
    total_turns: int
    total_tool_calls: int


class AgentRunResult(BaseModel):
    run_id: UUID
    status: WorkflowStatus
    output: GroundedAnalysis | TrainingDataRiskBrief | None = None
    artifact_identifier: str | None = None
    verification: VerificationResult | None = None
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    evidence_chunk_ids: list[UUID] = Field(default_factory=list)
    error_code: ToolErrorCode | None = None
    message: str
    export: ExportReceipt | None = None
