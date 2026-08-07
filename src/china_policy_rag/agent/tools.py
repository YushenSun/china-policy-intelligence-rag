"""Narrow domain tools backed by the existing deterministic Phase 3 services."""

import csv
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from china_policy_rag.analysis.evidence_selection import (
    TopicEvidenceSelector,
    assess_scope,
    assess_sufficiency,
)
from china_policy_rag.analysis.evidence_store import TopicEvidenceStore
from china_policy_rag.analysis.generation import LLMProvider
from china_policy_rag.analysis.models import EvidenceBudget, GroundedAnalysis, TrainingDataRiskBrief
from china_policy_rag.analysis.rendering import render_analysis_markdown, render_brief_markdown
from china_policy_rag.analysis.service import GroundedAnalysisService, GroundingFailure
from china_policy_rag.analysis.verification import verify_analysis, verify_brief

from .guardrails import MAX_QUESTION_CHARACTERS, safe_output_name
from .models import (
    ApprovalDecision,
    EvidenceGapReport,
    EvidenceHit,
    EvidenceSearchResult,
    ExportReceipt,
    QuestionAssessment,
    ToolErrorCode,
    ToolResult,
    TopicScopeSummary,
    ValidatedArtifact,
    VerificationStatus,
)

DEFAULT_EVIDENCE_SET = Path("data/annotations/phase2_5_topic_relevant.csv")
DEFAULT_REPORT_ROOT = Path("reports/agent_exports")


