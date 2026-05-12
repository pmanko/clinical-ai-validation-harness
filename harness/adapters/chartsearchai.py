from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChartSearchAiAdapter:
    repo_path: Path

    def command_plan(self) -> list[str]:
        return [
            "mvn -pl api test -Dtest=LlmInferenceServiceTest",
            "mvn -pl api test -Dtest=EnrichedRetrievalEvalTest",
            "mvn -pl api test -Dtest=EnrichedRetrievalEvalTest -Dchartsearchai.eval.model=medcpt",
        ]
