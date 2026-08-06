"""Orchestration for the offline Phase 1 local ingestion workflow."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from china_policy_rag.models import PolicyDocument, SourceChunk

from .base import (
    CHUNKING_VERSION,
    IDENTIFIER_VERSION,
    ChunkingConfig,
    DocumentStatus,
    IngestionReport,
    ManifestEntry,
)
from .chunking import chunk_section
from .discovery import discover_source_files
from .metadata import load_manifest
from .parsers import parser_for
from .serialization import ensure_output_paths, write_json, write_jsonl


def deterministic_document_id(relative_path: Path, file_sha256: str) -> UUID:
    """Create a stable UUIDv5 from normalized path, content hash, and schema version."""
    value = f"{IDENTIFIER_VERSION}:{relative_path.as_posix()}:{file_sha256}"
    return uuid5(NAMESPACE_URL, value)


def deterministic_chunk_id(document_id: UUID, chunk_index: int, text: str) -> UUID:
    """Create a stable UUIDv5 from document identity, order, text, and chunking version."""
    value = f"{CHUNKING_VERSION}:{document_id}:{chunk_index}:{text}"
    return uuid5(NAMESPACE_URL, value)


class IngestionResult:
    """In-memory result of a completed run, including report-safe failure status."""

    def __init__(
        self,
        documents: list[PolicyDocument],
        chunks: list[SourceChunk],
        report: IngestionReport,
    ) -> None:
        self.documents = documents
        self.chunks = chunks
        self.report = report


class IngestionPipeline:
    """Convert declared local documents into validated, source-traceable JSONL records."""

    def __init__(self, chunking: ChunkingConfig | None = None) -> None:
        self.chunking = chunking or ChunkingConfig()

    def run(
        self,
        input_dir: Path,
        manifest_path: Path,
        output_dir: Path,
        *,
        fail_on_unlisted_files: bool = False,
        overwrite: bool = False,
        report_path: Path | None = None,
    ) -> IngestionResult:
        """Process a validated manifest and serialize all successful documents atomically."""
        input_dir = input_dir.resolve()
        manifest_path = manifest_path.resolve()
        entries = load_manifest(manifest_path, input_dir)
        discovered = discover_source_files(input_dir)
        declared = {entry.file_path for entry in entries}
        unlisted = sorted(discovered - declared, key=lambda path: path.as_posix())
        if unlisted and fail_on_unlisted_files:
            names = ", ".join(path.as_posix() for path in unlisted)
            from .base import ManifestValidationError

            raise ManifestValidationError(f"Discovered files without manifest entries: {names}")

        output_paths = ensure_output_paths(output_dir, overwrite)
        if report_path is not None:
            if report_path.exists() and report_path.stat().st_size > 0 and not overwrite:
                from .base import OutputExistsError

                raise OutputExistsError(
                    f"Refusing to overwrite existing output: {report_path.name}"
                )
            output_paths["report"] = report_path
        started_at = datetime.now(UTC)
        documents: list[PolicyDocument] = []
        chunks: list[SourceChunk] = []
        statuses: list[DocumentStatus] = []
        warnings = [f"Unlisted supported file: {path.as_posix()}" for path in unlisted]

        for entry in entries:
            status, document, document_chunks = self._process_entry(input_dir, entry)
            statuses.append(status)
            if document is not None:
                documents.append(document)
                chunks.extend(document_chunks)
        completed_at = datetime.now(UTC)
        report = IngestionReport(
            started_at=started_at,
            completed_at=completed_at,
            input_directory=str(input_dir),
            manifest_path=str(manifest_path),
            manifest_entries=len(entries),
            discovered_files=len(discovered),
            documents_processed=len(documents),
            documents_failed=len(statuses) - len(documents),
            chunks_produced=len(chunks),
            warnings=warnings,
            documents=statuses,
            output_paths={key: str(path) for key, path in output_paths.items()},
            chunking_configuration=self.chunking,
        )
        write_jsonl(output_paths["documents"], documents)
        write_jsonl(output_paths["chunks"], chunks)
        write_json(output_paths["report"], report)
        return IngestionResult(documents, chunks, report)

    def _process_entry(
        self,
        input_dir: Path,
        entry: ManifestEntry,
    ) -> tuple[DocumentStatus, PolicyDocument | None, list[SourceChunk]]:
        """Process one source while preserving failures for the report."""
        try:
            extracted = parser_for(entry.file_path).parse(
                input_dir / entry.file_path, entry.file_path
            )
            document_id = deterministic_document_id(entry.file_path, extracted.file_sha256)
            text = "\n\n".join(section.text for section in extracted.sections)
            document = PolicyDocument(
                document_id=document_id,
                title=entry.title,
                issuer=entry.issuer,
                publication_date=entry.publication_date,
                jurisdiction=entry.jurisdiction,
                language=entry.language,
                document_type=entry.document_type,
                sector_tags=entry.sector_tags,
                source_url=entry.source_url,
                local_file_path=entry.file_path,
                text=text,
                source_file_sha256=extracted.file_sha256,
                parser_name=extracted.parser_name,
                parser_version=extracted.parser_version,
            )
            chunks: list[SourceChunk] = []
            document_offset = 0
            for section in extracted.sections:
                for span in chunk_section(section.text, self.chunking):
                    chunk_index = len(chunks)
                    chunks.append(
                        SourceChunk(
                            chunk_id=deterministic_chunk_id(document_id, chunk_index, span.text),
                            document_id=document_id,
                            chunk_index=chunk_index,
                            text=span.text,
                            page_reference=(
                                f"Page {section.page_number}"
                                if section.page_number is not None
                                else None
                            ),
                            section_reference=section.section_reference,
                            character_start=document_offset + span.start,
                            character_end=document_offset + span.end,
                            source_file_sha256=extracted.file_sha256,
                            chunking_version=CHUNKING_VERSION,
                        )
                    )
                document_offset += len(section.text) + 2
            status = DocumentStatus(
                file_path=entry.file_path.as_posix(),
                status="processed",
                document_id=str(document_id),
                file_sha256=extracted.file_sha256,
                parser_name=extracted.parser_name,
                chunk_count=len(chunks),
                warnings=extracted.warnings,
            )
            return status, document, chunks
        except Exception as error:
            return (
                DocumentStatus(
                    file_path=entry.file_path.as_posix(), status="failed", error=str(error)
                ),
                None,
                [],
            )
