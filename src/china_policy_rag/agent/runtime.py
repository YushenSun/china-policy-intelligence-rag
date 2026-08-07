"""Deterministic bounded runtime used offline and as the orchestration reference."""

import json
from collections import Counter
from collections.abc import Callable
from hashlib import sha256
from time import perf_counter
from typing import Any
from uuid import uuid4

from china_policy_rag.analysis.models import ScopeStatus, SufficiencyStatus

from .guardrails import check_user_input
from .models import (
    AgentLimits,
    AgentRunResult,
    ApprovalDecision,
    QuestionAssessment,
    ToolCallRecord,
    ToolErrorCode,
    ToolResult,
    VerificationStatus,
    WorkflowStatus,
    WorkflowTrace,
)
from .tools import DomainTools
from .trace import LocalTraceWriter


class WorkflowLimitError(RuntimeError):
    def __init__(self, code: ToolErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class ToolCallBudget:
    def __init__(self, limits: AgentLimits) -> None:
        self.limits = limits
        self.calls: list[ToolCallRecord] = []
        self._fingerprints: set[str] = set()
        self._counts: Counter[str] = Counter()

    def reserve(self, name: str, arguments: dict[str, object]) -> None:
        if len(self.calls) >= self.limits.maximum_turns:
            raise WorkflowLimitError(
                ToolErrorCode.WORKFLOW_LIMIT_EXCEEDED, "Maximum agent turns reached"
            )
        if len(self.calls) >= self.limits.maximum_tool_calls:
            raise WorkflowLimitError(
                ToolErrorCode.WORKFLOW_LIMIT_EXCEEDED, "Maximum total tool calls reached"
            )
        caps = {
            "search_topic_evidence": self.limits.maximum_search_calls,
            "grounded_analysis": self.limits.maximum_generation_calls,
            "generate_training_data_risk_brief": self.limits.maximum_generation_calls,
            "export_validated_report": self.limits.maximum_export_calls,
        }
        if name in caps and self._counts[name] >= caps[name]:
            raise WorkflowLimitError(
                ToolErrorCode.WORKFLOW_LIMIT_EXCEEDED, f"Maximum {name} calls reached"
            )
        fingerprint = sha256(
            f"{name}:{json.dumps(arguments, sort_keys=True, default=str)}".encode()
        ).hexdigest()
        if fingerprint in self._fingerprints:
            raise WorkflowLimitError(
                ToolErrorCode.REPEATED_TOOL_CALL, "Repeated identical tool call detected"
            )
        self._fingerprints.add(fingerprint)
        self._counts[name] += 1

    def record(
        self,
        name: str,
        arguments: dict[str, object],
        duration_ms: float,
        result: ToolResult[Any],
    ) -> None:
        self.calls.append(
            ToolCallRecord(
                sequence=len(self.calls) + 1,
                tool_name=name,
                arguments=_redact(arguments),
                duration_ms=duration_ms,
                success=result.success,
                error_code=result.error_code.value if result.error_code else None,
            )
        )


class PolicyAgentRuntime:
    """One orchestrator with no policy logic beyond deterministic routing."""

    def __init__(
        self,
        tools: DomainTools,
        limits: AgentLimits | None = None,
        trace_writer: LocalTraceWriter | None = None,
    ) -> None:
        self.tools = tools
        self.limits = limits or AgentLimits()
        self.trace_writer = trace_writer or LocalTraceWriter()

    def run(
        self,
        question: str,
        trace_local: bool = False,
        output_name: str | None = None,
        approve_export: bool = False,
        overwrite: bool = False,
    ) -> AgentRunResult:
        run_id = uuid4()
        budget = ToolCallBudget(self.limits)
        guard = check_user_input(question)
        if not guard.allowed:
            result = AgentRunResult(
                run_id=run_id,
                status=WorkflowStatus.REFUSED,
                error_code=guard.error_code,
                message=guard.message,
            )
            self._trace(result, question, trace_local)
            return result
        try:
            assessment_result = self._call(
                budget,
                "assess_question",
                {"question": question},
                lambda: self.tools.assess_question(question),
            )
            assessment = QuestionAssessment.model_validate(assessment_result.data)
            if (
                assessment.scope.status
                in {
                    ScopeStatus.OUT_OF_SCOPE,
                    ScopeStatus.INSUFFICIENT_EVIDENCE,
                }
                or assessment.sufficiency.status is SufficiencyStatus.INSUFFICIENT
            ):
                status = (
                    WorkflowStatus.REFUSED
                    if assessment.scope.status is ScopeStatus.OUT_OF_SCOPE
                    else WorkflowStatus.DEGRADED
                )
                result = AgentRunResult(
                    run_id=run_id,
                    status=status,
                    error_code=(
                        ToolErrorCode.OUT_OF_SCOPE
                        if status is WorkflowStatus.REFUSED
                        else ToolErrorCode.INSUFFICIENT_EVIDENCE
                    ),
                    message=assessment.sufficiency.explanation,
                    tool_calls=budget.calls,
                )
                self._trace(result, question, trace_local)
                return result
            jurisdictions = _jurisdictions(question)
            search_result = self._call(
                budget,
                "search_topic_evidence",
                {"query": question, "jurisdictions": jurisdictions, "top_k": 5},
                lambda: self.tools.search_topic_evidence(question, jurisdictions, 5),
            )
            if not search_result.success:
                raise WorkflowLimitError(
                    search_result.error_code or ToolErrorCode.INTERNAL_ERROR,
                    search_result.error_message or "Evidence search failed",
                )
            generated = self._call(
                budget,
                "grounded_analysis",
                {"question": question, "evidence_budget": 8},
                lambda: self.tools.grounded_analysis(question, 8),
            )
            if not generated.success or generated.data is None:
                result = AgentRunResult(
                    run_id=run_id,
                    status=WorkflowStatus.FAILED,
                    error_code=generated.error_code,
                    message=generated.error_message or "Verified generation failed",
                    tool_calls=budget.calls,
                )
                self._trace(result, question, trace_local)
                return result
            artifact = generated.data
            export = None
            if output_name:
                export_result = self._call(
                    budget,
                    "export_validated_report",
                    {
                        "identifier": artifact.identifier,
                        "format_name": "markdown",
                        "approved_output_name": output_name,
                        "approval": (
                            ApprovalDecision.APPROVED
                            if approve_export
                            else ApprovalDecision.REJECTED
                        ),
                    },
                    lambda: self.tools.export_validated_report(
                        artifact.identifier,
                        "markdown",
                        output_name,
                        ApprovalDecision.APPROVED if approve_export else ApprovalDecision.REJECTED,
                        overwrite,
                    ),
                )
                if not export_result.success:
                    result = AgentRunResult(
                        run_id=run_id,
                        status=WorkflowStatus.FAILED,
                        output=artifact.content,
                        artifact_identifier=artifact.identifier,
                        verification=artifact.verification,
                        tool_calls=budget.calls,
                        evidence_chunk_ids=artifact.evidence_chunk_ids,
                        error_code=export_result.error_code,
                        message=export_result.error_message or "Export failed",
                    )
                    self._trace(result, question, trace_local)
                    return result
                export = export_result.data
            result = AgentRunResult(
                run_id=run_id,
                status=WorkflowStatus.COMPLETED,
                output=artifact.content,
                artifact_identifier=artifact.identifier,
                verification=artifact.verification,
                tool_calls=budget.calls,
                evidence_chunk_ids=artifact.evidence_chunk_ids,
                message="Verified policy analysis completed.",
                export=export,
            )
        except WorkflowLimitError as error:
            result = AgentRunResult(
                run_id=run_id,
                status=WorkflowStatus.LIMIT_EXCEEDED,
                error_code=error.code,
                message=str(error),
                tool_calls=budget.calls,
            )
        self._trace(result, question, trace_local)
        return result

    @staticmethod
    def _call(
        budget: ToolCallBudget,
        name: str,
        arguments: dict[str, object],
        function: Callable[[], ToolResult[Any]],
    ) -> ToolResult[Any]:
        budget.reserve(name, arguments)
        started = perf_counter()
        result = function()
        budget.record(name, arguments, (perf_counter() - started) * 1000, result)
        return result

    def _trace(self, result: AgentRunResult, question: str, enabled: bool) -> None:
        if not enabled:
            return
        trace = WorkflowTrace(
            run_id=result.run_id,
            question_hash=sha256(question.encode()).hexdigest(),
            model_identifier=self.tools.provider.model_identifier,
            tool_calls=result.tool_calls,
            evidence_chunk_ids=result.evidence_chunk_ids,
            verification_status=(
                VerificationStatus.PASSED
                if result.verification and result.verification.passed
                else VerificationStatus.NOT_APPLICABLE
            ),
            refusal_status=result.status,
            total_turns=len(result.tool_calls),
            total_tool_calls=len(result.tool_calls),
        )
        self.trace_writer.write(trace)


def _jurisdictions(question: str) -> list[str]:
    lowered = question.lower()
    cn = "china" in lowered or "中国" in question
    eu = "eu" in lowered or "europe" in lowered or "欧盟" in question
    if cn and not eu:
        return ["CN"]
    if eu and not cn:
        return ["EU"]
    return ["CN", "EU"]


def _redact(arguments: dict[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in arguments.items():
        if any(term in key.lower() for term in ("key", "secret", "token")):
            redacted[key] = "[REDACTED]"
        elif key in {"question", "query"}:
            redacted[f"{key}_hash"] = sha256(str(value).encode()).hexdigest()
        else:
            redacted[key] = value
    return redacted
