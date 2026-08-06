"""Small deterministic retrieval metrics and YAML benchmark runner."""

import json
from pathlib import Path
from typing import Any

import yaml

from china_policy_rag.retrieval.models import RetrievalMode, RetrievalQuery
from china_policy_rag.retrieval.service import RetrievalService


def run_evaluation(
    service: RetrievalService, benchmark: Path, modes: list[str], ks: list[int]
) -> dict[str, object]:
    data: Any = yaml.safe_load(benchmark.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or not data.get("fixture_only")
        or not isinstance(data.get("queries"), list)
    ):
        raise ValueError("Benchmark must be a fixture-only YAML file with a queries list")
    corpus_ids = {str(chunk.chunk_id) for chunk in service.chunks}
    output: dict[str, object] = {"synthetic_fixture": True, "modes": {}}
    for mode_name in modes:
        results: list[dict[str, object]] = []
        for row in data["queries"]:
            relevant = set(row.get("relevant_chunk_ids", []))
            if not relevant.issubset(corpus_ids):
                raise ValueError(
                    f"Benchmark has unknown relevant chunk ID for {row.get('query_id')}"
                )
            hits = service.search(
                RetrievalQuery(
                    text=row["query_text"],
                    mode=RetrievalMode(mode_name),
                    top_k=max(ks),
                    candidate_k=max(ks),
                )
            ).evidence
            ranked = [str(item.chunk_id) for item in hits]
            metrics = {}
            for k in ks:
                selected = ranked[:k]
                matched = [item for item in selected if item in relevant]
                metrics[str(k)] = {
                    "recall": len(matched) / len(relevant) if relevant else None,
                    "precision": len(matched) / k,
                    "hit_rate": float(bool(matched)),
                    "mrr": next(
                        (1 / (i + 1) for i, item in enumerate(selected) if item in relevant), 0.0
                    ),
                }
            results.append({"query_id": row["query_id"], "metrics": metrics})
        output["modes"][mode_name] = results  # type: ignore[index]
    return output


def write_evaluation(path: Path, results: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
