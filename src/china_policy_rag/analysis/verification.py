"""Deterministic structural and provenance verification independent of the LLM."""

from collections.abc import Iterable
from uuid import UUID

from .evidence_store import TopicEvidenceStore
from .models import (
    AnalysisClaim,
    ClaimType,
    GroundedAnalysis,
    GroundedUncertainty,
    InferenceLevel,
    RiskSeverity,
    ScopeStatus,
    TrainingDataRiskBrief,
    VerificationIssue,
    VerificationResult,
)

_STRONG_TYPES = {
    ClaimType.OBLIGATION,
    ClaimType.PROHIBITION,
    ClaimType.TRANSPARENCY_REQUIREMENT,
    ClaimType.DOCUMENTATION_REQUIREMENT,
    ClaimType.DATA_QUALITY_REQUIREMENT,
    ClaimType.COPYRIGHT_REQUIREMENT,
    ClaimType.PERSONAL_DATA_REQUIREMENT,
    ClaimType.SECURITY_REQUIREMENT,
    ClaimType.COMPARISON,
}
_EXTERNAL_RECOMMENDATION_PHRASES = (
    "consult later guidance",
    "using later guidance",
    "later guidance should be consulted",
    "consult guidelines",
    "look to case law",
    "consult regulators",
    "consult authorities",
    "结合后续指南",
    "参考后续指南",
    "咨询监管机构",
)
_BROAD_MODEL_SCOPE_PHRASES = (
    "all general-purpose ai models",
    "all gpai models",
    "apply to all gpai",
    "apply to all general-purpose",
    "所有通用人工智能模型",
    "适用于所有通用人工智能模型",
)
_EVIDENCE_GAP_AS_UNCERTAINTY_PHRASES = (
    "does not specify",
    "not specified",
    "not expressly stated",
    "unclear whether",
    "absence of a public-disclosure",
    "未明确",
    "未说明",
    "未规定",
    "未在提供的证据",
    "存在解释空间",
)


def is_evidence_gap_statement(statement: str) -> bool:
    """Identify explicit absence-language that cannot be a legal uncertainty."""

    lowered = statement.lower()
    return any(phrase in lowered for phrase in _EVIDENCE_GAP_AS_UNCERTAINTY_PHRASES)


def is_structurally_unsupported_claim(
    claim: AnalysisClaim,
    store: TopicEvidenceStore,
    allowed_chunk_ids: set[UUID],
) -> bool:
    """Identify safe-to-omit claims that fail only known evidence-structure rules."""

    if not claim.citation_chunk_ids:
        return False
    evidence = []
    for chunk_id in claim.citation_chunk_ids:
        if (
            chunk_id not in allowed_chunk_ids
            or store.is_excluded(chunk_id)
            or (item := store.get(chunk_id)) is None
        ):
            return False
        evidence.append(item)
    if claim.claim_type in _STRONG_TYPES and not any(item.human_label == 2 for item in evidence):
        return True
    jurisdictions = {item.jurisdiction for item in evidence}
    return claim.claim_type is ClaimType.COMPARISON and not {"CN", "EU"}.issubset(jurisdictions)


def verify_analysis(
    analysis: GroundedAnalysis,
    store: TopicEvidenceStore,
    allowed_chunk_ids: set[UUID] | None = None,
    maximum_citations_per_claim: int = 6,
) -> VerificationResult:
    errors: list[VerificationIssue] = []
    warnings: list[VerificationIssue] = []
    verified = 0
    cited: set[UUID] = set()
    for claim in analysis.claims:
        claim_errors = _verify_claim(claim, store, allowed_chunk_ids, maximum_citations_per_claim)
        if claim_errors:
            errors.extend(claim_errors)
        else:
            verified += 1
            cited.update(claim.citation_chunk_ids)
        if claim.confidence > 0.9:
            warnings.append(
                VerificationIssue(
                    code="HIGH_MODEL_CONFIDENCE",
                    message="Model confidence is not evidence quality or legal certainty.",
                    claim_id=claim.claim_id,
                )
            )
    for uncertainty in analysis.uncertainties:
        uncertainty_errors = _verify_uncertainty(uncertainty, store, allowed_chunk_ids)
        if uncertainty_errors:
            errors.extend(uncertainty_errors)
        else:
            cited.update(uncertainty.citation_chunk_ids)
    errors.extend(_verify_scope_limitation_classification(analysis))
    errors.extend(_verify_no_external_recommendations(analysis, store, allowed_chunk_ids))
    denominator = len(allowed_chunk_ids or cited)
    coverage = len(cited) / denominator if denominator else 0.0
    return VerificationResult(
        passed=not errors,
        errors=errors,
        warnings=warnings,
        verified_claim_count=verified,
        rejected_claim_count=len(analysis.claims) - verified,
        evidence_coverage=min(coverage, 1.0),
    )


