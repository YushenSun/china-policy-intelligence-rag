"""Privacy-minimising local workflow trace records."""

from pathlib import Path

from .models import WorkflowTrace


class LocalTraceWriter:
    def __init__(self, root: Path = Path("reports/traces")) -> None:
        self.root = root

    def write(self, trace: WorkflowTrace) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        output = self.root / f"{trace.run_id}.json"
        output.write_text(trace.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return output
