# China Policy Intelligence RAG Prototype

## Overview

This project is an offline, source-traceable research prototype for Chinese and English policy documents. Its public demonstration corpus focuses on training-data compliance and transparency for generative and general-purpose AI models in China and the European Union. It converts authorised local sources into provenance-preserving chunks, retrieves ranked evidence, and records reproducible synthetic evaluation artefacts for future grounded-analysis work.

## Problem Statement

Policy signals are often distributed across long, multilingual documents. Analysts need a disciplined way to preserve source context, retrieve relevant evidence, and communicate uncertainty when producing decision-support material.

## Intended Users

The intended users are strategy, policy, market-intelligence, and risk-analysis professionals who need transparent evidence trails rather than unsupported summaries.

## Planned Outputs

- Source-grounded answers with citations
- Retrieval evidence records
- Structured policy and sector risk briefs
- Explicit assumptions and uncertainty statements

## Current Status

**Phase 2 implements an offline ingestion and evidence-retrieval foundation.** It supports TXT, Markdown, HTML, and text-based PDF inputs; YAML metadata validation; deterministic identifiers; conservative bilingual normalization; deterministic chunking; persistent lexical and vector indexes; hybrid retrieval; metadata filters; source-traceable evidence output; and synthetic offline evaluation.

The public Phase 2.5 corpus deliberately excludes geopolitical-security strategy documents. Its human-labelled topic evidence set contains 20 relevant unique chunks, including 9 core chunks. These labels are topic-level evidence judgements, not a query-level retrieval benchmark. See [the topic scope](data/phase2_5/TOPIC_SCOPE.md) and [the corpus guide](docs/phase2_5_corpus.md).

Persistent lexical retrieval, optional local semantic retrieval, deterministic hybrid fusion, metadata filters, evidence output, and synthetic offline evaluation are available. LLM-generated answers, citation verification against generated claims, risk briefs, agents, MCP, web collection, OCR, and production deployment are not implemented.

## Planned Architecture

The architecture separates local document handling, metadata validation, retrieval, answer generation, citation verification, risk-brief generation, and evaluation. See [the architecture proposal](docs/architecture.md), [ingestion guide](docs/ingestion.md), [retrieval guide](docs/retrieval.md), and [evaluation guide](docs/evaluation.md). Answer generation remains planned future work.

## Installation

Python 3.11 or newer is required.

```powershell
python -m pip install -e ".[dev]"
```

For local ingestion, create a private `data/raw/manifest.yaml` from `data/raw/manifest.example.yaml` and use only authorised local files. No external service is required.

```powershell
python -m china_policy_rag.cli ingest --input-dir data/raw --manifest data/raw/manifest.yaml --output-dir data/processed
```

## Developer Commands

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src
```

To apply formatting:

```powershell
python -m ruff format .
```

## Roadmap

1. **Phase 0:** repository foundation, configuration, and typed models.
2. **Phase 1:** local ingestion, metadata validation, provenance-preserving text preparation, and deterministic chunking.
3. **Phase 2 (current):** persistent hybrid retrieval, metadata filtering, evidence bundles, and synthetic offline evaluation.
4. **Phase 3:** source-grounded answer and structured risk-brief workflows.
5. **Phase 4:** optional agent and MCP extensions, subject to explicit scope and security review.

## Limitations

The pipeline accepts only local text, Markdown, HTML, and text-based PDFs. It does not perform OCR or fetch sources. The default offline embedding provider is deterministic but is not a semantic-quality model; sentence-transformers is optional and requires a locally available model. Character-based chunking is deterministic but not tokenizer-aware. Retrieval results are evidence candidates, not generated answers or verified facts.

## Data Provenance Principles

- Retain stable source identifiers, issuer, publication date, jurisdiction, language, URLs or local paths, and evidence locations.
- Do not fabricate documents, quotations, citations, or evaluation results.
- Record assumptions and uncertainty alongside analytical outputs.
- Use only data whose collection, storage, and use are authorised for the intended context.

## Security and Privacy Principles

- Do not commit API keys, credentials, or private documents.
- Store future secrets in environment variables or an approved secret manager.
- Keep external integrations behind interfaces and avoid making them prerequisites for local tests.
- Apply appropriate access controls and retention rules before handling sensitive source material.
