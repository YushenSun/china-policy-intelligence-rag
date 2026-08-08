"""Vendor-neutral structured generation providers."""

import json
import os
from importlib import import_module
from typing import Any, Protocol, TypeVar, cast

from pydantic import BaseModel

from .models import (
    AnalysisClaim,
    ClaimType,
    DueDiligenceQuestion,
    GroundedAnalysis,
    InferenceLevel,
    RiskSeverity,
    ScopeAssessment,
    SufficiencyAssessment,
    TopicEvidence,
    TrainingDataRiskBrief,
    TrainingDataRiskFactor,
)
from .prompts import SYSTEM_PROMPT

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"


class LLMProvider(Protocol):
    model_identifier: str

    def generate_analysis(
        self,
        question: str,
        scope: ScopeAssessment,
        sufficiency: SufficiencyAssessment,
        evidence: list[TopicEvidence],
        evidence_set_version: str,
        prompt: str,
    ) -> GroundedAnalysis: ...

    def generate_brief(
        self,
        evidence: list[TopicEvidence],
        evidence_set_version: str,
        prompt: str,
    ) -> TrainingDataRiskBrief: ...


class DeterministicFakeLLM:
    """Offline schema and plumbing provider; it makes no semantic-quality claim."""

    model_identifier = "deterministic-fake-v1"

    def generate_analysis(
        self,
        question: str,
        scope: ScopeAssessment,
        sufficiency: SufficiencyAssessment,
        evidence: list[TopicEvidence],
        evidence_set_version: str,
        prompt: str,
    ) -> GroundedAnalysis:
        del prompt
        core = [item for item in evidence if item.human_label == 2]
        claims = [_claim_from_evidence(item, index + 1) for index, item in enumerate(core)]
        jurisdictions = {item.jurisdiction for item in core}
        if {"CN", "EU"}.issubset(jurisdictions):
            cn = next(item for item in core if item.jurisdiction == "CN")
            eu = next(item for item in core if item.jurisdiction == "EU")
            claims.append(
                AnalysisClaim(
                    claim_id=f"C{len(claims) + 1:02d}",
                    claim_text=(
                        "The curated evidence supports a comparison of China and EU training-data "
                        "requirements, while not establishing complete regulatory symmetry."
                    ),
                    claim_type=ClaimType.COMPARISON,
                    jurisdiction="CN-EU",
                    citation_chunk_ids=[cn.chunk_id, eu.chunk_id],
                    confidence=0.7,
                    qualification="Limited to the human-curated evidence set.",
                    inference_level=InferenceLevel.SYNTHESIS,
                )
            )
        return GroundedAnalysis(
            question=question,
            scope_status=scope.status,
            scope_explanation=scope.explanation,
            sufficiency_status=sufficiency.status,
            short_answer=(
                "The curated core evidence supports a bounded analysis of training-data "
                "compliance and transparency; see the verified claims below."
            ),
            claims=claims,
            evidence_gaps=sufficiency.missing_aspects,
            uncertainties=[
                "The fake provider validates offline workflow behaviour, not semantic quality."
            ],
            evidence_set_version=evidence_set_version,
            model_identifier=self.model_identifier,
        )

    def generate_brief(
        self,
        evidence: list[TopicEvidence],
        evidence_set_version: str,
        prompt: str,
    ) -> TrainingDataRiskBrief:
        del prompt
        core = [item for item in evidence if item.human_label == 2]
        cn = [item for item in core if item.jurisdiction == "CN"]
        eu = [item for item in core if item.jurisdiction == "EU"]
        cn_claims = [_claim_from_evidence(item, index + 1) for index, item in enumerate(cn)]
        eu_claims = [
            _claim_from_evidence(item, index + 1 + len(cn)) for index, item in enumerate(eu)
        ]
        comparative = (
            [
                AnalysisClaim(
                    claim_id=f"C{len(core) + 1:02d}",
                    claim_text=(
                        "The current evidence establishes jurisdiction-specific obligations, "
                        "does not establish that an unmentioned equivalent requirement is absent."
                    ),
                    claim_type=ClaimType.COMPARISON,
                    jurisdiction="CN-EU",
                    citation_chunk_ids=[cn[0].chunk_id, eu[0].chunk_id],
                    confidence=0.7,
                    qualification="Comparison is limited to the curated evidence.",
                    inference_level=InferenceLevel.SYNTHESIS,
                )
            ]
            if cn and eu
            else []
        )
        risks = [
            TrainingDataRiskFactor(
                risk_id=f"R{index + 1:02d}",
                category=_claim_type(item),
                jurisdiction=item.jurisdiction,
                description=item.reviewer_note or "Evidence-grounded training-data requirement.",
                business_relevance=(
                    "Operational controls should be able to evidence this requirement."
                ),
                severity=RiskSeverity.UNKNOWN,
                evidence_chunk_ids=[item.chunk_id],
                mitigation_question=_due_diligence_text(item),
                inference_level=InferenceLevel.DIRECT,
            )
            for index, item in enumerate(core)
        ]
        questions = [
            DueDiligenceQuestion(
                question_id=f"D{index + 1:02d}",
                question=_due_diligence_text(item),
                jurisdiction=item.jurisdiction,
                evidence_chunk_ids=[item.chunk_id],
            )
            for index, item in enumerate(core)
        ]
        return TrainingDataRiskBrief(
            title=(
                "China–EU Training Data Compliance and Transparency: Implications for "
                "Generative AI Model Providers"
            ),
            executive_summary=(
                "The human-curated evidence identifies obligations concerning lawful sourcing, "
                "personal information, data quality, annotation, security, copyright, technical "
                "documentation, and training-content transparency."
            ),
            scope="Training-data compliance and transparency in the curated China–EU evidence.",
            china_findings=cn_claims,
            eu_findings=eu_claims,
            comparative_findings=comparative,
            risk_factors=risks,
            recommended_due_diligence_questions=questions,
            evidence_gaps=[
                "No equivalent requirement is established where the current evidence is silent.",
                "This topic-level evidence set is not a query-level retrieval benchmark.",
            ],
            uncertainties=[
                "Severity is left UNKNOWN by the deterministic fake provider.",
                "A qualified analyst should review the source text before decision use.",
            ],
            citations=[item.chunk_id for item in core],
            evidence_set_version=evidence_set_version,
            model_identifier=self.model_identifier,
        )


