"""Command-line entry point for the offline local ingestion workflow."""

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from .annotation import export_candidates
from .corpus import validate_corpus
from .evaluation.runner import run_evaluation, write_evaluation
from .ingestion.base import ChunkingConfig, IngestionError
from .ingestion.pipeline import IngestionPipeline
from .retrieval.embeddings import provider_for
from .retrieval.indexes import build_indexes
from .retrieval.models import RetrievalMode, RetrievalQuery
from .retrieval.rendering import render_markdown
from .retrieval.service import RetrievalService


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
    index = subparsers.add_parser("index", help="Build or inspect a persistent retrieval index")
    index_sub = index.add_subparsers(dest="index_command", required=True)
    build = index_sub.add_parser(
        "build", help="Build indexes using offline deterministic embeddings"
    )
    build.add_argument("--chunks", type=Path, required=True)
    build.add_argument("--index-dir", type=Path, required=True)
    build.add_argument("--overwrite", action="store_true")
    build.add_argument(
        "--embedding-provider",
        choices=["deterministic", "sentence-transformers"],
        default="deterministic",
    )
    build.add_argument("--embedding-model")
    inspect = index_sub.add_parser("inspect", help="Show index metadata")
    inspect.add_argument("--index-dir", type=Path, required=True)
    search = subparsers.add_parser("search", help="Retrieve source-traceable evidence")
    search.add_argument("--index-dir", type=Path, required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--mode", choices=[item.value for item in RetrievalMode], default="hybrid")
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--format", choices=["json", "text", "markdown"], default="text")
    search.add_argument(
        "--embedding-provider",
        choices=["deterministic", "sentence-transformers"],
        default="deterministic",
    )
    search.add_argument("--embedding-model")
    evaluate = subparsers.add_parser(
        "evaluate", help="Evaluate retrieval against a synthetic offline benchmark"
    )
    evaluate.add_argument("--index-dir", type=Path, required=True)
    evaluate.add_argument("--benchmark", type=Path, required=True)
    evaluate.add_argument(
        "--modes", nargs="+", choices=[item.value for item in RetrievalMode], required=True
    )
    evaluate.add_argument("--k", nargs="+", type=int, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument(
        "--embedding-provider",
        choices=["deterministic", "sentence-transformers"],
        default="deterministic",
    )
    evaluate.add_argument("--embedding-model")
    corpus = subparsers.add_parser("corpus", help="Validate a fixed local authoritative corpus")
    corpus_subparsers = corpus.add_subparsers(dest="corpus_command", required=True)
    validate = corpus_subparsers.add_parser("validate", help="Validate files and write hashes")
    validate.add_argument("--raw-dir", type=Path, required=True)
    validate.add_argument("--manifest", type=Path, required=True)
    validate.add_argument("--output", type=Path, required=True)
    annotate = subparsers.add_parser(
        "annotate", help="Export retrieval candidates for human labelling"
    )
    annotate_subparsers = annotate.add_subparsers(dest="annotate_command", required=True)
    export = annotate_subparsers.add_parser(
        "export", help="Write merged retrieval candidates as a BOM CSV"
    )
    export.add_argument("--index-dir", type=Path, required=True)
    export.add_argument("--query-seeds", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--top-k", type=int, default=10)
    export.add_argument(
        "--embedding-provider",
        choices=["deterministic", "sentence-transformers"],
        default="deterministic",
    )
    export.add_argument("--embedding-model")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a CLI command and return a shell-compatible status code."""
    parser = build_parser()
    arguments = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if getattr(arguments, "debug", False) else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    try:
        if arguments.command == "index":
            if arguments.index_command == "inspect":
                print(
                    arguments.index_dir.joinpath("index_manifest.json").read_text(encoding="utf-8")
                )
                return 0
            provider = provider_for(arguments.embedding_provider, arguments.embedding_model)
            manifest = build_indexes(
                arguments.chunks,
                arguments.index_dir,
                provider,
                arguments.overwrite,
            )
            print(f"Built index for {manifest['chunk_count']} chunks.")
            return 0
        if arguments.command == "search":
            provider = provider_for(arguments.embedding_provider, arguments.embedding_model)
            bundle = RetrievalService(str(arguments.index_dir), provider).search(
                RetrievalQuery(
                    text=arguments.query,
                    top_k=arguments.top_k,
                    candidate_k=max(arguments.top_k, 20),
                    mode=RetrievalMode(arguments.mode),
                )
            )
            if arguments.format == "json":
                print(bundle.model_dump_json(indent=2))
            elif arguments.format == "markdown":
                print(render_markdown(bundle))
            else:
                for item in bundle.evidence:
                    print(f"{item.rank}. {item.title} [{item.chunk_id}]\n{item.text[:500]}\n")
            return 0
        if arguments.command == "evaluate":
            provider = provider_for(arguments.embedding_provider, arguments.embedding_model)
            service = RetrievalService(str(arguments.index_dir), provider)
            results = run_evaluation(service, arguments.benchmark, arguments.modes, arguments.k)
            write_evaluation(arguments.output, results)
            print(
                f"Evaluated {len(arguments.modes)} mode(s); results written to {arguments.output}."
            )
            return 0
        if arguments.command == "corpus":
            report = validate_corpus(arguments.raw_dir, arguments.manifest, arguments.output)
            print(f"Validated {report['valid_count']} source file(s).")
            return 0
        if arguments.command == "annotate":
            provider = provider_for(arguments.embedding_provider, arguments.embedding_model)
            count = export_candidates(
                RetrievalService(str(arguments.index_dir), provider),
                arguments.query_seeds,
                arguments.output,
                arguments.top_k,
            )
            print(f"Exported {count} candidate row(s) for human review.")
            return 0
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
        if getattr(arguments, "debug", False):
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
