"""Render validated JSON models with stable chunk-level citation aliases."""

import html
from uuid import UUID

from .evidence_store import TopicEvidenceStore
from .models import GroundedAnalysis, GroundedUncertainty, TopicEvidence, TrainingDataRiskBrief
from .verification import all_cited_chunk_ids


def render_analysis_markdown(analysis: GroundedAnalysis, store: TopicEvidenceStore) -> str:
    cited = all_cited_chunk_ids(analysis.claims) | _uncertainty_citation_ids(analysis.uncertainties)
    aliases = _aliases(cited, store)
    blocks = [
        "# Grounded policy analysis",
        f"**Question:** {_escape(analysis.question)}",
        f"**Scope:** `{analysis.scope_status}` — {_escape(analysis.scope_explanation)}",
        f"**Evidence sufficiency:** `{analysis.sufficiency_status}`",
        _escape(analysis.short_answer),
    ]
    if analysis.claims:
        blocks.append("## Verified claims")
        for claim in analysis.claims:
            citations = " ".join(f"[{aliases[item]}]" for item in claim.citation_chunk_ids)
            qualification = (
                f" Qualification: {_escape(claim.qualification)}" if claim.qualification else ""
            )
            blocks.append(
                f"- **{claim.claim_id} · {claim.inference_level} · {claim.jurisdiction}:** "
                f"{_escape(claim.claim_text)} {citations}.{qualification}"
            )
    if analysis.evidence_gaps:
        blocks.append(
            "## Evidence gaps\n\n" + "\n".join(f"- {_escape(x)}" for x in analysis.evidence_gaps)
        )
    if analysis.uncertainties:
        blocks.append(
            "## Legal uncertainties\n\n"
            + "\n".join(_render_uncertainty(item, aliases) for item in analysis.uncertainties)
        )
    if cited:
        blocks.append(_references(cited, aliases, store))
    blocks.append(f"> {_escape(analysis.disclaimer)}")
    return "\n\n".join(blocks) + "\n"


def render_brief_markdown(brief: TrainingDataRiskBrief, store: TopicEvidenceStore) -> str:
    cited = set(brief.citations) | _uncertainty_citation_ids(brief.uncertainties)
    aliases = _aliases(cited, store)
    blocks = [
        f"# {_escape(brief.title)}",
        f"## Executive summary\n\n{_escape(brief.executive_summary)}",
        f"## Scope\n\n{_escape(brief.scope)}",
    ]
    for heading, claims in (
        ("China findings", brief.china_findings),
        ("EU findings", brief.eu_findings),
        ("Comparative findings", brief.comparative_findings),
    ):
        blocks.append(f"## {heading}")
        if not claims:
            blocks.append("No equivalent requirement is established by the current evidence set.")
        else:
            blocks.append(
                "\n".join(
                    f"- {_escape(claim.claim_text)} "
                    + " ".join(f"[{aliases[item]}]" for item in claim.citation_chunk_ids)
                    for claim in claims
                )
            )
    blocks.append("## Risk factors")
    blocks.append(
        "\n".join(
            f"- **{risk.risk_id} · {risk.severity} · {risk.jurisdiction}:** "
            f"{_escape(risk.description)} "
            + " ".join(f"[{aliases[item]}]" for item in risk.evidence_chunk_ids)
            + f"  \n  Due diligence: {_escape(risk.mitigation_question)}"
            for risk in brief.risk_factors
        )
    )
    blocks.append("## Recommended due-diligence questions")
    blocks.append(
        "\n".join(
            f"- {_escape(item.question)} "
            + " ".join(f"[{aliases[chunk_id]}]" for chunk_id in item.evidence_chunk_ids)
            for item in brief.recommended_due_diligence_questions
        )
    )
    blocks.append(
        "## Evidence gaps\n\n" + "\n".join(f"- {_escape(x)}" for x in brief.evidence_gaps)
    )
    blocks.append(
        "## Legal uncertainties\n\n"
        + "\n".join(_render_uncertainty(item, aliases) for item in brief.uncertainties)
    )
    blocks.append(_references(cited, aliases, store))
    blocks.append(f"> {_escape(brief.disclaimer)}")
    return "\n\n".join(blocks) + "\n"


def evidence_packet_json(evidence: list[TopicEvidence]) -> str:
    return "[\n" + ",\n".join(item.model_dump_json(indent=2) for item in evidence) + "\n]\n"


def _aliases(chunk_ids: set[UUID], store: TopicEvidenceStore) -> dict[UUID, str]:
    counters: dict[str, int] = {}
    aliases: dict[UUID, str] = {}
    items = sorted(
        (store.require(chunk_id) for chunk_id in chunk_ids),
        key=lambda x: (x.jurisdiction, str(x.chunk_id)),
    )
    for item in items:
        prefix = item.jurisdiction if item.jurisdiction in {"CN", "EU"} else "SRC"
        counters[prefix] = counters.get(prefix, 0) + 1
        aliases[item.chunk_id] = f"{prefix}-{counters[prefix]}"
    return aliases


def _uncertainty_citation_ids(uncertainties: list[GroundedUncertainty]) -> set[UUID]:
    return {chunk_id for item in uncertainties for chunk_id in item.citation_chunk_ids}


def _render_uncertainty(uncertainty: GroundedUncertainty, aliases: dict[UUID, str]) -> str:
    citations = " ".join(f"[{aliases[chunk_id]}]" for chunk_id in uncertainty.citation_chunk_ids)
    return f"- **{uncertainty.uncertainty_type}:** {_escape(uncertainty.statement)} {citations}."


def _references(chunk_ids: set[UUID], aliases: dict[UUID, str], store: TopicEvidenceStore) -> str:
    lines = ["## Evidence References"]
    for chunk_id, alias in sorted(aliases.items(), key=lambda pair: pair[1]):
        item = store.require(chunk_id)
        location = item.page_reference or item.section_reference or "Not available"
        lines.append(
            f"### [{alias}]\n\n"
            f"- Title: {_escape(item.title)}\n"
            f"- Issuer: {_escape(item.issuer)}\n"
            f"- Publication date: {item.publication_date}\n"
            f"- Jurisdiction: {item.jurisdiction}\n"
            f"- Chunk: `{item.chunk_id}`\n"
            f"- Source: {_escape(item.source_url or item.local_file_path)}\n"
            f"- Section/Page: {_escape(location)}\n\n"
            f"> {_escape(item.text).replace(chr(10), chr(10) + '> ')}"
        )
    return "\n\n".join(lines)


def _escape(value: object) -> str:
    text = html.escape(str(value), quote=False)
    for character in ("\\", "`", "*", "_", "[", "]"):
        text = text.replace(character, f"\\{character}")
    return text
