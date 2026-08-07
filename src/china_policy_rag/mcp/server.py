"""Optional local stdio MCP server over the read-only domain-tool adapter."""

import json
from importlib import import_module
from typing import Any

from china_policy_rag.agent.tools import DomainTools, load_topic_store
from china_policy_rag.analysis.generation import DeterministicFakeLLM

from .tools import ReadOnlyMCPAdapter


def create_server() -> Any:
    try:
        fastmcp = import_module("mcp.server.fastmcp")
    except ImportError as error:
        raise RuntimeError("Install the optional `.[mcp]` dependency") from error
    adapter = ReadOnlyMCPAdapter(DomainTools(load_topic_store(), DeterministicFakeLLM()))
    server = fastmcp.FastMCP("china-policy-intelligence-read-only")

    def render(name: str, arguments: dict[str, object] | None = None) -> str:
        return json.dumps(adapter.call(name, arguments).model_dump(mode="json"))

    def policy_get_scope() -> str:
        """Return the exact supported topic and evidence boundary."""
        return render("policy_get_scope")

    def policy_search_evidence(
        query: str,
        jurisdictions: list[str] | None = None,
        top_k: int = 5,
        include_supporting: bool = True,
        evidence_budget: int = 8,
    ) -> str:
        """Search only human-approved topic evidence with bounded results."""
        return render(
            "policy_search_evidence",
            {
                "query": query,
                "jurisdictions": jurisdictions or ["CN", "EU"],
                "top_k": top_k,
                "include_supporting": include_supporting,
                "evidence_budget": evidence_budget,
            },
        )

    def policy_inspect_evidence(chunk_id: str) -> str:
        """Inspect one permitted evidence UUID; unknown and label-0 IDs fail."""
        return render("policy_inspect_evidence", {"chunk_id": chunk_id})

    def policy_assess_question(question: str) -> str:
        """Assess scope and evidence sufficiency without model generation."""
        return render("policy_assess_question", {"question": question})

    def policy_list_evidence_gaps() -> str:
        """List deterministic known gaps in the curated evidence set."""
        return render("policy_list_evidence_gaps")

    def policy_verify_analysis(
        payload: dict[str, object] | None = None, identifier: str | None = None
    ) -> str:
        """Verify structured JSON or a safe in-process artifact identifier."""
        return render("policy_verify_analysis", {"payload": payload, "identifier": identifier})

    for function in (
        policy_get_scope,
        policy_search_evidence,
        policy_inspect_evidence,
        policy_assess_question,
        policy_list_evidence_gaps,
        policy_verify_analysis,
    ):
        server.tool()(function)
    return server


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
