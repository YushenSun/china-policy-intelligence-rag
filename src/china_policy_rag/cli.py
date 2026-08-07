"""Command-line entry point for the offline local ingestion workflow."""

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from .agent.evaluation import (
    evaluate_workflows,
    load_workflow_cases,
    write_workflow_evaluation,
)
from .agent.runtime import PolicyAgentRuntime
from .agent.tools import DEFAULT_EVIDENCE_SET, DomainTools, load_topic_store
from .analysis.generation import provider_for as analysis_provider_for
from .analysis.models import GroundedAnalysis, TrainingDataRiskBrief
from .analysis.rendering import (
    evidence_packet_json,
    render_analysis_markdown,
    render_brief_markdown,
)
from .analysis.service import GroundedAnalysisService, GroundingFailure
from .analysis.verification import verify_analysis, verify_brief
from .annotation import export_candidates, materialize_topic_annotations
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
    materialize = annotate_subparsers.add_parser(
        "materialize-topic",
        help="Validate human topic labels and write deduplicated evidence files",
    )
    materialize.add_argument("--annotated-csv", type=Path, required=True)
    materialize.add_argument("--relevant-output", type=Path, required=True)
    materialize.add_argument("--core-output", type=Path, required=True)
    materialize.add_argument("--summary-output", type=Path, required=True)
    materialize.add_argument("--topic", required=True)
    materialize.add_argument("--manifest", type=Path, default=Path("data/phase2_5/manifest.yaml"))
    analysis = subparsers.add_parser(
        "analysis", help="Generate and verify scoped grounded analysis"
    )
    analysis_subparsers = analysis.add_subparsers(dest="analysis_command", required=True)
    ask = analysis_subparsers.add_parser(
        "ask", help="Answer a scoped question from curated evidence"
    )
    ask.add_argument("--question", required=True)
    ask.add_argument("--evidence-set", type=Path, required=True)
    ask.add_argument("--provider", choices=["fake", "openai"], default="fake")
    ask.add_argument("--model")
    ask.add_argument("--format", choices=["json", "markdown"], default="markdown")
    brief = analysis_subparsers.add_parser(
        "brief", help="Generate the canonical China–EU risk brief"
    )
    brief.add_argument("--evidence-set", type=Path, required=True)
    brief.add_argument("--provider", choices=["fake", "openai"], default="fake")
    brief.add_argument("--model")
    brief.add_argument("--output", type=Path, required=True)
    verify = analysis_subparsers.add_parser("verify", help="Verify a saved analysis or brief JSON")
    verify.add_argument("--analysis-json", type=Path, required=True)
    verify.add_argument("--evidence-set", type=Path, required=True)
    agent = subparsers.add_parser("agent", help="Run or evaluate the bounded policy agent")
    agent_subparsers = agent.add_subparsers(dest="agent_command", required=True)
    agent_run = agent_subparsers.add_parser("run", help="Run one verified agent workflow")
    agent_run.add_argument("--question", required=True)
    agent_run.add_argument("--evidence-set", type=Path, default=DEFAULT_EVIDENCE_SET)
    agent_run.add_argument("--provider", choices=["fake", "openai"], default="fake")
    agent_run.add_argument("--model")
    agent_run.add_argument("--show-tools", action="store_true")
    agent_run.add_argument("--trace-local", action="store_true")
    agent_run.add_argument(
        "--output", help="Approved plain file name written only under reports/agent_exports"
    )
    agent_run.add_argument("--approve-export", action="store_true")
    agent_run.add_argument("--overwrite", action="store_true")
    agent_scope = agent_subparsers.add_parser("scope", help="Show the exact supported scope")
    agent_scope.add_argument("--evidence-set", type=Path, default=DEFAULT_EVIDENCE_SET)
    agent_inspect = agent_subparsers.add_parser(
        "inspect", help="Inspect one permitted evidence chunk"
    )
    agent_inspect.add_argument("--chunk-id", required=True)
    agent_inspect.add_argument("--evidence-set", type=Path, default=DEFAULT_EVIDENCE_SET)
    agent_evaluate = agent_subparsers.add_parser(
        "evaluate", help="Run the offline Agent Workflow Evaluation"
    )
    agent_evaluate.add_argument("--cases", type=Path, required=True)
    agent_evaluate.add_argument("--evidence-set", type=Path, default=DEFAULT_EVIDENCE_SET)
    agent_evaluate.add_argument("--provider", choices=["fake"], default="fake")
    agent_evaluate.add_argument("--output", type=Path, required=True)
    mcp = subparsers.add_parser("mcp", help="Run the optional read-only policy MCP server")
    mcp_subparsers = mcp.add_subparsers(dest="mcp_command", required=True)
    mcp_serve = mcp_subparsers.add_parser("serve", help="Serve approved tools locally")
    mcp_serve.add_argument("--transport", choices=["stdio"], default="stdio")
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
            if arguments.annotate_command == "materialize-topic":
                counts = materialize_topic_annotations(
                    arguments.annotated_csv,
                    arguments.relevant_output,
                    arguments.core_output,
                    arguments.summary_output,
                    arguments.topic,
                    arguments.manifest,
                )
                print(
                    "Materialized "
                    f"{counts['relevant']} relevant and {counts['core']} core unique chunk(s)."
                )
                return 0
            provider = provider_for(arguments.embedding_provider, arguments.embedding_model)
            count = export_candidates(
                RetrievalService(str(arguments.index_dir), provider),
                arguments.query_seeds,
                arguments.output,
                arguments.top_k,
            )
            print(f"Exported {count} candidate row(s) for human review.")
            return 0
        if arguments.command == "analysis":
            return _run_analysis(arguments)
        if arguments.command == "agent":
            return _run_agent(arguments)
        if arguments.command == "mcp":
            from .mcp.server import create_server

            create_server().run(transport=arguments.transport)
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
    except (GroundingFailure, IngestionError, OSError, ValueError) as error:
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


