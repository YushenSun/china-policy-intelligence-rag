"""Stable read-only MCP tool registry delegating to the normal domain tools."""

from typing import Any

from pydantic import ValidationError

from china_policy_rag.agent.models import ToolErrorCode, ToolResult
from china_policy_rag.agent.tools import DomainTools

from .schemas import (
    AssessQuestionInput,
    InspectEvidenceInput,
    SearchEvidenceInput,
    VerifyAnalysisInput,
)

READ_ONLY_TOOL_NAMES = (
    "policy_get_scope",
    "policy_search_evidence",
    "policy_inspect_evidence",
    "policy_assess_question",
    "policy_list_evidence_gaps",
    "policy_verify_analysis",
)


class ReadOnlyMCPAdapter:
    def __init__(self, domain_tools: DomainTools) -> None:
        self.domain_tools = domain_tools

    def list_tools(self) -> list[str]:
        return list(READ_ONLY_TOOL_NAMES)

    def call(self, name: str, arguments: dict[str, object] | None = None) -> ToolResult[Any]:
        args = arguments or {}
        try:
            if name == "policy_get_scope":
                if args:
                    return _invalid("policy_get_scope takes no arguments")
                return self.domain_tools.get_topic_scope()
            if name == "policy_search_evidence":
                search_input = SearchEvidenceInput.model_validate(args)
                return self.domain_tools.search_topic_evidence(**search_input.model_dump())
            if name == "policy_inspect_evidence":
                inspect_input = InspectEvidenceInput.model_validate(args)
                return self.domain_tools.inspect_evidence(inspect_input.chunk_id)
            if name == "policy_assess_question":
                assess_input = AssessQuestionInput.model_validate(args)
                return self.domain_tools.assess_question(assess_input.question)
            if name == "policy_list_evidence_gaps":
                if args:
                    return _invalid("policy_list_evidence_gaps takes no arguments")
                return self.domain_tools.list_evidence_gaps()
            if name == "policy_verify_analysis":
                verify_input = VerifyAnalysisInput.model_validate(args)
                return self.domain_tools.verify_analysis(
                    verify_input.payload, verify_input.identifier
                )
        except ValidationError as error:
            return _invalid(str(error))
        return _invalid("Unknown or non-read-only MCP tool")


def _invalid(message: str) -> ToolResult[Any]:
    return ToolResult(
        success=False,
        error_code=ToolErrorCode.INVALID_ARGUMENT,
        error_message=message,
    )
