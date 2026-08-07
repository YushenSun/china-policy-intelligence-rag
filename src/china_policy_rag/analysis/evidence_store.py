"""Validated, read-only access to the human-curated topic evidence set."""

import csv
from collections.abc import Iterable
from datetime import date
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from .models import TopicEvidence

MAX_EVIDENCE_FILE_BYTES = 10_000_000


class TopicEvidenceStore:
    """Load exact source text and mechanically exclude label-0 evidence."""

    def __init__(
        self,
        evidence: Iterable[TopicEvidence],
        excluded_chunk_ids: Iterable[UUID] = (),
        version: str = "topic-evidence-v1",
    ) -> None:
        items = list(evidence)
        self._by_id = {item.chunk_id: item for item in items}
        if len(self._by_id) != len(items):
            raise ValueError("Evidence store contains duplicate chunk IDs")
        self.excluded_chunk_ids = frozenset(excluded_chunk_ids)
        self.version = version

    @classmethod
    def load_csv(cls, path: Path) -> "TopicEvidenceStore":
        resolved = path.resolve(strict=True)
        if resolved.suffix.lower() != ".csv":
            raise ValueError("Evidence set must be a CSV file")
        if resolved.stat().st_size > MAX_EVIDENCE_FILE_BYTES:
            raise ValueError("Evidence set exceeds the 10 MB safety limit")
        raw = resolved.read_bytes()
        version = f"topic-evidence-{sha256(raw).hexdigest()[:16]}"
        with resolved.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {
                "chunk_id",
                "document_id",
                "title",
                "issuer",
                "jurisdiction",
                "publication_date",
                "language",
                "local_file_path",
                "source_url",
                "page_reference",
                "section_reference",
                "chunk_text",
                "human_label",
                "reviewer_note",
            }
            if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                missing = sorted(required.difference(reader.fieldnames or []))
                raise ValueError(f"Evidence CSV is missing required columns: {missing}")
            rows = list(reader)
        if not rows:
            raise ValueError("Evidence CSV is empty")

        grouped: dict[UUID, list[dict[str, str]]] = {}
        for row in rows:
            try:
                chunk_id = UUID(row["chunk_id"])
                label = int(row["human_label"])
            except (TypeError, ValueError) as error:
                raise ValueError("Evidence CSV contains an invalid chunk ID or label") from error
            if label not in {0, 1, 2}:
                raise ValueError(f"Unsupported human label for chunk {chunk_id}: {label}")
            grouped.setdefault(chunk_id, []).append(row)

        included: list[TopicEvidence] = []
        excluded: set[UUID] = set()
        for chunk_id, group in grouped.items():
            labels = {int(row["human_label"]) for row in group}
            texts = {row["chunk_text"] for row in group}
            documents = {row["document_id"] for row in group}
            if len(labels) != 1 or len(texts) != 1 or len(documents) != 1:
                raise ValueError(f"Conflicting duplicate evidence rows for chunk {chunk_id}")
            label = next(iter(labels))
            if label == 0:
                excluded.add(chunk_id)
                continue
            row = group[0]
            try:
                included.append(
                    TopicEvidence(
                        chunk_id=chunk_id,
                        document_id=UUID(row["document_id"]),
                        title=row["title"],
                        issuer=row["issuer"],
                        jurisdiction=row["jurisdiction"],
                        publication_date=date.fromisoformat(row["publication_date"]),
                        language=row["language"],
                        local_file_path=row["local_file_path"],
                        source_url=row["source_url"] or None,
                        page_reference=row["page_reference"] or None,
                        section_reference=row["section_reference"] or None,
                        text=row["chunk_text"],
                        human_label=label,
                        reviewer_note=row["reviewer_note"] or None,
                    )
                )
            except ValidationError as error:
                raise ValueError(f"Invalid evidence row for chunk {chunk_id}: {error}") from error
        if not included:
            raise ValueError("Evidence CSV contains no label-1 or label-2 chunks")
        return cls(included, excluded, version)

    @property
    def evidence(self) -> list[TopicEvidence]:
        return list(self._by_id.values())

    @property
    def core_evidence(self) -> list[TopicEvidence]:
        return [item for item in self._by_id.values() if item.human_label == 2]

    def get(self, chunk_id: UUID) -> TopicEvidence | None:
        return self._by_id.get(chunk_id)

    def require(self, chunk_id: UUID) -> TopicEvidence:
        item = self.get(chunk_id)
        if item is None:
            raise KeyError(f"Unknown topic-evidence chunk ID: {chunk_id}")
        return item

    def contains(self, chunk_id: UUID) -> bool:
        return chunk_id in self._by_id

    def is_excluded(self, chunk_id: UUID) -> bool:
        return chunk_id in self.excluded_chunk_ids
