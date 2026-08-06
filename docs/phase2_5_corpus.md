# Phase 2.5 Authoritative Corpus

The repository includes a fixed 15-source official allowlist in `data/phase2_5/source_catalog.yaml`. It is not a general scraper. Downloaded source files remain under ignored `data/raw/phase2_5`; metadata, query seeds, and annotation instructions are versioned separately.

Run the reviewed downloader in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_corpus.ps1 -ProjectRoot $PWD
```

If a source fails, use its exact `download_url` from `data/phase2_5/source_catalog.yaml`, save it to the matching `file_path` under `data/raw`, then rerun validation:

```powershell
python -m china_policy_rag.cli corpus validate --raw-dir data/raw --manifest data/raw/phase2_5/manifest.yaml --output data/processed/phase2_5_corpus_validation.json
```

After all files validate, ingest with the same manifest. PDF files are supported when they contain extractable text; OCR is not implemented. E5 indexing uses the optional local `sentence-transformers` provider with `query: ` and `passage: ` prefixes; no model is downloaded by tests.
