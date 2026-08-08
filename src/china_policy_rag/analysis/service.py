"""End-to-end orchestration for scoped generation and deterministic verification."""

from datetime import UTC, datetime
from uuid import UUID

from .evidence_selection import TopicEvidenceSelector, assess_scope, assess_sufficiency
from .evidence_store import TopicEvidenceStore
from .generation import LLMProvider
from .models import (
    EvidenceBudget,
    GroundedAnalysis,
    SufficiencyStatus,
    TrainingDataRiskBrief,
    VerificationResult,
)
from .prompts import build_analysis_prompt
from .refusal import refusal_analysis
from .verification import (
    is_evidence_gap_statement,
    is_structurally_unsupported_claim,
    verify_analysis,
    verify_brief,
)

CANONICAL_BRIEF_QUESTION = (
    "Compare China and the EU regarding lawful training-data sourcing, copyright, personal "
    "information, data quality, annotation, security, technical documentation, training-content "
    "transparency, regulatory disclosure, and downstream information duties."
)


class GroundingFailure(ValueError):
    """Raised when generated structured output fails deterministic grounding rules."""


class GroundedAnalysisService:
    def __init__(
        self,
        store: TopicEvidenceStore,
        provider: LLMProvider,
        budget: EvidenceBudget | None = None,
    ) -> None:
        self.store = store
        self.provider = provider
        self.selector = TopicEvidenceSelector(store, budget)

    def ask(self, question: str) -> tuple[GroundedAnalysis, VerificationResult, set[UUID]]:
        scope = assess_scope(question)
        selection = self.selector.select(question)
        sufficiency = assess_sufficiency(scope, selection)
        allowed = {item.chunk_id for item in selection.evidence}
        if sufficiency.status is SufficiencyStatus.INSUFFICIENT:
            analysis = refusal_analysis(
                question,
                scope,
                sufficiency,
                self.store.version,
                self.provider.model_identifier,
            )
        else:
            prompt = build_analysis_prompt(question, sufficiency, selection.evidence)
            analysis = self.provider.generate_analysis(
                question,
                scope,
                sufficiency,
                selection.evidence,
                self.store.version,
                prompt,
            )
            analysis = _normalize_grounding_categories(analysis)
            analysis = _omit_structurally_unsupported_claims(analysis, self.store, allowed)
            analysis = analysis.model_copy(update={"generated_at": datetime.now(UTC)})
        verification = verify_analysis(analysis, self.store, allowed)
        if not verification.passed:
            raise GroundingFailure(verification.model_dump_json(indent=2))
        return analysis, verification, allowed

    def brief(self) -> tuple[TrainingDataRiskBrief, VerificationResult, list[UUID]]:
        scope = assess_scope(CANONICAL_BRIEF_QUESTION)
        selection = self.selector.select(CANONICAL_BRIEF_QUESTION)
        sufficiency = assess_sufficiency(scope, selection)
        if sufficiency.status is SufficiencyStatus.INSUFFICIENT:
            raise GroundingFailure(sufficiency.explanation)
        prompt = build_analysis_prompt(CANONICAL_BRIEF_QUESTION, sufficiency, selection.evidence)
        brief = self.provider.generate_brief(selection.evidence, self.store.version, prompt)
        brief = brief.model_copy(update={"generated_at": datetime.now(UTC)})
        verification = verify_brief(brief, self.store)
        if not verification.passed:
            raise GroundingFailure(verification.model_dump_json(indent=2))
        return brief, verification, [item.chunk_id for item in selection.evidence]


def _normalize_grounding_categories(analysis: GroundedAnalysis) -> GroundedAnalysis:
    """Move evidence-silence statements out of legal uncertainties deterministically."""

    evidence_gaps = list(analysis.evidence_gaps)
    legal_uncertainties = []
    for uncertainty in analysis.uncertainties:
        if is_evidence_gap_statement(uncertainty.statement):
            if uncertainty.statement not in evidence_gaps:
                evidence_gaps.append(uncertainty.statement)
        else:
            legal_uncertainties.append(uncertainty)
    return analysis.model_copy(
        update={
            "evidence_gaps": evidence_gaps,
            "uncertainties": legal_uncertainties,
        }
    )


def _omit_structurally_unsupported_claims(
    analysis: GroundedAnalysis,
    store: TopicEvidenceStore,
    allowed_chunk_ids: set[UUID],
) -> GroundedAnalysis:
    """Conservatively omit structurally unsupported claims before strict verification."""

    claims = [
        claim
        for claim in analysis.claims
        if not is_structurally_unsupported_claim(claim, store, allowed_chunk_ids)
    ]
    return analysis.model_copy(update={"claims": claims})
