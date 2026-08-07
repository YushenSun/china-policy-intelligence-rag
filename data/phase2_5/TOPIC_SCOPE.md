# Topic Scope: Training-Data Compliance and Transparency for Generative AI Models

## Research question

How do China's interim rules for generative AI services and the EU AI Act frame compliance and transparency duties for the training data of generative or general-purpose AI models?

## In scope

- Lawful data sources, intellectual-property and personal-information requirements.
- Data quality, annotation and safety-management requirements.
- Training-data and model-documentation disclosure obligations.
- The EU AI Act duties for general-purpose AI models, including copyright, text-and-data-mining reservations, training-content summaries, technical documentation, and fine-tuning data records.

## Out of scope

- General AI industry policy, broad digitalisation, investment policy, and semiconductor policy.
- Geopolitical competition, national-security strategy, espionage, and country-threat characterisations.
- Claim generation, legal advice, and retrieval-quality metrics.

## Annotation method

The human annotation in `data/annotations/phase2_5_topic_annotated.csv` is topic-level. A repeated `chunk_id` receives one consistent label regardless of the retrieval query that surfaced it.

- **2 — Core evidence:** directly supports the research question.
- **1 — Supporting evidence:** clearly relevant context or conditions, but not sufficient on its own.
- **0 — Not sufficient:** does not support the focused topic.

The materialized artefacts contain 20 unique relevant chunks (labels 1 and 2), including 9 unique core chunks. They are a curated evidence set, not a query-level gold benchmark; do not use them to report Recall@k, MRR, Precision@k, or other retrieval metrics.
