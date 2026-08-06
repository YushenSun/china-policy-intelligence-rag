# Project Specification: China Policy Intelligence RAG Prototype

## User Problem

Strategic analysts need a reliable way to examine multilingual policy and industry material while preserving the evidence and uncertainty behind each conclusion. Manual workflows make it difficult to keep source metadata, quoted context, and structured risk reasoning consistent.

## Scope

The final MVP is planned to accept Chinese and English documents, retain traceable source metadata, retrieve relevant evidence, produce source-grounded answers, and create structured risk briefs with explicit uncertainty and reproducible evaluation.

Phase 0 is limited to repository scaffolding, configuration defaults, typed domain models, documentation, and offline validation tests.

## Non-Goals

Phase 0 does not implement document ingestion, web scraping, PDF parsing, chunking, storage, embeddings, retrieval, reranking, LLM calls, RAG, agents, MCP servers, frontend work, deployment, or benchmark claims.

## Functional Requirements for Later Phases

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

For Phase 0, the success criteria are a clean installable package, validated domain models, environment-based configuration defaults, professional documentation, and passing offline tests, linting, formatting, and type checks.

For the planned MVP, success criteria will be defined with an approved evaluation set and include citation traceability, groundedness review, multilingual coverage, structured-output validity, and reproducible evaluation runs. No performance target is asserted before that evaluation is designed and conducted.

## Planned Evaluation Approach

Future evaluation will use a documented, authorised held-out corpus with known source metadata. It should measure retrieval relevance, citation correctness and completeness, grounded answer quality, risk-brief structure validity, uncertainty calibration, and reproducibility. Human review criteria and automated checks will be versioned with the evaluation data. Results will be reported only after actual runs.

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
5. **Phase 4:** evaluate optional agent and MCP extensions after core workflows are validated.