def verify_brief(brief: TrainingDataRiskBrief, store: TopicEvidenceStore) -> VerificationResult:
    claims = [*brief.china_findings, *brief.eu_findings, *brief.comparative_findings]
    errors: list[VerificationIssue] = []
    for claim in claims:
        errors.extend(_verify_claim(claim, store, None, 6))
    for risk in brief.risk_factors:
        evidence = [store.get(chunk_id) for chunk_id in risk.evidence_chunk_ids]
        if any(item is None for item in evidence):
            errors.append(
                VerificationIssue(
                    code="UNKNOWN_RISK_CITATION",
                    message=f"Risk {risk.risk_id} cites unknown evidence.",
                )
            )
            continue
        if risk.severity is RiskSeverity.HIGH and not any(
            item is not None and item.human_label == 2 for item in evidence
        ):
            errors.append(
                VerificationIssue(
                    code="HIGH_RISK_WITHOUT_CORE",
                    message=f"HIGH risk {risk.risk_id} requires label-2 evidence.",
                )
            )
        if risk.jurisdiction in {"CN", "EU"} and any(
            item is not None and item.jurisdiction != risk.jurisdiction for item in evidence
        ):
            errors.append(
                VerificationIssue(
                    code="RISK_JURISDICTION_MISMATCH",
                    message=f"Risk {risk.risk_id} cites another jurisdiction.",
                )
            )
    for uncertainty in brief.uncertainties:
        errors.extend(_verify_uncertainty(uncertainty, store, None))
    errors.extend(_verify_no_external_recommendations(brief, store, None))
    cited = set(brief.citations)
    unknown = [chunk_id for chunk_id in cited if not store.contains(chunk_id)]
    for chunk_id in unknown:
        errors.append(
            VerificationIssue(
                code="UNKNOWN_BRIEF_CITATION", message=f"Unknown brief citation: {chunk_id}"
            )
        )
    verified = len(claims) - len({issue.claim_id for issue in errors if issue.claim_id})
    return VerificationResult(
        passed=not errors,
        errors=errors,
        verified_claim_count=max(verified, 0),
        rejected_claim_count=len(claims) - max(verified, 0),
        evidence_coverage=len(cited) / len(store.evidence) if store.evidence else 0.0,
    )


def _verify_claim(
    claim: AnalysisClaim,
    store: TopicEvidenceStore,
    allowed_chunk_ids: set[UUID] | None,
    maximum_citations: int,
) -> list[VerificationIssue]:
    errors: list[VerificationIssue] = []
    if not claim.citation_chunk_ids and claim.claim_type is not ClaimType.UNCERTAINTY:
        return [_issue("MISSING_CITATION", "Substantive claim has no citation.", claim)]
    if len(claim.citation_chunk_ids) > maximum_citations:
        errors.append(_issue("CITATION_BUDGET_EXCEEDED", "Claim has too many citations.", claim))
    evidence = []
    for chunk_id in claim.citation_chunk_ids:
        if store.is_excluded(chunk_id):
            errors.append(_issue("LABEL_ZERO_CITATION", f"Excluded chunk cited: {chunk_id}", claim))
            continue
        item = store.get(chunk_id)
        if item is None:
            errors.append(_issue("UNKNOWN_CITATION", f"Unknown chunk cited: {chunk_id}", claim))
            continue
        if allowed_chunk_ids is not None and chunk_id not in allowed_chunk_ids:
            errors.append(
                _issue(
                    "UNSUPPLIED_CITATION",
                    f"Chunk was not supplied to generation: {chunk_id}",
                    claim,
                )
            )
        if not item.text:
            errors.append(
                _issue("MISSING_SOURCE_TEXT", f"Source text unavailable: {chunk_id}", claim)
            )
        evidence.append(item)
    if (
        claim.claim_type in _STRONG_TYPES
        and evidence
        and not any(item.human_label == 2 for item in evidence)
    ):
        errors.append(
            _issue(
                "STRONG_CLAIM_WITHOUT_CORE", "Strong claim relies only on label-1 evidence.", claim
            )
        )
    jurisdictions = {item.jurisdiction for item in evidence}
    if claim.jurisdiction == "CN" and jurisdictions and jurisdictions != {"CN"}:
        errors.append(
            _issue("CN_JURISDICTION_MISMATCH", "China claim cites non-CN evidence.", claim)
        )
    if claim.jurisdiction == "EU" and jurisdictions and jurisdictions != {"EU"}:
        errors.append(_issue("EU_JURISDICTION_MISMATCH", "EU claim cites non-EU evidence.", claim))
    if (
        claim.claim_type is ClaimType.COMPARISON
        and evidence
        and not {"CN", "EU"}.issubset(jurisdictions)
    ):
        errors.append(
            _issue("ONE_SIDED_COMPARISON", "China–EU comparison lacks one jurisdiction.", claim)
        )
    if claim.inference_level is InferenceLevel.INTERPRETIVE and not claim.qualification:
        errors.append(
            _issue("UNQUALIFIED_INTERPRETATION", "Interpretive claim lacks qualification.", claim)
        )
    return errors


