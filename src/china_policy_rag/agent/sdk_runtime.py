"""Optional OpenAI Agents SDK adapter; imported and invoked only on explicit request."""

from importlib import import_module
from typing import Any

from .guardrails import check_user_input
from .policy_agent import POLICY_AGENT_INSTRUCTIONS
from .tools import DomainTools


class OpenAIAgentsSDKRuntime:
    """Thin optional adapter over the same bounded domain-tool implementation."""

    def __init__(
        self,
        tools: DomainTools,
        model: str,
        enable_sdk_tracing: bool = False,
        maximum_turns: int = 8,
    ) -> None:
        if not model.strip():
            raise ValueError("An explicit model is required")
        self.tools = tools
        self.model = model
        self.enable_sdk_tracing = enable_sdk_tracing
        self.maximum_turns = maximum_turns

    def run(self, question: str) -> Any:
        guard = check_user_input(question)
        if not guard.allowed:
            raise ValueError(guard.message)
        sdk, agent = self.build_agent()
        return sdk.Runner.run_sync(agent, question, max_turns=self.maximum_turns)

    def build_agent(self) -> tuple[Any, Any]:
        """Build the SDK agent without executing a provider request."""
        try:
            sdk = import_module("agents")
        except ImportError as error:
            raise RuntimeError("Install the optional `.[agent]` dependency") from error
        configure_tracing = getattr(sdk, "set_tracing_disabled", None)
        if callable(configure_tracing):
            configure_tracing(not self.enable_sdk_tracing)
        function_tool = sdk.function_tool
        approved_tools = [
            function_tool(self.tools.get_topic_scope),
            function_tool(self.tools.search_topic_evidence),
            function_tool(self.tools.inspect_evidence),
            function_tool(self.tools.assess_question),
            function_tool(self.tools.grounded_analysis),
            function_tool(self.tools.generate_training_data_risk_brief),
            function_tool(self._verify_registered_analysis),
            function_tool(self.tools.list_evidence_gaps),
        ]
        agent = sdk.Agent(
            name="China-EU Training Data Policy Agent",
            instructions=POLICY_AGENT_INSTRUCTIONS,
            model=self.model,
            tools=approved_tools,
        )
        return sdk, agent

    def _verify_registered_analysis(self, identifier: str) -> str:
        """Verify a previously generated safe artifact identifier; paths are not accepted."""
        return self.tools.verify_analysis(identifier=identifier).model_dump_json()
