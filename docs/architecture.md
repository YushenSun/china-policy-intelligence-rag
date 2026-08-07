# Proposed Architecture

## Implementation Status

Phase 3 implements ingestion, persistent retrieval, human-curated topic evidence, bounded evidence selection, structured generation, deterministic claim-level citation verification, refusal/degradation, and a structured risk brief. Optional provider access remains isolated and is not required for offline operation.

## Design Principles

- Preserve traceable source metadata and evidence locations throughout the workflow.
- Keep provider-specific integrations behind interfaces.
- Separate retrieval, generation, citation checking, and evaluation for independent testing.
- Treat uncertainty as an explicit output, not an implicit confidence claim.

## Proposed Component Boundaries

| Component | Status | Responsibility |
| --- | --- | --- |
| Configuration layer | Implemented | Read local defaults and future provider settings from the environment. |
| Domain models | Implemented | Validate shared records for sources, retrieval, citations, answers, and risk briefs. |
| Document ingestion | Implemented | Import authorised local TXT, Markdown, HTML, and text-based PDF documents. |
| Text normalization | Implemented | Conservatively normalize Unicode and whitespace while retaining paragraph boundaries. |
| Metadata validation | Implemented | Validate a YAML manifest and local paths before ingestion. |
| Chunking | Implemented | Create deterministic paragraph-aware, evidence-addressable text segments. |
| JSONL serialization | Implemented | Persist processed documents, chunks, and a machine-readable report locally. |
| Storage | Implemented | Persist local lexical/vector indexes and versioned evidence artefacts. |
| Embedding provider | Implemented | Use deterministic tests or optional local sentence-transformers. |
| Lexical and vector retrieval | Implemented | Retrieve candidate evidence using complementary methods. |
| Reranking | Planned | Order retrieved evidence for a specific question. |
| Topic evidence store | Implemented | Load labels 1/2 with exact provenance and mechanically exclude label 0. |
| Evidence selection and sufficiency | Implemented | Enforce evidence budgets, core preference, scope, and jurisdiction coverage. |
| Grounded answer generation | Implemented | Produce validated structured data before rendering. |
| Citation verification | Implemented | Check citations, labels, provenance, jurisdiction, and support rules. |
| Structured risk-brief generation | Implemented | Build a bounded China–EU training-data risk brief. |
| Evaluation | Implemented | Run synthetic retrieval plumbing tests and offline grounding tests. |
| Optional agent and MCP extensions | Planned | Add bounded orchestration only after core workflows are validated. |

```mermaid
flowchart LR
    A["Authorised local documents"] --> B["Implemented: ingestion"]
    B --> C["Implemented: normalization and metadata validation"]
    C --> D["Implemented: chunking and JSONL artifacts"]
    D --> E["Implemented: lexical and vector retrieval"]
    E --> L["Implemented: human-curated topic evidence"]
    L --> F["Implemented: bounded evidence selection"]
    F --> G["Implemented: structured grounded generation"]
    G --> H["Implemented: deterministic citation verification"]
    H --> I["Implemented: structured risk brief and rendering"]
    D --> J["Implemented: offline evaluation"]
    H --> J
    K["Implemented: configuration and domain models"] -. contracts .-> B
    K -. contracts .-> G
    K -. contracts .-> I
```

## Future Extension Notes

An optional agent or MCP layer may coordinate approved tools in a later phase, but it must not obscure evidence provenance or bypass citation verification. It should remain separate from the core domain and retrieval interfaces.
