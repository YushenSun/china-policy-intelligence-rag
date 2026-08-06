"""Command-line entry point for the offline local ingestion workflow."""

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from .ingestion.base import ChunkingConfig, IngestionError
from .ingestion.pipeline import IngestionPipeline


def build_parser() -> argparse.ArgumentParser:
    """Build the small, dependency-free command-line interface."""
    parser = argparse.ArgumentParser(prog="china-policy-rag")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest = subparsers.add_parser("ingest", help="Ingest local declared source files into JSONL")
    ingest.add_argument("--input-dir", type=Path, required=True)
    ingest.add_argument("--manifest", type=Path, required=True)
    ingest.add_argument("--output-dir", type=Path, required=True)
    ingest.add_argument("--max-chars", type=int, default=1200)
    ingest.add_argument("--overlap-chars", type=int, default=150)
    ingest.add_argument("--min-chars", type=int, default=100)
    ingest.add_argument("--fail-on-unlisted-files", action="store_true")
    ingest.add_argument("--overwrite", action="store_true")
    ingest.add_argument("--report-path", type=Path)
    ingest.add_argument("--debug", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a CLI command and return a shell-compatible status code."""
    parser = build_parser()
    arguments = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if arguments.debug else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    if arguments.command != "ingest":
        parser.error("Unknown command")
    try:
        config = ChunkingConfig(
            max_chars=arguments.max_chars,
            overlap_chars=arguments.overlap_chars,
            min_chars=arguments.min_chars,
        )
        result = IngestionPipeline(config).run(
            arguments.input_dir,
            arguments.manifest,
            arguments.output_dir,
            fail_on_unlisted_files=arguments.fail_on_unlisted_files,
            overwrite=arguments.overwrite,
            report_path=arguments.report_path,
        )
    except (IngestionError, OSError, ValueError) as error:
        logging.error("%s", error)
        if arguments.debug:
            raise
        return 1
    print(
        "Processed "
        f"{result.report.documents_processed} document(s), "
        f"produced {result.report.chunks_produced} chunk(s), "
        f"failed {result.report.documents_failed} document(s)."
    )
    return 1 if result.report.documents_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
