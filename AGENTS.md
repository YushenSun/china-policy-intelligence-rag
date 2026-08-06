# Repository Guidance

## Purpose

This repository is the Phase 0 foundation for the China Policy Intelligence RAG Prototype. The long-term project is intended to support evidence-based analysis of Chinese and English policy and industry documents.

## Current Status

Phase 1 implements local TXT, Markdown, HTML, and text-based PDF ingestion; YAML metadata validation; conservative normalization; deterministic chunking; JSONL serialization; and an offline CLI. Retrieval, RAG, agents, MCP integration, evaluation, and risk-brief generation remain roadmap items.

## Development Commands

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m china_policy_rag.cli ingest --input-dir data/raw --manifest data/raw/manifest.yaml --output-dir data/processed
```

Use `python -m ruff format .` to apply formatting.

## Coding Conventions

- Target Python 3.11+ and use explicit type annotations.
- Prefer small, clear modules and Pydantic models over premature abstractions.
- Keep documentation and code comments in professional English.
- Add or update deterministic, offline tests whenever behaviour changes.
- Run the test, lint, format, and type-check commands before handing off work.

## Accuracy, Security, and Scope

- Never fabricate source documents, citations, API responses, credentials, benchmark results, or evaluation outcomes.
- Never commit secrets. Use environment variables and `.env.example` placeholders only.
- Keep future external services behind clear interfaces so local tests remain offline.
- Do not download sources, implement OCR, or add retrieval/model dependencies during Phase 1 work.
- State assumptions, limitations, and unimplemented work plainly.
- Complete only the phase and scope requested; do not begin a later phase without an explicit request.
