# Retrieval Evaluation

`evaluate` runs Recall@k, Precision@k, MRR, and Hit Rate@k against a YAML benchmark explicitly marked `fixture_only: true`. These synthetic results validate plumbing only and are not retrieval-quality claims.

```powershell
python -m china_policy_rag.cli evaluate --index-dir data/indexes/default --benchmark data/evaluation/benchmark.yaml --modes lexical semantic hybrid --k 1 3 5 --output data/evaluation/results.json
```

Each benchmark entry requires `query_id`, `query_text`, and chunk IDs judged relevant. For future evaluation, replace synthetic fixtures with authorised, human-labelled relevance data and report its provenance separately.
