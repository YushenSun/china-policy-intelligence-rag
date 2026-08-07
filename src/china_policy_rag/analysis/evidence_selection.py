"""Deterministic scope, evidence selection, and sufficiency policies."""

from collections import Counter

from china_policy_rag.retrieval.embeddings import _tokens
from china_policy_rag.retrieval.query import normalize_query

from .evidence_store import TopicEvidenceStore
from .models import (
    EvidenceBudget,
    EvidenceSelection,
    ScopeAssessment,
    ScopeStatus,
    SufficiencyAssessment,
    SufficiencyStatus,
    TopicEvidence,
)

_TOPIC_TERMS = {
    "training data",
    "training-data",
    "training content",
    "dataset",
    "data source",
    "provenance",
    "copyright",
    "text and data mining",
    "personal information",
    "personal data",
    "data quality",
    "annotation",
    "transparency",
    "documentation",
    "fine-tuning",
    "训练数据",
    "训练内容",
    "数据来源",
    "版权",
    "个人信息",
    "数据质量",
    "标注",
    "透明度",
    "文档",
    "微调",
}
_AI_TERMS = {"ai", "artificial intelligence", "model", "generative", "人工智能", "模型"}
_OUT_OF_SCOPE_TERMS = {
    "semiconductor subsidy",
    "gpu",
    "unemployment",
    "stock",
    "competitor",
    "healthcare investment",
    "foreign investment restriction",
    "芯片补贴",
    "显卡",
    "失业",
    "股票",
    "医疗外资",
}
_KNOWN_EVIDENCE_GAPS = {
    "tax",
    "retention period",
    "licensing fee",
    "penalty amount",
    "罚款金额",
    "保存期限",
    "许可费用",
}
_COMPARISON_TERMS = {
    "china and the eu",
    "china-eu",
    "china–eu",
    "differ",
    "difference",
    "compare",
    "comparison",
    "中国和欧盟",
    "中欧",
    "比较",
    "差异",
}


def assess_scope(question: str) -> ScopeAssessment:
    normalized = normalize_query(question).lower()
    if any(term in normalized for term in _OUT_OF_SCOPE_TERMS):
        return ScopeAssessment(
            status=ScopeStatus.OUT_OF_SCOPE,
            explanation=(
                "The curated evidence is limited to training-data compliance and transparency "
                "for generative or general-purpose AI models in China and the EU."
            ),
        )
    if any(term in normalized for term in _KNOWN_EVIDENCE_GAPS):
        return ScopeAssessment(
            status=ScopeStatus.INSUFFICIENT_EVIDENCE,
            explanation="The question is topic-adjacent, but the requested detail is absent.",
        )
    matches = sorted(term for term in _TOPIC_TERMS if term in normalized)
    if matches:
        return ScopeAssessment(
            status=ScopeStatus.IN_SCOPE,
            explanation="The question directly concerns the curated training-data topic.",
            matched_topics=matches,
        )
    if any(term in normalized for term in _AI_TERMS):
        return ScopeAssessment(
            status=ScopeStatus.PARTIALLY_IN_SCOPE,
            explanation=(
                "The question concerns AI, but only its training-data compliance and "
                "transparency portion can be addressed from this evidence set."
            ),
        )
    return ScopeAssessment(
        status=ScopeStatus.OUT_OF_SCOPE,
        explanation=(
            "The requested topic falls outside the curated training-data compliance and "
            "transparency evidence set."
        ),
    )


class TopicEvidenceSelector:
    def __init__(self, store: TopicEvidenceStore, budget: EvidenceBudget | None = None) -> None:
        self.store = store
        self.budget = budget or EvidenceBudget()

    def select(self, question: str) -> EvidenceSelection:
        comparison = _is_comparison(question)
        ranked = sorted(
            ((item, _relevance(question, item)) for item in self.store.evidence),
            key=lambda pair: (-pair[1], str(pair[0].chunk_id)),
        )
        core = [pair for pair in ranked if pair[0].human_label == 2]
        supporting = [pair for pair in ranked if pair[0].human_label == 1]
        chosen: list[tuple[TopicEvidence, float]] = []

        if comparison:
            per_jurisdiction = max(1, self.budget.maximum_core_chunks // 2)
            for jurisdiction in ("CN", "EU"):
                matches = [pair for pair in core if pair[0].jurisdiction == jurisdiction][
                    :per_jurisdiction
                ]
                chosen.extend(matches)
        for pair in core:
            if (
                pair not in chosen
                and len([item for item in chosen if item[0].human_label == 2])
                < self.budget.maximum_core_chunks
            ):
                chosen.append(pair)
        for pair in supporting:
            if (
                len([item for item in chosen if item[0].human_label == 1])
                >= self.budget.maximum_supporting_chunks
            ):
                break
            if len(chosen) >= self.budget.maximum_chunks:
                break
            if pair[1] > 0 or not chosen:
                chosen.append(pair)
        chosen = chosen[: self.budget.maximum_chunks]
        return EvidenceSelection(
            question=question,
            evidence=[item for item, _ in chosen],
            comparison_requested=comparison,
            retrieval_scores={item.chunk_id: score for item, score in chosen},
        )


def assess_sufficiency(
    scope: ScopeAssessment, selection: EvidenceSelection
) -> SufficiencyAssessment:
    if scope.status in {ScopeStatus.OUT_OF_SCOPE, ScopeStatus.INSUFFICIENT_EVIDENCE}:
        return SufficiencyAssessment(
            status=SufficiencyStatus.INSUFFICIENT,
            explanation="No substantive answer may be generated for an out-of-scope question.",
            missing_aspects=["Evidence within the selected topic scope"],
        )
    core = [item for item in selection.evidence if item.human_label == 2]
    if not core:
        return SufficiencyAssessment(
            status=SufficiencyStatus.INSUFFICIENT,
            explanation="No human-labelled core evidence was selected.",
            missing_aspects=["At least one label-2 core chunk"],
        )
    jurisdictions = {item.jurisdiction for item in core}
    if selection.comparison_requested and not {"CN", "EU"}.issubset(jurisdictions):
        return SufficiencyAssessment(
            status=SufficiencyStatus.INSUFFICIENT,
            explanation="A China–EU comparison requires label-2 evidence from both jurisdictions.",
            missing_aspects=["Core evidence from both CN and EU"],
        )
    supported = sorted(jurisdictions)
    if scope.status is ScopeStatus.PARTIALLY_IN_SCOPE:
        return SufficiencyAssessment(
            status=SufficiencyStatus.LIMITED,
            explanation="Only the training-data portion of the question is supported.",
            supported_aspects=supported,
            missing_aspects=["Aspects outside the curated topic"],
        )
    return SufficiencyAssessment(
        status=SufficiencyStatus.SUFFICIENT,
        explanation="Selected evidence includes human-labelled core support.",
        supported_aspects=supported,
    )


def _is_comparison(question: str) -> bool:
    normalized = normalize_query(question).lower()
    return any(term in normalized for term in _COMPARISON_TERMS)


def _relevance(question: str, evidence: TopicEvidence) -> float:
    query_tokens = Counter(_tokens(normalize_query(question).lower()))
    haystack = " ".join([evidence.title, evidence.reviewer_note or "", evidence.text]).lower()
    evidence_tokens = Counter(_tokens(haystack))
    return float(sum(min(count, evidence_tokens[token]) for token, count in query_tokens.items()))
