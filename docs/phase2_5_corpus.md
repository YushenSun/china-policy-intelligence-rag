# Phase 2.5 Authoritative Corpus

The repository includes a fixed 9-source public-portfolio allowlist in `data/phase2_5/source_catalog.yaml`. It covers general AI, data, industrial, and investment regulation; it excludes geopolitical-security strategy documents. It is not a general scraper. Downloaded source files remain under ignored `data/raw/phase2_5`; metadata, query seeds, and annotation instructions are versioned separately.

Run the reviewed downloader in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_corpus.ps1 -ProjectRoot $PWD
```

If a source fails, use its exact `download_url` from `data/phase2_5/source_catalog.yaml`, save it to the matching `file_path` under `data/raw`, then rerun validation:

```powershell
python -m china_policy_rag.cli corpus validate --raw-dir data/raw --manifest data/raw/phase2_5/manifest.yaml --output data/processed/phase2_5_corpus_validation.json
```

After all files validate, ingest with the same manifest:

```powershell
python -m china_policy_rag.cli ingest --input-dir data/raw --manifest data/raw/phase2_5/manifest.yaml --output-dir data/processed/phase2_5 --overwrite
```

PDF files are supported when they contain extractable text; OCR is not implemented. Build the real multilingual E5 index after installing the optional local dependency and downloading the model once:

```powershell
python -m pip install -e ".[semantic]"
python -m china_policy_rag.cli index build --chunks data/processed/phase2_5/chunks.jsonl --index-dir data/indexes/phase2_5_e5 --embedding-provider sentence-transformers --embedding-model intfloat/multilingual-e5-base --overwrite
python -m china_policy_rag.cli annotate export --index-dir data/indexes/phase2_5_e5 --query-seeds data/phase2_5/query_seeds.yaml --output data/annotations/phase2_5_candidates.csv --top-k 10 --embedding-provider sentence-transformers --embedding-model intfloat/multilingual-e5-base
```

Candidate CSV files use UTF-8 with BOM and have blank `human_label` and `reviewer_note` fields. Human reviewers, rather than Codex or an LLM, must assign the relevance grades.

For a focused research topic, materialize human topic-level labels into deduplicated evidence artefacts:

```powershell
python -m china_policy_rag.cli annotate materialize-topic `
  --annotated-csv data/annotations/phase2_5_topic_annotated.csv `
  --relevant-output data/annotations/phase2_5_topic_relevant.csv `
  --core-output data/annotations/phase2_5_topic_core.csv `
  --summary-output data/annotations/phase2_5_topic_summary.json `
  --topic "Training-data compliance and transparency for generative AI models"
```

This validates that repeated chunk IDs have a consistent human label, requires reviewer notes for core evidence, and writes unique chunks only. The result is a topic evidence set, not a retrieval evaluation benchmark.
