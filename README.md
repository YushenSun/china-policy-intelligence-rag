# China Policy Intelligence RAG Prototype

## Overview

This project is a planned evidence-based research tool for analysing Chinese and English policy and industry documents. Its purpose is to make strategic analysis more traceable by linking conclusions to identifiable source evidence.

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

**Phase 0 provides only repository scaffolding and typed domain models.** Retrieval, RAG, document ingestion, agents, MCP integrations, and risk-brief generation are not implemented.

## Planned Architecture

The proposed architecture separates document handling, metadata validation, retrieval, answer generation, citation verification, risk-brief generation, and evaluation. See [the architecture proposal](docs/architecture.md). All pipeline components are planned future work; only configuration and domain-model layers exist today.

## Installation

Python 3.11 or newer is required.

```powershell
python -m pip install -e ".[dev]"
```

For future integrations, copy `.env.example` to `.env` and populate only the settings needed by that integration. No external service is required for Phase 0.

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

1. **Phase 0 (current):** repository foundation, configuration, and typed models.
2. **Phase 1:** local document and metadata ingestion with provenance validation.
3. **Phase 2:** offline retrieval baselines and reproducible evaluation fixtures.
4. **Phase 3:** source-grounded answer and structured risk-brief workflows.
5. **Phase 4:** optional agent and MCP extensions, subject to explicit scope and security review.

## Limitations

This repository does not yet ingest documents, retrieve evidence, call language models, generate answers, or produce risk briefs. The models define contracts for future work but are not evidence of operational capabilities or quality.

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
