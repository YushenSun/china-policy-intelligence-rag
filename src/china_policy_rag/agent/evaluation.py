"""Deterministic Agent Workflow Evaluation for routing and tool behaviour."""

import json
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from china_policy_rag.analysis.models import GroundedAnalysis

from .models import WorkflowStatus
from .runtime import PolicyAgentRuntime


class WorkflowCase(BaseModel):
    case_id: str = Field(pattern=r"^AW[0-9]{2,}$")
    input: str = Field(min_length=1, max_length=2_000)
    expected_scope_status: str
    allowed_tools: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    expected_final_status: WorkflowStatus
    maximum_tool_calls: int = Field(ge=0, le=10)
    notes: str = ""


class CaseEvaluation(BaseModel):
    case_id: str
    actual_status: WorkflowStatus
    tool_names: list[str]
    routing_correct: bool
    refusal_correct: bool
    required_tools_present: bool
    forbidden_tools_absent: bool
    within_tool_limit: bool
    verification_passed: bool
    citation_valid: bool
    jurisdiction_coverage: bool
    repeated_call_detected: bool


class WorkflowMetrics(BaseModel):
    case_count: int
    scope_routing_accuracy: float
    correct_refusal_rate: float
    required_tool_use_rate: float
    forbidden_tool_call_rate: float
    verification_pass_rate: float
    citation_validity_rate: float
    average_tool_calls: float
    repeated_call_rate: float
    evidence_jurisdiction_coverage: float
    workflow_completion_rate: float


class WorkflowEvaluation(BaseModel):
    title: str = "Agent Workflow Evaluation"
    cases: list[CaseEvaluation]
    metrics: WorkflowMetrics


def load_workflow_cases(path: Path) -> list[WorkflowCase]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("Workflow case YAML must contain a cases list")
    cases = [WorkflowCase.model_validate(item) for item in payload["cases"]]
    if len(cases) < 15:
        raise ValueError("At least 15 human-authored workflow cases are required")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Workflow case IDs must be unique")
    return cases


def evaluate_workflows(
    runtime: PolicyAgentRuntime, cases: list[WorkflowCase]
) -> WorkflowEvaluation:
    results: list[CaseEvaluation] = []
    for case in cases:
        run = runtime.run(case.input)
        names = [item.tool_name for item in run.tool_calls]
        expected_refusal = case.expected_final_status in {
            WorkflowStatus.REFUSED,
            WorkflowStatus.DEGRADED,
        }
        actual_refusal = run.status in {WorkflowStatus.REFUSED, WorkflowStatus.DEGRADED}
        content_scope = (
            run.output.scope_status.value if isinstance(run.output, GroundedAnalysis) else None
        )
        if case.expected_scope_status == "CN-EU":
            routing_correct = run.status is WorkflowStatus.COMPLETED and content_scope == "IN_SCOPE"
        elif case.expected_scope_status == "IN_SCOPE":
            routing_correct = content_scope == "IN_SCOPE"
        elif case.expected_scope_status == "OUT_OF_SCOPE":
            routing_correct = run.status is WorkflowStatus.REFUSED
        else:
            routing_correct = run.status is WorkflowStatus.DEGRADED
        jurisdictions = {
            evidence.jurisdiction
            for evidence_id in run.evidence_chunk_ids
            if (evidence := runtime.tools.store.get(evidence_id)) is not None
        }
        comparison = "CN-EU" in case.expected_scope_status or "comparison" in case.notes.lower()
        results.append(
            CaseEvaluation(
                case_id=case.case_id,
                actual_status=run.status,
                tool_names=names,
                routing_correct=routing_correct,
                refusal_correct=expected_refusal == actual_refusal,
                required_tools_present=set(case.required_tools).issubset(names),
                forbidden_tools_absent=(
                    not set(case.forbidden_tools).intersection(names)
                    and (not names or set(names).issubset(case.allowed_tools))
                ),
                within_tool_limit=len(names) <= case.maximum_tool_calls,
                verification_passed=bool(run.verification and run.verification.passed)
                or actual_refusal,
                citation_valid=bool(run.verification and run.verification.passed) or actual_refusal,
                jurisdiction_coverage=not comparison or {"CN", "EU"}.issubset(jurisdictions),
                repeated_call_detected=len(
                    {
                        (
                            call.tool_name,
                            json.dumps(call.arguments, sort_keys=True, default=str),
                        )
                        for call in run.tool_calls
                    }
                )
                != len(run.tool_calls),
            )
        )
    count = len(results)
    calls = sum(len(item.tool_names) for item in results)
    metrics = WorkflowMetrics(
        case_count=count,
        scope_routing_accuracy=_rate(results, "routing_correct"),
        correct_refusal_rate=_rate(results, "refusal_correct"),
        required_tool_use_rate=_rate(results, "required_tools_present"),
        forbidden_tool_call_rate=1.0 - _rate(results, "forbidden_tools_absent"),
        verification_pass_rate=_rate(results, "verification_passed"),
        citation_validity_rate=_rate(results, "citation_valid"),
        average_tool_calls=calls / count,
        repeated_call_rate=sum(item.repeated_call_detected for item in results) / count,
        evidence_jurisdiction_coverage=_rate(results, "jurisdiction_coverage"),
        workflow_completion_rate=sum(
            item.actual_status
            in {WorkflowStatus.COMPLETED, WorkflowStatus.REFUSED, WorkflowStatus.DEGRADED}
            for item in results
        )
        / count,
    )
    return WorkflowEvaluation(cases=results, metrics=metrics)


def write_workflow_evaluation(path: Path, evaluation: WorkflowEvaluation) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(evaluation.model_dump(mode="json"), indent=2) + "\n"
    path.write_text(rendered, encoding="utf-8")


def _rate(items: list[CaseEvaluation], field: str) -> float:
    return sum(bool(getattr(item, field)) for item in items) / len(items)