def _verify_uncertainty(
    uncertainty: GroundedUncertainty,
    store: TopicEvidenceStore,
    allowed_chunk_ids: set[UUID] | None,
) -> list[VerificationIssue]:
    errors: list[VerificationIssue] = []
    if is_evidence_gap_statement(uncertainty.statement):
        errors.append(
            VerificationIssue(
                code="EVIDENCE_GAP_MISCLASSIFIED_AS_LEGAL_UNCERTAINTY",
                message=(
                    "Evidence silence or an unspecified detail must be recorded as an "
                    "evidence gap, not a legal uncertainty."
                ),
            )
        )
    if len(uncertainty.citation_chunk_ids) > 6:
        errors.append(
            VerificationIssue(
                code="UNCERTAINTY_CITATION_BUDGET_EXCEEDED",
                message="Legal uncertainty has too many citations.",
            )
        )
    for chunk_id in uncertainty.citation_chunk_ids:
        if store.is_excluded(chunk_id):
            errors.append(
                VerificationIssue(
                    code="LABEL_ZERO_UNCERTAINTY_CITATION",
                    message=f"Excluded chunk cited by legal uncertainty: {chunk_id}",
                )
            )
            continue
        item = store.get(chunk_id)
        if item is None:
            errors.append(
                VerificationIssue(
                    code="UNKNOWN_UNCERTAINTY_CITATION",
                    message=f"Unknown legal-uncertainty citation: {chunk_id}",
                )
            )
            continue
        if allowed_chunk_ids is not None and chunk_id not in allowed_chunk_ids:
            errors.append(
                VerificationIssue(
                    code="UNSUPPLIED_UNCERTAINTY_CITATION",
                    message=f"Legal uncertainty cites an unsupplied chunk: {chunk_id}",
                )
            )
        if not item.text:
            errors.append(
                VerificationIssue(
                    code="MISSING_UNCERTAINTY_SOURCE_TEXT",
                    message=f"Legal-uncertainty source text unavailable: {chunk_id}",
                )
            )
    return errors


def _verify_no_external_recommendations(
    output: GroundedAnalysis | TrainingDataRiskBrief,
    store: TopicEvidenceStore,
    allowed_chunk_ids: set[UUID] | None,
) -> list[VerificationIssue]:
    supplied_ids = allowed_chunk_ids or {item.chunk_id for item in store.evidence}
    supplied_text = " ".join(
        store.require(chunk_id).text.lower()
        for chunk_id in supplied_ids
        if store.contains(chunk_id)
    )
    output_text = " ".join(
        [
            output.short_answer
            if isinstance(output, GroundedAnalysis)
            else output.executive_summary,
            *(claim.claim_text for claim in _output_claims(output)),
            *(claim.qualification or "" for claim in _output_claims(output)),
            *output.evidence_gaps,
            *(item.statement for item in output.uncertainties),
        ]
    ).lower()
    errors: list[VerificationIssue] = []
    for phrase in _EXTERNAL_RECOMMENDATION_PHRASES:
        if phrase in output_text and phrase not in supplied_text:
            errors.append(
                VerificationIssue(
                    code="UNSUPPORTED_EXTERNAL_RECOMMENDATION",
                    message=(
                        "Output recommends an external source not present in supplied evidence: "
                        f"{phrase}"
                    ),
                )
            )
    return errors


def _verify_scope_limitation_classification(
    analysis: GroundedAnalysis,
) -> list[VerificationIssue]:
    if analysis.scope_status is not ScopeStatus.PARTIALLY_IN_SCOPE:
        return []
    errors: list[VerificationIssue] = []
    for uncertainty in analysis.uncertainties:
        statement = uncertainty.statement.lower()
        if any(phrase in statement for phrase in _BROAD_MODEL_SCOPE_PHRASES):
            errors.append(
                VerificationIssue(
                    code="SCOPE_LIMITATION_MISCLASSIFIED_AS_LEGAL_UNCERTAINTY",
                    message=(
                        "A broad-model application limit belongs in the deterministic scope "
                        "explanation, not a legal uncertainty."
                    ),
                )
            )
    return errors


def _output_claims(output: GroundedAnalysis | TrainingDataRiskBrief) -> list[AnalysisClaim]:
    if isinstance(output, GroundedAnalysis):
        return output.claims
    return [*output.china_findings, *output.eu_findings, *output.comparative_findings]


def all_cited_chunk_ids(claims: Iterable[AnalysisClaim]) -> set[UUID]:
    return {chunk_id for claim in claims for chunk_id in claim.citation_chunk_ids}


def _issue(code: str, message: str, claim: AnalysisClaim) -> VerificationIssue:
    return VerificationIssue(code=code, message=message, claim_id=claim.claim_id)
