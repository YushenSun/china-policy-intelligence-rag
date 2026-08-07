# Phase 2.5 Retrieval Annotation Guide

## Purpose

Create a small, defensible human-labelled retrieval benchmark for the China Policy Intelligence RAG Prototype.

The benchmark is for retrieval evaluation only. It is not a claim that the system can produce legally authoritative advice or complete geopolitical analysis.

## Inputs

- `manifest.yaml`: authoritative-source metadata.
- `query_seeds.yaml`: 19 bilingual, cross-language and comparative queries.
- Candidate chunks exported from lexical, semantic and hybrid retrieval.

## Non-negotiable rule

Do not let an LLM or Codex assign the final relevance labels. Models may format candidate files, but a human must read the source chunk and decide the label.

## Relevance scale

Use three grades:

- **2 — Answer-bearing:** The chunk directly contains a provision, target, definition, obligation, restriction, policy measure or strategic statement needed to answer the query.
- **1 — Supporting context:** The chunk is clearly related and useful for interpretation, but cannot answer the core question by itself.
- **0 — Not relevant:** The chunk does not materially help answer the query.

For binary metrics such as Recall@k, Precision@k, MRR and Hit Rate@k, treat grade **2** as relevant.
For nDCG, retain both grades 2 and 1 if the evaluation implementation supports graded relevance.

## Query-specific rules

### Direct queries

At least one grade-2 chunk must contain the explicit answer. Do not label a broad introduction as grade 2 merely because it names the policy.

### Cross-language queries

Judge relevance by meaning, not language. An English query may have a Chinese answer-bearing chunk and vice versa.

### Parallel-document queries

Official translations may both be relevant. Prefer the version matching the query language as the primary grade-2 evidence, but label an equivalent parallel passage as grade 2 when it contains the same answer.

### Comparative queries

A valid benchmark must include grade-2 evidence from **each required side** of the comparison. For Q21, this means China and the EU.

## Annotation procedure

1. Build the real corpus and index.
2. For each query, retrieve at least top 10 results from lexical, semantic and hybrid modes.
3. Merge candidates by chunk ID, preserving the best rank from each mode.
4. Add any obvious answer-bearing chunks from the expected source files if retrieval missed them.
5. Read each candidate in context. Open the source page or adjacent chunks when needed.
6. Assign grade 0, 1 or 2.
7. Record a short note for every grade-2 label.
8. Review all grade-2 labels a second time after at least one hour or on the next day.
9. Compile the evaluator benchmark using grade-2 chunk IDs.
10. Keep the annotation sheet under version control.

## Quality controls

- Do not select duplicate overlapping chunks as separate gold evidence unless each contains distinct required information.
- Prefer the smallest chunk that fully supports the answer.
- Preserve page or section references.
- Flag parser corruption, broken Chinese text, missing tables or lost headings.
- Flag queries that cannot be answered from the selected corpus.
- Do not change a query after seeing results without recording a version change.
- Do not report metrics from an unreviewed benchmark.

## Recommended metrics

Report separately for lexical, semantic and hybrid retrieval:

- Recall@5 and Recall@10
- Precision@5
- MRR
- Hit Rate@5
- nDCG@10 if graded labels are supported

Also report:

- direct-query performance
- cross-language-query performance
- comparative-query performance
- Chinese-query and English-query performance

## Minimum benchmark acceptance

Before using results in a portfolio:

- all 15 queries reviewed;
- every direct query has at least one grade-2 chunk;
- Q21 has grade-2 evidence from both sides;
- no unresolved parser corruption in gold chunks;
- benchmark file clearly marked as human-labelled;
- results reproducible from a clean index build.

## Claims allowed after completion

Allowed:

> Evaluated lexical, semantic and hybrid retrieval on a small human-labelled bilingual policy benchmark.

Not allowed without evidence:

> Achieved production-grade policy intelligence.  
> The system understands Chinese policy.  
> The benchmark proves legal or geopolitical accuracy.