class DomainTools:
    """Only the capabilities intentionally available to an agent or MCP client."""

    def __init__(
        self,
        store: TopicEvidenceStore,
        provider: LLMProvider,
        report_root: Path = DEFAULT_REPORT_ROOT,
    ) -> None:
        self.store = store
        self.provider = provider
        self.report_root = report_root
        self._artifacts: dict[str, ValidatedArtifact] = {}

    def get_topic_scope(self) -> ToolResult[TopicScopeSummary]:
        return ToolResult(
            success=True,
            data=TopicScopeSummary(
                topic=(
                    "China-EU training-data compliance and transparency for generative and "
                    "general-purpose AI models"
                ),
                jurisdictions=["CN", "EU"],
                evidence_set_version=self.store.version,
                allowed_dimensions=[
                    "lawful sourcing",
                    "copyright and personal information",
                    "data quality and annotation",
                    "security management",
                    "training-data and model documentation disclosure",
                ],
                limitations=[
                    "20 human-relevant chunks; label-0 evidence is mechanically excluded",
                    "No unrestricted web research or legal advice",
                    "Silence in the evidence does not establish absence of regulation",
                ],
                relevant_chunks=len(self.store.evidence),
                core_chunks=len(self.store.core_evidence),
            ),
            provenance={"evidence_set_version": self.store.version},
        )

    def search_topic_evidence(
        self,
        query: str,
        jurisdictions: list[str] | None = None,
        top_k: int = 5,
        include_supporting: bool = True,
        evidence_budget: int = 8,
    ) -> ToolResult[EvidenceSearchResult]:
        if not query.strip() or len(query) > MAX_QUESTION_CHARACTERS:
            return self._failure(ToolErrorCode.INVALID_ARGUMENT, "Invalid query length")
        if not 1 <= top_k <= 8 or not 1 <= evidence_budget <= 8:
            return self._failure(ToolErrorCode.INVALID_ARGUMENT, "top_k and budget must be 1..8")
        requested = set(jurisdictions or ["CN", "EU"])
        if not requested or not requested.issubset({"CN", "EU"}):
            return self._failure(ToolErrorCode.INVALID_ARGUMENT, "Jurisdictions must be CN or EU")
        budget = min(top_k, evidence_budget)
        selector = TopicEvidenceSelector(
            self.store,
            EvidenceBudget(
                maximum_chunks=budget,
                maximum_core_chunks=budget,
                maximum_supporting_chunks=budget if include_supporting else 0,
            ),
        )
        selection = selector.select(query)
        hits = [
            EvidenceHit(
                evidence=item,
                retrieval_score=selection.retrieval_scores.get(item.chunk_id, 0.0),
            )
            for item in selection.evidence
            if item.jurisdiction in requested and (include_supporting or item.human_label == 2)
        ][:top_k]
        return ToolResult(
            success=True,
            data=EvidenceSearchResult(query=query, hits=hits),
            provenance={"evidence_set_version": self.store.version},
        )

    def inspect_evidence(self, chunk_id: str) -> ToolResult[Any]:
        try:
            parsed = UUID(chunk_id)
        except ValueError:
            return self._failure(ToolErrorCode.INVALID_CHUNK_ID, "chunk_id must be a UUID")
        if self.store.is_excluded(parsed):
            return self._failure(
                ToolErrorCode.EXCLUDED_EVIDENCE, "The requested chunk has human label 0"
            )
        item = self.store.get(parsed)
        if item is None:
            return self._failure(ToolErrorCode.INVALID_CHUNK_ID, "Unknown topic chunk ID")
        return ToolResult(
            success=True,
            data=item,
            provenance={"evidence_set_version": self.store.version},
        )

    def assess_question(self, question: str) -> ToolResult[QuestionAssessment]:
        if not question.strip() or len(question) > MAX_QUESTION_CHARACTERS:
            return self._failure(ToolErrorCode.INVALID_ARGUMENT, "Invalid question length")
        scope = assess_scope(question)
        selection = TopicEvidenceSelector(self.store).select(question)
        sufficiency = assess_sufficiency(scope, selection)
        jurisdictions = sorted({item.jurisdiction for item in selection.evidence})
        workflow = ["scope_assessment"]
        if sufficiency.status.value != "INSUFFICIENT":
            workflow += ["evidence_search", "grounded_generation", "citation_verification"]
        return ToolResult(
            success=True,
            data=QuestionAssessment(
                scope=scope,
                sufficiency=sufficiency,
                evidence_gaps=sufficiency.missing_aspects,
                relevant_jurisdictions=jurisdictions,
                recommended_workflow=workflow,
            ),
            provenance={"evidence_set_version": self.store.version},
        )

    def grounded_analysis(
        self, question: str, evidence_budget: int = 8
    ) -> ToolResult[ValidatedArtifact]:
        if not 1 <= evidence_budget <= 8:
            return self._failure(ToolErrorCode.INVALID_ARGUMENT, "evidence_budget must be 1..8")
        try:
            analysis_store = self._store_for_question(question)
            service = GroundedAnalysisService(
                analysis_store,
                self.provider,
                EvidenceBudget(
                    maximum_chunks=evidence_budget,
                    maximum_core_chunks=min(6, evidence_budget),
                    maximum_supporting_chunks=min(2, evidence_budget),
                ),
            )
            analysis, verification, selected = service.ask(question)
        except GroundingFailure as error:
            return self._failure(ToolErrorCode.VERIFICATION_FAILED, str(error))
        artifact = self._register("analysis", analysis, verification, sorted(selected, key=str))
        return ToolResult(
            success=True,
            data=artifact,
            provenance={"evidence_set_version": self.store.version},
            verification_status=VerificationStatus.PASSED,
        )

    def _store_for_question(self, question: str) -> TopicEvidenceStore:
        lowered = question.lower()
        asks_cn = "china" in lowered or "中国" in question
        asks_eu = "eu" in lowered or "europe" in lowered or "欧盟" in question
        if asks_cn == asks_eu:
            return self.store
        jurisdiction = "CN" if asks_cn else "EU"
        evidence = [item for item in self.store.evidence if item.jurisdiction == jurisdiction]
        return TopicEvidenceStore(
            evidence,
            self.store.excluded_chunk_ids,
            self.store.version,
        )

    def generate_training_data_risk_brief(
        self,
        focus_dimensions: list[str] | None = None,
        jurisdictions: list[str] | None = None,
    ) -> ToolResult[ValidatedArtifact]:
        del focus_dimensions
        if jurisdictions and set(jurisdictions) != {"CN", "EU"}:
            return self._failure(
                ToolErrorCode.INSUFFICIENT_EVIDENCE,
                "The canonical comparative brief requires both CN and EU evidence",
            )
        try:
            brief, verification, selected = GroundedAnalysisService(
                self.store, self.provider
            ).brief()
        except GroundingFailure as error:
            return self._failure(ToolErrorCode.VERIFICATION_FAILED, str(error))
        artifact = self._register("brief", brief, verification, selected)
        return ToolResult(
            success=True,
            data=artifact,
            provenance={"evidence_set_version": self.store.version},
            verification_status=VerificationStatus.PASSED,
        )

    def verify_analysis(
        self, payload: dict[str, object] | None = None, identifier: str | None = None
    ) -> ToolResult[Any]:
        try:
            if identifier:
                artifact = self._artifacts.get(identifier)
                if artifact is None:
                    return self._failure(ToolErrorCode.INVALID_ARGUMENT, "Unknown safe identifier")
                result = artifact.verification
            elif payload is not None:
                if "risk_factors" in payload:
                    result = verify_brief(TrainingDataRiskBrief.model_validate(payload), self.store)
                else:
                    result = verify_analysis(GroundedAnalysis.model_validate(payload), self.store)
            else:
                return self._failure(
                    ToolErrorCode.INVALID_ARGUMENT, "Provide payload or identifier"
                )
        except ValidationError as error:
            return self._failure(ToolErrorCode.INVALID_ARGUMENT, str(error))
        return ToolResult(
            success=result.passed,
            data=result,
            error_code=None if result.passed else ToolErrorCode.VERIFICATION_FAILED,
            error_message=None if result.passed else "Deterministic verification failed",
            verification_status=(
                VerificationStatus.PASSED if result.passed else VerificationStatus.FAILED
            ),
        )

    def list_evidence_gaps(self) -> ToolResult[EvidenceGapReport]:
        return ToolResult(
            success=True,
            data=EvidenceGapReport(
                evidence_set_version=self.store.version,
                known_gaps=[
                    "The set does not establish complete China-EU regulatory symmetry.",
                    "Penalty amounts, retention periods, and licensing fees are not covered.",
                    "Topic labels are not query-level retrieval relevance judgments.",
                    "No conclusion may be drawn about rules absent from this curated set.",
                ],
            ),
            provenance={"evidence_set_version": self.store.version},
        )

    def export_validated_report(
        self,
        identifier: str,
        format_name: str,
        approved_output_name: str,
        approval: ApprovalDecision,
        overwrite: bool = False,
    ) -> ToolResult[ExportReceipt]:
        if approval is not ApprovalDecision.APPROVED:
            return self._failure(
                ToolErrorCode.APPROVAL_REQUIRED, "Explicit approval is required for export"
            )
        if format_name not in {"json", "markdown"}:
            return self._failure(ToolErrorCode.INVALID_ARGUMENT, "Format must be json or markdown")
        artifact = self._artifacts.get(identifier)
        if artifact is None or not artifact.verification.passed:
            return self._failure(
                ToolErrorCode.VERIFICATION_FAILED, "Only a registered verified artifact can export"
            )
        try:
            extension = "md" if format_name == "markdown" else "json"
            name = safe_output_name(approved_output_name, extension)
        except ValueError as error:
            return self._failure(ToolErrorCode.OUTPUT_PATH_REJECTED, str(error))
        root = self.report_root.resolve()
        output = root / name
        if output.exists() and not overwrite:
            return self._failure(ToolErrorCode.OUTPUT_PATH_REJECTED, "Output already exists")
        root.mkdir(parents=True, exist_ok=True)
        if format_name == "json":
            rendered = artifact.content.model_dump_json(indent=2)
        elif artifact.kind == "brief":
            rendered = render_brief_markdown(
                TrainingDataRiskBrief.model_validate(artifact.content), self.store
            )
        else:
            rendered = render_analysis_markdown(
                GroundedAnalysis.model_validate(artifact.content), self.store
            )
        output.write_text(rendered + ("\n" if format_name == "json" else ""), encoding="utf-8")
        return ToolResult(
            success=True,
            data=ExportReceipt(
                artifact_identifier=identifier,
                output_path=output.as_posix(),
                format=format_name,
                approval=approval,
            ),
            verification_status=VerificationStatus.PASSED,
        )

    def _register(
        self,
        kind: str,
        content: GroundedAnalysis | TrainingDataRiskBrief,
        verification: Any,
        evidence_chunk_ids: list[UUID],
    ) -> ValidatedArtifact:
        identifier = sha256(content.model_dump_json().encode()).hexdigest()[:20]
        artifact = ValidatedArtifact(
            identifier=identifier,
            kind=kind,
            content=content,
            verification=verification,
            evidence_chunk_ids=evidence_chunk_ids,
        )
        self._artifacts[identifier] = artifact
        return artifact

    @staticmethod
    def _failure(code: ToolErrorCode, message: str) -> ToolResult[Any]:
        return ToolResult(success=False, error_code=code, error_message=message)


def load_topic_store(path: Path = DEFAULT_EVIDENCE_SET) -> TopicEvidenceStore:
    """Load relevant evidence plus sibling label-0 IDs when the annotation source is present."""
    store = TopicEvidenceStore.load_csv(path)
    annotated = path.with_name("phase2_5_topic_annotated.csv")
    if path.name != DEFAULT_EVIDENCE_SET.name or not annotated.is_file():
        return store
    with annotated.open(encoding="utf-8-sig", newline="") as handle:
        excluded = {
            UUID(row["chunk_id"]) for row in csv.DictReader(handle) if row.get("human_label") == "0"
        }
    return TopicEvidenceStore(store.evidence, excluded, store.version)