def _run_analysis(arguments: argparse.Namespace) -> int:
    store = load_topic_store(arguments.evidence_set)
    if arguments.analysis_command == "verify":
        path = arguments.analysis_json.resolve(strict=True)
        if path.stat().st_size > 2_000_000:
            raise ValueError("Analysis JSON exceeds the 2 MB safety limit")
        payload = path.read_text(encoding="utf-8")
        if '"risk_factors"' in payload:
            result = verify_brief(TrainingDataRiskBrief.model_validate_json(payload), store)
        else:
            result = verify_analysis(GroundedAnalysis.model_validate_json(payload), store)
        print(result.model_dump_json(indent=2))
        return 0 if result.passed else 2

    provider = analysis_provider_for(arguments.provider, arguments.model)
    service = GroundedAnalysisService(store, provider)
    if arguments.analysis_command == "ask":
        analysis, _, _ = service.ask(arguments.question)
        if arguments.format == "json":
            print(analysis.model_dump_json(indent=2))
        else:
            print(render_analysis_markdown(analysis, store))
        return 0

    brief, verification, selected_ids = service.brief()
    output = arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_brief_markdown(brief, store), encoding="utf-8")
    stem = output.stem
    prefix = stem[:-6] if stem.endswith("_brief") else stem
    json_path = output.with_suffix(".json")
    evidence_path = output.with_name(f"{prefix}_evidence.json")
    verification_path = output.with_name(f"{prefix}_verification.json")
    json_path.write_text(brief.model_dump_json(indent=2), encoding="utf-8")
    evidence_path.write_text(
        evidence_packet_json([store.require(chunk_id) for chunk_id in selected_ids]),
        encoding="utf-8",
    )
    verification_path.write_text(verification.model_dump_json(indent=2), encoding="utf-8")
    print(f"Wrote verified brief artefacts under {output.parent}.")
    return 0


def _run_agent(arguments: argparse.Namespace) -> int:
    store = load_topic_store(arguments.evidence_set)
    if arguments.agent_command in {"scope", "inspect"}:
        tools = DomainTools(store, analysis_provider_for("fake"))
        tool_result = (
            tools.get_topic_scope()
            if arguments.agent_command == "scope"
            else tools.inspect_evidence(arguments.chunk_id)
        )
        print(tool_result.model_dump_json(indent=2))
        return 0 if tool_result.success else 2
    provider = analysis_provider_for(arguments.provider, getattr(arguments, "model", None))
    runtime = PolicyAgentRuntime(DomainTools(store, provider))
    if arguments.agent_command == "evaluate":
        evaluation = evaluate_workflows(runtime, load_workflow_cases(arguments.cases))
        write_workflow_evaluation(arguments.output, evaluation)
        print(evaluation.model_dump_json(indent=2))
        return 0
    run_result = runtime.run(
        arguments.question,
        trace_local=arguments.trace_local,
        output_name=arguments.output,
        approve_export=arguments.approve_export,
        overwrite=arguments.overwrite,
    )
    if arguments.show_tools:
        for call in run_result.tool_calls:
            status = "OK" if call.success else call.error_code
            print(f"[{call.sequence}] {call.tool_name}: {status}")
    if run_result.output is not None:
        print(render_analysis_markdown(GroundedAnalysis.model_validate(run_result.output), store))
    else:
        print(f"{run_result.status}: {run_result.message}")
    if run_result.export is not None:
        print(f"Exported approved report: {run_result.export.output_path}")
    return 0 if run_result.status.value in {"COMPLETED", "REFUSED", "DEGRADED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
