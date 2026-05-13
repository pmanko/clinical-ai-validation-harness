from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunManifest:
    run_id: str
    project: str
    component: str
    git_sha: str
    dataset_id: str
    dataset_version: str
    schema_mapping_version: str
    gen_ai_provider_name: str
    generated_at: str = field(default_factory=utc_now_iso)
    evidence_status: str = "development"
    decision_rationale: str | None = None
    target_provenance: list[dict[str, Any]] = field(default_factory=list)
    otel_semconv_status: str = "development"
    otel_semconv_stability_opt_in: str = "gen_ai_latest_experimental"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": self.run_id,
            "project": self.project,
            "component": self.component,
            "git_sha": self.git_sha,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "schema_mapping_version": self.schema_mapping_version,
            "generated_at": self.generated_at,
            "evidence_status": self.evidence_status,
            "target_provenance": list(self.target_provenance),
            "otel": {
                "semconv_status": self.otel_semconv_status,
                "semconv_stability_opt_in": self.otel_semconv_stability_opt_in,
                "gen_ai.provider.name": self.gen_ai_provider_name,
            },
        }
        if self.decision_rationale is not None:
            payload["decision_rationale"] = self.decision_rationale
        return payload


def write_manifest(path: Path, manifest: RunManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), indent=2) + "\n", encoding="utf-8")


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event.setdefault("timestamp", utc_now_iso())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, separators=(",", ":")) + "\n")