class OpenAIProvider:
    """Optional OpenAI Responses structured-output adapter; never loaded by offline tests."""

    def __init__(self, model: str, temperature: float = 0.0) -> None:
        if not model.strip():
            raise ValueError("An explicit OpenAI model is required")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the OpenAI provider")
        try:
            module = import_module("openai")
        except ImportError as error:
            raise RuntimeError("Install the optional `.[openai]` dependency") from error
        self._client: Any = module.OpenAI(api_key=api_key, max_retries=2)
        self.model_identifier = model
        self.temperature = temperature

    def generate_analysis(
        self,
        question: str,
        scope: ScopeAssessment,
        sufficiency: SufficiencyAssessment,
        evidence: list[TopicEvidence],
        evidence_set_version: str,
        prompt: str,
    ) -> GroundedAnalysis:
        del evidence
        parsed = self._parse(prompt, GroundedAnalysis)
        return parsed.model_copy(
            update={
                "question": question,
                "scope_status": scope.status,
                "scope_explanation": scope.explanation,
                "sufficiency_status": sufficiency.status,
                "evidence_set_version": evidence_set_version,
                "model_identifier": self.model_identifier,
            }
        )

    def generate_brief(
        self,
        evidence: list[TopicEvidence],
        evidence_set_version: str,
        prompt: str,
    ) -> TrainingDataRiskBrief:
        del evidence
        parsed = self._parse(prompt, TrainingDataRiskBrief)
        return parsed.model_copy(
            update={
                "evidence_set_version": evidence_set_version,
                "model_identifier": self.model_identifier,
            }
        )

    def _parse(self, prompt: str, schema: type[StructuredModel]) -> StructuredModel:
        response = self._client.responses.parse(
            model=self.model_identifier,
            instructions=SYSTEM_PROMPT,
            input=prompt,
            text_format=schema,
            temperature=self.temperature,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError("OpenAI provider returned no parsed structured output")
        return cast(StructuredModel, parsed)


class DeepSeekProvider:
    """Optional DeepSeek JSON-output adapter over its OpenAI-compatible API."""

    def __init__(
        self,
        model: str = DEFAULT_DEEPSEEK_MODEL,
        temperature: float = 0.0,
    ) -> None:
        if not model.strip():
            raise ValueError("An explicit DeepSeek model is required")
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is required for the DeepSeek provider")
        try:
            module = import_module("openai")
        except ImportError as error:
            raise RuntimeError("Install the optional `.[deepseek]` dependency") from error
        self._client: Any = module.OpenAI(
            api_key=api_key,
            base_url=DEEPSEEK_BASE_URL,
            max_retries=2,
            timeout=90.0,
        )
        self.model_identifier = model
        self.temperature = temperature

    def generate_analysis(
        self,
        question: str,
        scope: ScopeAssessment,
        sufficiency: SufficiencyAssessment,
        evidence: list[TopicEvidence],
        evidence_set_version: str,
        prompt: str,
    ) -> GroundedAnalysis:
        del evidence
        parsed = self._parse(prompt, GroundedAnalysis)
        return parsed.model_copy(
            update={
                "question": question,
                "scope_status": scope.status,
                "scope_explanation": scope.explanation,
                "sufficiency_status": sufficiency.status,
                "evidence_set_version": evidence_set_version,
                "model_identifier": self.model_identifier,
            }
        )

    def generate_brief(
        self,
        evidence: list[TopicEvidence],
        evidence_set_version: str,
        prompt: str,
    ) -> TrainingDataRiskBrief:
        del evidence
        parsed = self._parse(prompt, TrainingDataRiskBrief)
        return parsed.model_copy(
            update={
                "evidence_set_version": evidence_set_version,
                "model_identifier": self.model_identifier,
            }
        )

    def _parse(self, prompt: str, schema: type[StructuredModel]) -> StructuredModel:
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        json_instructions = (
            f"{SYSTEM_PROMPT}\nReturn exactly one JSON object matching this JSON Schema. "
            f"Do not use Markdown fences. JSON Schema:\n{schema_json}"
        )
        try:
            response = self._client.chat.completions.create(
                model=self.model_identifier,
                messages=[
                    {"role": "system", "content": json_instructions},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=self.temperature,
                max_tokens=8_192,
                extra_body={"thinking": {"type": "disabled"}},
            )
        except Exception as error:
            status_code = getattr(error, "status_code", None)
            if status_code == 401:
                message = (
                    "DeepSeek authentication failed (HTTP 401). "
                    "Create a valid API key and reload DEEPSEEK_API_KEY."
                )
            elif status_code == 429:
                message = "DeepSeek rate limit or account balance error (HTTP 429)."
            else:
                message = f"DeepSeek API request failed ({type(error).__name__})."
            raise RuntimeError(message) from error
        if not response.choices:
            raise ValueError("DeepSeek provider returned no completion choices")
        content = response.choices[0].message.content
        if not content or not content.strip():
            raise ValueError("DeepSeek provider returned empty JSON content")
        return schema.model_validate_json(content)


def provider_for(name: str, model: str | None = None) -> LLMProvider:
    if name == "fake":
        return DeterministicFakeLLM()
    if name == "openai":
        if model is None:
            raise ValueError("--model is required for the OpenAI provider")
        return OpenAIProvider(model)
    if name == "deepseek":
        return DeepSeekProvider(model or DEFAULT_DEEPSEEK_MODEL)
    raise ValueError("Unsupported analysis provider; use fake, openai, or deepseek")


def _claim_from_evidence(item: TopicEvidence, number: int) -> AnalysisClaim:
    return AnalysisClaim(
        claim_id=f"C{number:02d}",
        claim_text=item.reviewer_note or "The cited passage contains relevant policy evidence.",
        claim_type=_claim_type(item),
        jurisdiction=item.jurisdiction,
        citation_chunk_ids=[item.chunk_id],
        confidence=0.9,
        inference_level=InferenceLevel.DIRECT,
    )


def _claim_type(item: TopicEvidence) -> ClaimType:
    text = f"{item.reviewer_note or ''} {item.text}".lower()
    if "copyright" in text or "版权" in text:
        return ClaimType.COPYRIGHT_REQUIREMENT
    if "personal" in text or "个人信息" in text:
        return ClaimType.PERSONAL_DATA_REQUIREMENT
    if "security" in text or "安全" in text:
        return ClaimType.SECURITY_REQUIREMENT
    if "documentation" in text or "文档" in text:
        return ClaimType.DOCUMENTATION_REQUIREMENT
    if "transparen" in text or "透明" in text or "摘要" in text:
        return ClaimType.TRANSPARENCY_REQUIREMENT
    if "quality" in text or "annotation" in text or "质量" in text or "标注" in text:
        return ClaimType.DATA_QUALITY_REQUIREMENT
    return ClaimType.OBLIGATION


def _due_diligence_text(item: TopicEvidence) -> str:
    category = _claim_type(item)
    questions = {
        ClaimType.COPYRIGHT_REQUIREMENT: (
            "Can copyright restrictions and rights reservations be identified and documented?"
        ),
        ClaimType.PERSONAL_DATA_REQUIREMENT: (
            "Can the lawful basis for personal information in training data be documented?"
        ),
        ClaimType.SECURITY_REQUIREMENT: (
            "Are training-data security controls and incident procedures documented?"
        ),
        ClaimType.DOCUMENTATION_REQUIREMENT: (
            "Is model and training-process documentation complete and current?"
        ),
        ClaimType.TRANSPARENCY_REQUIREMENT: (
            "Can the required training-content information be disclosed in sufficient detail?"
        ),
        ClaimType.DATA_QUALITY_REQUIREMENT: (
            "Are data-quality and annotation practices documented and reviewed?"
        ),
    }
    return questions.get(
        category, "Can the organisation document compliance with this requirement?"
    )
