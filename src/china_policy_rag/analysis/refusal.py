"""Explicit refusal and degradation responses for bounded analysis."""

from .models import (
    GroundedAnalysis,
    ScopeAssessment,
    ScopeStatus,
    SufficiencyAssessment,
    SufficiencyStatus,
)


def refusal_analysis(
    question: str,
    scope: ScopeAssessment,
    sufficiency: SufficiencyAssessment,
    evidence_set_version: str,
    model_identifier: str,
) -> GroundedAnalysis:
    if scope.status is ScopeStatus.OUT_OF_SCOPE:
        answer = (
            "This evidence set is limited to training-data compliance and transparency for "
            "generative or general-purpose AI models in China and the EU. The requested topic "
            "falls outside the curated evidence."
        )
    else:
        answer = (
            "The current curated evidence does not support a sufficiently grounded answer to "
            "this question."
        )
    return GroundedAnalysis(
        question=question,
        scope_status=scope.status,
        scope_explanation=scope.explanation,
        sufficiency_status=SufficiencyStatus.INSUFFICIENT,
        short_answer=answer,
        claims=[],
        evidence_gaps=sufficiency.missing_aspects,
        uncertainties=[],
        evidence_set_version=evidence_set_version,
        model_identifier=model_identifier,
    )
