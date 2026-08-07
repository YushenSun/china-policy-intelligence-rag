# Grounded Analysis and Citation Verification

Phase 3 is limited to training-data compliance and transparency for generative or general-purpose AI models in China and the EU. It does not provide legal advice or unrestricted chat.

## Evidence policy

- Label 2 is human-reviewed core topic evidence and may support substantive policy claims.
- Label 1 is supporting context and cannot be the sole support for a strong regulatory claim.
- Label 0 is mechanically excluded from the topic evidence store, prompts, and citations.
- Human labels are evidence-quality constraints, not retrieval scores or model confidence.

The selector searches only the curated label-1/2 universe, deduplicates chunks, prioritises core evidence, enforces a configurable budget, and requires core evidence from both CN and EU for comparative answers. Insufficient evidence produces an explicit refusal; partial scope produces a narrower answer with gaps.

## Structured generation

Providers return validated Pydantic models rather than Markdown. Source text is wrapped as untrusted evidence and instructions inside it are explicitly ignored. The optional OpenAI provider reads `OPENAI_API_KEY` from the environment and is not required for tests. The fake provider validates the workflow only.

## Deterministic verification

Every claim is checked independently of the provider. Verification rejects unknown, excluded, unsupplied, missing, excessive, or jurisdiction-mismatched citations; one-sided comparison claims; and strong claims supported only by label-1 evidence. Interpretive claims require a written qualification. This is structural grounding validation, not semantic-entailment or legal-correctness verification.

## Commands

```powershell
python -m china_policy_rag.cli analysis ask `
  --question "What copyright obligations apply to EU GPAI model providers?" `
  --evidence-set data/annotations/phase2_5_topic_relevant.csv `
  --provider fake `
  --format json

python -m china_policy_rag.cli analysis brief `
  --evidence-set data/annotations/phase2_5_topic_relevant.csv `
  --provider fake `
  --output reports/china_eu_training_data_brief.md

python -m china_policy_rag.cli analysis verify `
  --analysis-json reports/china_eu_training_data_brief.json `
  --evidence-set data/annotations/phase2_5_topic_relevant.csv
```

The JSON model is canonical. Markdown is rendered only after deterministic verification.
