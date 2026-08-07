# Project Specification: China Policy Intelligence RAG Prototype

## User Problem

Strategic analysts need a reliable way to examine multilingual policy and industry material while preserving the evidence and uncertainty behind each conclusion. Manual workflows make it difficult to keep source metadata, quoted context, and structured risk reasoning consistent.

## Scope

The final MVP is planned to accept Chinese and English documents, retain traceable source metadata, retrieve relevant evidence, produce source-grounded answers, and create structured risk briefs with explicit uncertainty and reproducible evaluation.

Phase 4 adds auditable single-agent orchestration over the Phase 3 services, narrow domain tools, local traces, approval-gated export, read-only MCP, and reproducible workflow evaluation. It does not expand the evidence corpus or weaken citation verification.

## Current Non-Goals

The MVP does not implement web scraping, OCR, autonomous research agents, Internet-facing MCP, monitoring, legal advice, unrestricted chat, frontend work, deployment, or query-level benchmark claims from topic labels.

## Functional Requirements

- Ingest authorised Chinese and English policy and industry documents.
- Validate and retain source metadata and provenance.
- Normalize and chunk text while retaining page or section references.
- Support lexical and vector retrieval with inspectable evidence.
- Generate answers grounded in retrieved evidence and attach verifiable citations.
- Generate structured risk briefs identifying affected sectors, opportunities, risks, assumptions, and uncertainty.
- Provide reproducible evaluation datasets, metrics, and run records.

## Non-Functional Requirements

- Python 3.11+ and Windows-compatible local development.
- Typed, modular code with deterministic tests that require no network, credentials, or external services.
- Clear separation between domain logic and external providers.
- Documentation that distinguishes implemented behaviour from plans.
- Secure handling of secrets and authorised data only.

## Success Criteria

For Phase 4, success requires a clean installable package; mechanically bounded evidence; verified outputs; refusal, loop, path, and approval controls; a read-only MCP allowlist; privacy-minimising traces; reproducible offline workflow evaluation; and passing tests, linting, formatting, and type checks.

For the planned MVP, success criteria will be defined with an approved evaluation set and include citation traceability, groundedness review, multilingual coverage, structured-output validity, and reproducible evaluation runs. No performance target is asserted before that evaluation is designed and conducted.

## Evaluation Approach

Retrieval evaluation remains separate from the human-authored Agent Workflow Evaluation. Phase 4 measures scope routing, refusals, required/forbidden tool use, verification, citation validity, call counts, repeated calls, jurisdiction coverage, and workflow completion. These deterministic cases test behaviour rather than claiming general AI quality. Semantic and legal-quality review still requires qualified humans.

## Risk Register

| Risk | Potential impact | Planned mitigation |
| --- | --- | --- |
| Incorrect or missing provenance | Unsupported analysis | Enforce source metadata and citation validation |
| Hallucinated or weakly grounded outputs | Misleading decisions | Require evidence locations and citation verification |
| Translation or multilingual ambiguity | Misinterpretation | Retain source language and original evidence context |
| Sensitive or unauthorised data | Privacy or legal exposure | Use authorised sources, access controls, and retention rules |
| Provider changes or outages | Unreliable integrations | Isolate external providers behind interfaces |
| Irreproducible evaluation | Untrustworthy comparisons | Version datasets, settings, and evaluation artifacts |

## Phased Roadmap

1. **Phase 0:** establish repository standards, configuration, models, and offline tests.
2. **Phase 1:** build local ingestion, metadata validation, and provenance-preserving text preparation.
3. **Phase 2:** introduce retrieval baselines and evaluation fixtures.
4. **Phase 3:** add grounded answer and risk-brief workflows with citation checks.
5. **Phase 4 (current):** add bounded orchestration, MCP interoperability, tracing, and tool-use evaluation.
