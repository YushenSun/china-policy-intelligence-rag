"""Deterministic input, output-name, and tool-boundary guardrails."""

import re
from pathlib import Path

from pydantic import BaseModel

from .models import ToolErrorCode

MAX_QUESTION_CHARACTERS = 2_000
_OUTPUT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
_FILESYSTEM = re.compile(r"(?:[A-Za-z]:\\|/etc/|/home/|\.\.[\\/])", re.IGNORECASE)


class GuardrailDecision(BaseModel):
    allowed: bool
    error_code: ToolErrorCode | None = None
    message: str = "Input accepted."


def check_user_input(question: str) -> GuardrailDecision:
    stripped = question.strip()
    if not stripped:
        return _reject(ToolErrorCode.INVALID_ARGUMENT, "Question must not be empty.")
    if len(stripped) > MAX_QUESTION_CHARACTERS:
        return _reject(ToolErrorCode.INVALID_ARGUMENT, "Question exceeds 2,000 characters.")
    lowered = stripped.lower()
    if _FILESYSTEM.search(stripped) or (
        "read" in lowered and any(word in lowered for word in ("file", "secret", "filesystem"))
    ):
        return _reject(
            ToolErrorCode.INVALID_ARGUMENT,
            "Arbitrary filesystem access is outside the policy-agent boundary.",
        )
    if "label" in lowered and any(
        word in lowered for word in ("change", "alter", "modify", "override", "set to")
    ):
        return _reject(ToolErrorCode.INVALID_ARGUMENT, "Human relevance labels are immutable.")
    if "ignore" in lowered and any(
        word in lowered for word in ("instruction", "scope", "grounding", "rule", "previous")
    ):
        return _reject(
            ToolErrorCode.OUT_OF_SCOPE,
            "Instructions cannot override the curated evidence and verification boundary.",
        )
    if "chunk_id" in lowered and any(
        phrase in lowered for phrase in ("even if", "not in the evidence", "invent")
    ):
        return _reject(ToolErrorCode.INVALID_CHUNK_ID, "Unknown chunk IDs cannot be forced.")
    if any(
        phrase in lowered
        for phrase in ("legal advice", "definitive legal conclusion", "legally liable")
    ):
        return _reject(
            ToolErrorCode.OUT_OF_SCOPE,
            "The workflow provides policy intelligence, not legal advice.",
        )
    return GuardrailDecision(allowed=True)


def safe_output_name(name: str, format_name: str) -> str:
    if Path(name).is_absolute() or ".." in name or "/" in name or "\\" in name:
        raise ValueError("Output must be a plain file name, not a path")
    if not _OUTPUT_NAME.fullmatch(name):
        raise ValueError("Output name contains unsupported characters")
    suffix = f".{format_name}"
    return name if name.lower().endswith(suffix) else f"{name}{suffix}"


def _reject(code: ToolErrorCode, message: str) -> GuardrailDecision:
    return GuardrailDecision(allowed=False, error_code=code, message=message)
