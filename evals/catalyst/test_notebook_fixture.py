from __future__ import annotations

import json
import re
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "catalyst-notebook-golden"
REQUIRED_FAMILIES = {
    "narrowing",
    "aggregation-output-shape",
    "unresolved-correction",
    "lint-clean-semantic-reviewer-correction",
    "hub-tool-failure",
}
ABS_PATH = re.compile(r"(/Users/|/home/|/private/|/tmp/)")
SECRETISH = re.compile(r"(api[_-]?key|password|secret|token)\s*[:=]", re.I)


def test_catalyst_fixture_provenance_and_coverage() -> None:
    prov = json.loads((FIXTURE / "provenance.json").read_text(encoding="utf-8"))
    assert prov["evidence_status"] == "development"
    assert prov["phi_free"] is True
    assert prov["release_evidence"] is False

    for name in (
        "run_manifest.json",
        "suite.json",
        "results.json",
        "evidence-index.json",
        "evidence-index.sha256",
    ):
        assert (FIXTURE / name).is_file(), name

    results = json.loads((FIXTURE / "results.json").read_text(encoding="utf-8"))
    families = {row["family"] for row in results["results"]}
    assert REQUIRED_FAMILIES <= families
    assert prov["gold_fail_scenarios"]
    assert prov["no_judge_scenarios"]

    text_blob = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in FIXTURE.rglob("*")
        if p.is_file() and p.suffix in {".json", ".jsonl", ".sql", ".md", ".txt"}
    )
    assert not ABS_PATH.search(text_blob)
    assert not SECRETISH.search(text_blob)
