# Retrieval and Evidence Selection

Phase 2 persists a portable lexical token index and a NumPy exact cosine-similarity index. Each index records the corpus SHA-256 fingerprint, source JSONL path, schema version, embedding identifier, dimensions, and chunk count. Search refuses a stale corpus fingerprint.

Lexical matching uses simple English alphanumeric terms and individual CJK characters. It does not claim Chinese word segmentation. Semantic mode uses a deterministic hash provider for tests only; it is not a semantic-quality model. `sentence-transformers` is optional and lazy-loaded for local use.

Hybrid mode applies weighted Reciprocal Rank Fusion, not raw-score averaging. Filters use OR within a field, AND across fields, and inclusive date bounds. Exact normalized duplicate chunks are removed conservatively.

Use `index build --embedding-provider deterministic`, `index inspect`, `search --format json|text|markdown`, and `evaluate` via `python -m china_policy_rag.cli`. The optional `sentence-transformers` provider requires `--embedding-model` and the `semantic` extra. Evidence output is retrieved source text and metadata only; it is not a generated answer or verified claim. Never index unauthorised or private source material.
