"""Deterministic structural and provenance verification independent of the LLM."""

from collections.abc import Iterable
from uuid import UUID

from .evidence_store import TopicEvidenceStore
from .models import (
    AnalysisClaim,
    ClaimType,
    GroundedAnalysis,
    InferenceLevel,
    RiskSeverity,
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


def all_cited_chunk_ids(claims: Iterable[AnalysisClaim]) -> set[UUID]:
    return {chunk_id for claim in claims for chunk_id in claim.citation_chunk_ids}


def _issue(code: str, message: str, claim: AnalysisClaim) -> VerificationIssue:
    return VerificationIssue(code=code, message=message, claim_id=claim.claim_id)
