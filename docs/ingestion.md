# Local Ingestion Guide

## Scope

Phase 1 ingests authorised local `.txt`, `.md`, `.html`, `.htm`, and text-based `.pdf` files. It does not download sources, execute page scripts, follow links, perform OCR, or support scanned/image-only PDFs.

## Manifest

Create a private `data/raw/manifest.yaml` using [manifest.example.yaml](../data/raw/manifest.example.yaml) as a schema reference. Each `sources` entry requires a relative `file_path`, title, issuer, publication date, jurisdiction, language (`zh` or `en`), and document type. Optional metadata includes sector tags, source URL, access date, and notes.

Paths must remain within the raw-data directory. Duplicate paths, missing files, unknown metadata keys, and unsupported extensions are rejected.

## Run Ingestion

```powershell
python -m china_policy_rag.cli ingest `
  --input-dir data/raw `
  --manifest data/raw/manifest.yaml `
  --output-dir data/processed
```

Use `--overwrite` only when replacing existing generated artifacts. Use `--fail-on-unlisted-files` to make every supported local source require a manifest entry.

## Outputs

- `documents.jsonl`: validated `PolicyDocument` records, including local path, content hash, and parser metadata.
- `chunks.jsonl`: validated `SourceChunk` records with deterministic IDs, source hash, text offsets, and available page or section references.
- `ingestion_report.json`: run timestamps, counts, warnings, per-document status, configuration, and output paths. It does not contain full document text.

## Stable IDs

Document IDs use UUIDv5 over an identifier-version string, normalized relative path, and source-file SHA-256. Chunk IDs use UUIDv5 over the document ID, chunk index, normalized chunk text, and chunking-version string. Re-running unchanged input with unchanged configuration produces the same IDs.

## Limitations and Provenance

PDF extraction is limited to selectable text; a textless PDF is rejected with an OCR limitation message. Chunking uses characters rather than a language-model tokenizer. Preserve the original local file, its declared metadata, and generated source hash. Only ingest documents you are authorised to store and analyse; do not commit private files, private manifests, or credentials.
