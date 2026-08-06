"""Offline tests for Phase 0 domain models and configuration."""

from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from china_policy_rag.config import Settings
from china_policy_rag.models import (
    Citation,
    DocumentType,
    Language,
    PolicyDocument,
    RetrievalHit,
    RiskBrief,
    RiskCategory,
    RiskFactor,
    SourceChunk,
)


def make_document(**overrides: object) -> PolicyDocument:
    """Build a valid document without asserting any real policy content."""
    values: dict[str, object] = {
        "title": "Illustrative policy record",
        "issuer": "Illustrative issuer",
        "publication_date": date(2025, 1, 1),
        "jurisdiction": "Illustrative jurisdiction",
        "language": Language.ENGLISH,
        "document_type": DocumentType.POLICY,
        "text": "Illustrative text used only for model validation.",
    }
    values.update(overrides)
    return PolicyDocument.model_validate(values)


def make_citation() -> Citation:
    """Build a structurally valid citation without fabricating a source claim."""
    return Citation(
        document_id=uuid4(),
        source_title="Illustrative source record",
        evidence_location="Section 1",
        quoted_evidence="Illustrative evidence used only for validation.",
    )


def test_policy_document_creation() -> None:
    document = make_document()

    assert document.language is Language.ENGLISH
    assert document.title == "Illustrative policy record"


@pytest.mark.parametrize("field", ["title", "issuer", "jurisdiction", "text"])
def test_policy_document_rejects_empty_required_text_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        make_document(**{field: "   "})


def test_policy_document_rejects_unsupported_language() -> None:
    with pytest.raises(ValidationError):
        make_document(language="fr")


def test_retrieval_hit_rejects_out_of_bounds_score() -> None:
    chunk = SourceChunk(document_id=uuid4(), chunk_index=0, text="Validation text.")

    with pytest.raises(ValidationError):
        RetrievalHit(chunk=chunk, score=1.01, retrieval_method="lexical")


@pytest.mark.parametrize(
    "field",
    ["source_title", "evidence_location", "quoted_evidence"],
)
def test_citation_requires_source_identification_and_evidence_location(field: str) -> None:
    values: dict[str, object] = {
        "document_id": uuid4(),
        "source_title": "Illustrative source",
        "evidence_location": "Page 1",
        "quoted_evidence": "Illustrative evidence.",
    }
    values[field] = ""

    with pytest.raises(ValidationError):
        Citation.model_validate(values)


def test_risk_brief_requires_at_least_one_citation() -> None:
    factor = RiskFactor(
        category=RiskCategory.POLICY,
        description="Illustrative factor for validation.",
        affected_sectors=["Illustrative sector"],
    )

    with pytest.raises(ValidationError):
        RiskBrief(
            title="Illustrative brief",
            summary="Illustrative summary for validation.",
            risk_factors=[factor],
            citations=[],
        )


def test_configuration_defaults_do_not_require_external_services() -> None:
    settings = Settings(_env_file=None)

    assert settings.raw_data_dir.as_posix() == "data/raw"
    assert settings.processed_data_dir.as_posix() == "data/processed"
    assert settings.database_url is None
    assert settings.embedding_api_key is None
