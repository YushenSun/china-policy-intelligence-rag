# Repository Guidance

## Purpose

This repository is the Phase 3 China Policy Intelligence RAG Prototype. Its public MVP supports evidence-based analysis of a narrow China–EU training-data policy topic.

## Current Status

Phase 3 implements ingestion, retrieval, human-curated topic evidence, structured grounded analysis, deterministic citation verification, refusal/degradation, and a structured risk brief. Agents, MCP, monitoring, legal advice, frontend work, and deployment remain out of scope.

## Development Commands

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m china_policy_rag.cli ingest --input-dir data/raw --manifest data/raw/manifest.yaml --output-dir data/processed
python -m china_policy_rag.cli analysis ask --question "What training-data transparency is required?" --evidence-set data/annotations/phase2_5_topic_relevant.csv --provider fake --format markdown
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
- Keep topic analysis mechanically limited to human labels 1 and 2; never supply label 0.
- Do not begin Phase 4 or add agents, MCP, monitoring, frontend, or deployment without an explicit request.
- State assumptions, limitations, and unimplemented work plainly.
- Complete only the phase and scope requested; do not begin a later phase without an explicit request.
