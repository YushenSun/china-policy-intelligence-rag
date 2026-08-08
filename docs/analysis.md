# Grounded Analysis and Citation Verification

Phase 3 is limited to training-data compliance and transparency for generative or general-purpose AI models in China and the EU. It does not provide legal advice or unrestricted chat.

## Evidence policy

- Label 2 is human-reviewed core topic evidence and may support substantive policy claims.
- Label 1 is supporting context and cannot be the sole support for a strong regulatory claim.
- Label 0 is mechanically excluded from the topic evidence store, prompts, and citations.
- Human labels are evidence-quality constraints, not retrieval scores or model confidence.

The selector searches only the curated label-1/2 universe, deduplicates chunks, prioritises core evidence, enforces a configurable budget, and requires core evidence from both CN and EU for comparative answers. Insufficient evidence produces an explicit refusal; partial scope produces a narrower answer with gaps.

## Structured generation

Providers return validated Pydantic models rather than Markdown. Source text is wrapped as untrusted evidence and instructions inside it are explicitly ignored. The optional OpenAI Responses provider reads `OPENAI_API_KEY`; the optional DeepSeek JSON-output provider reads `DEEPSEEK_API_KEY` and uses the fixed official API base URL. Neither provider makes calls at import time. The fake provider validates the workflow only, and all automated tests remain offline.

## Deterministic verification

Every claim is checked independently of the provider. Verification rejects unknown, excluded, unsupplied, missing, excessive, or jurisdiction-mismatched citations; one-sided comparison claims; and strong claims supported only by label-1 evidence. Interpretive claims require a written qualification. This is structural grounding validation, not semantic-entailment or legal-correctness verification.

Evidence-scope limitations, evidence gaps, and legal uncertainties are distinct. The deterministic scope guard reports when a question exceeds the application scope represented in the curated evidence; an evidence gap must not be restated as a legal uncertainty. Each legal uncertainty is a structured object with at least one supplied chunk citation, and verification rejects unsupported recommendations to consult later guidance, case law, regulators, or other external sources. These are deterministic provenance rules, not LLM-based entailment verification.

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

python -m china_policy_rag.cli analysis ask `
  --question "How do China and the EU differ in training-data transparency?" `
  --evidence-set data/annotations/phase2_5_topic_relevant.csv `
  --provider deepseek `
  --model deepseek-v4-flash `
  --format markdown `
  --output reports/deepseek_test.md
```

The JSON model is canonical. Markdown is rendered only after deterministic verification.

`analysis ask --output` writes the same UTF-8 output to a local file and still prints it to the terminal. Real-provider runs log their start before the request; DeepSeek requests time out after 90 seconds.
