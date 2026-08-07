"""Bounded MCP input schemas."""

import json

from pydantic import BaseModel, Field, model_validator


class SearchEvidenceInput(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    jurisdictions: list[str] = Field(default_factory=lambda: ["CN", "EU"], max_length=2)
    top_k: int = Field(default=5, ge=1, le=8)
    include_supporting: bool = True
    evidence_budget: int = Field(default=8, ge=1, le=8)


class InspectEvidenceInput(BaseModel):
    chunk_id: str = Field(min_length=36, max_length=36)


class AssessQuestionInput(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)


class VerifyAnalysisInput(BaseModel):
    payload: dict[str, object] | None = None
    identifier: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def bound_and_require_one_source(self) -> "VerifyAnalysisInput":
        if (self.payload is None) == (self.identifier is None):
            raise ValueError("Provide exactly one of payload or identifier")
        if self.payload is not None and len(json.dumps(self.payload)) > 2_000_000:
            raise ValueError("Analysis payload exceeds 2 MB")
        return self
