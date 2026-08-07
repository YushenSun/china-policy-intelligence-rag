# Auditable Agent and MCP Workflow

## Design

Phase 4 uses one deliberately constrained orchestrator. It coordinates narrow domain tools; it does not perform autonomous research, mutate the corpus, or contain policy rules. Scope routing, evidence selection, sufficiency, structured generation, and claim-level verification remain deterministic Phase 3 services. A generated object becomes a successful tool result only after verification passes.

Direct function tools are the low-latency primary interface. The optional local MCP server exposes a smaller read-only subset over the same `DomainTools` instance. It has no shell, network, arbitrary file read/write, annotation editing, or corpus mutation capability. Only stdio transport is supported.

The optional OpenAI Agents SDK adapter is lazy-loaded from the `agent` extra. It uses the current `Agent`, `Runner`, and `function_tool` APIs and does not import the SDK or call a provider at package import time. The deterministic runtime remains the offline test reference. SDK tracing is explicitly configured; external tracing is opt-in because tool arguments and evidence metadata may be sent to the configured provider.

## Trust and guardrail boundaries

- Human labels 1/2 define usable evidence; 149 known label-0 IDs are tracked and rejected.
- Evidence text is untrusted content, never agent instructions.
- User input is bounded to 2,000 characters and rejects filesystem, label-mutation, grounding-bypass, and invented-ID attempts.
- `top_k` and evidence budgets are bounded to 8.
- Substantive output must be a registered, verifier-passed artifact.
- Export accepts only a safe file name, writes below `reports/agent_exports/`, never overwrites by default, and requires `APPROVED`/`--approve-export`.
- Limits are 8 turns, 10 calls, 3 searches, 2 generations, and 1 export; identical calls are rejected.

Agent autonomy is deliberately constrained. Absence in this evidence set does not establish absence of regulation, and outputs are policy intelligence rather than legal advice.

## Tracing

`--trace-local` writes JSON below ignored `reports/traces/`. It records a UUID, UTC timestamp, SHA-256 question hash, model, redacted tool arguments, durations, selected chunk IDs, verification/refusal status, turns, and call count. It does not record environment dumps, credentials, raw questions, or full evidence.

## Security review and residual risks

Controls cover prompt/tool injection, schema validation, path traversal, arbitrary read/write denial, an MCP allowlist, unknown/excluded IDs, API-key non-disclosure, trace minimisation, bounded loops/prompts/results, malformed MCP input, Markdown escaping, and mandatory verification.

Residual risks remain: structural citation checks do not prove semantic entailment or legal correctness; an authorised provider receives selected evidence; optional SDK defects may exist; and a local stdio client inherits its launching user's permissions. MCP is not Internet-facing. Human review remains required before decision use.

## Commands

```powershell
python -m china_policy_rag.cli agent run --question "How do China and the EU differ in training-data transparency?" --provider fake --show-tools --trace-local
python -m china_policy_rag.cli agent run --question "Compare China and EU training-data copyright requirements." --provider fake --output demo.md --approve-export
python -m china_policy_rag.cli agent evaluate --cases data/evaluation/agent_workflows.yaml --provider fake --output reports/agent_evaluation.json
python -m pip install -e ".[mcp]"
python -m china_policy_rag.cli mcp serve --transport stdio
```

For real verified generation, choose either `.[deepseek]` with `DEEPSEEK_API_KEY` or `.[openai]` with `OPENAI_API_KEY`. DeepSeek defaults to `deepseek-v4-flash`; OpenAI requires an explicit model. To experiment with the optional OpenAI Agents SDK adapter, install `.[agent]`; vendor tracing must be deliberately enabled after considering privacy.
