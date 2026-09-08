"""Build the hash-bound evidence bundle the dual-provider parity gate's FULL phase consumes.

`verify_dual_provider_parity_gates.py --phase full` requires a `dual_provider_parity_evidence.v1`
document: for every gate that claims live product behavior, an observation naming the artifacts it
used (with SHA-256) and expressing its claims as `json_pointer_equals` assertions the evaluator
re-reads. Deliberately, an assertion may not certify itself with a stored `actual` or `passed`
field — the evaluator resolves the artifact, verifies its digest, reads the pointer and compares.

Nothing produced such a bundle, so the full phase could not be run at all. This builder does, from a
declarative manifest (`datasets/validation/conformance/parity-evidence-manifest.json`), and holds
the properties that make a bundle worth trusting:

* every assertion is evaluated HERE, against the artifact it names, before the bundle is written, so
  the builder cannot emit a claim that is false or that the gate evaluator would reject;
* every artifact is hashed from disk at build time;
* a dirty worktree aborts the build, because the heads recorded would not cover the content the
  artifacts were produced from;
* observations the manifest does not cover are reported, so a PARTIAL bundle is explicit about what
  it leaves unproven instead of being silently short.

Usage:
    python3 scripts/build_parity_evidence.py --out artifacts/parity-evidence/evidence.json
    scripts/verify-dual-provider-parity-gates.sh --phase full --evidence <that file>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

SCHEMA = "dual_provider_parity_evidence.v1"

REPOSITORY_PATHS = {
    "harness": ".",
    "med-agent-hub": "targets/med-agent-hub",
    "querystore": "targets/querystore",
    "chartsearchai": "targets/chartsearchai",
    "chartsearchai-esm": "targets/chartsearchai-esm",
}

# Mirrors the evaluator's LIVE_OBSERVATIONS. Kept here so the builder can report what a partial
# bundle does not cover; `test_parity_evidence_builder.py` pins that the two stay in step.
LIVE_OBSERVATIONS = {
    "G04": ("bundled_without_hub", "hub_without_bundled_model", "no_silent_fallback"),
    "G05": ("single_provider_picker_hidden", "multi_provider_picker_visible",
            "provider_switch_new_conversation"),
    "G06": ("bundled_local_turn", "bundled_remote_turn", "bundled_query_scoped",
            "bundled_full_chart", "bundled_stream", "bundled_warmup_cache"),
    "G07": ("full_and_ranked_read_semantics",),
    "G08": ("etag_304", "chart_change_new_snapshot", "mixed_snapshot_rejected"),
    "G09": ("hub_without_querystore", "alternate_source_contract"),
    "G10": ("context_policy_parity",),
    "G12": ("cache_scope_isolation", "failed_revalidation_no_stale_serve"),
    "G14": ("temporal_gate_relay",),
    "G15": ("review_rewrite_regated", "final_answer_grounded", "prior_turn_citation_isolation"),
    "G16": ("drug_safety_checked", "drug_safety_limited", "drug_safety_unavailable"),
    "G17": ("provider_picker", "validation_and_evidence_visible", "reload_hydration"),
    "G18": ("new_turn_preemption", "disconnect_cancellation", "single_row_settled"),
    "G19": ("low_confidence_visible", "rejected_output_inspectable", "evidence_resolved",
            "no_silent_downgrade"),
    "G20": ("pr_descriptions_aligned",),
    "G21": ("required_ci", "real_path_smoke", "code_qa", "publication_prs"),
    "G22": ("evaluation_metadata_complete",),
}


class EvidenceError(RuntimeError):
    """A manifest entry that cannot be turned into honest evidence."""


def sha256_of(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_pointer(document, pointer: str):
    """RFC 6901 resolution, matching what the gate evaluator does with the same pointer."""
    if pointer in ("", "/"):
        return document
    if not pointer.startswith("/"):
        raise EvidenceError(f"pointer must start with '/': {pointer!r}")
    current = document
    for raw in pointer.lstrip("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            try:
                current = current[int(token)]
            except (ValueError, IndexError) as exc:
                raise EvidenceError(f"pointer {pointer!r} does not resolve") from exc
        elif isinstance(current, dict):
            if token not in current:
                raise EvidenceError(f"pointer {pointer!r} does not resolve")
            current = current[token]
        else:
            raise EvidenceError(f"pointer {pointer!r} does not resolve")
    return current


def _relative(root: pathlib.Path, path_text: str) -> pathlib.Path:
    candidate = pathlib.Path(path_text)
    return candidate if candidate.is_absolute() else (root / candidate)


def build_observation(root: pathlib.Path, entry: dict) -> dict:
    """Hash the entry's artifacts and PROVE its assertions before emitting the observation."""
    gate, identifier = entry.get("gate"), entry.get("id")
    method = (entry.get("method") or "").strip()
    if not method:
        raise EvidenceError(f"{gate}/{identifier}: an observation must state its method")
    artifacts, by_path = [], {}
    for artifact in entry.get("artifacts") or []:
        path = _relative(root, artifact["path"])
        if not path.is_file():
            raise EvidenceError(f"{gate}/{identifier}: artifact is missing: {artifact['path']}")
        by_path[artifact["path"]] = json.loads(path.read_text(encoding="utf-8"))
        artifacts.append({
            "kind": artifact.get("kind", "probe"),
            "path": str(path.relative_to(root)) if not pathlib.Path(artifact["path"]).is_absolute()
                    else artifact["path"],
            "sha256": sha256_of(path),
        })
    if not artifacts:
        raise EvidenceError(f"{gate}/{identifier}: an observation must cite at least one artifact")
    assertions = []
    for assertion in entry.get("assertions") or []:
        name = assertion["name"]
        document = by_path.get(assertion["artifact_path"])
        if document is None:
            raise EvidenceError(
                f"{gate}/{identifier}: assertion {name} names an artifact the observation does not cite")
        actual = resolve_pointer(document, assertion["artifact_json_pointer"])
        if actual != assertion["expected"]:
            raise EvidenceError(
                f"{gate}/{identifier}: assertion {name} is FALSE against its artifact — "
                f"{assertion['artifact_json_pointer']} is {actual!r}, not {assertion['expected']!r}")
        # No `actual`/`passed` keys: the evaluator must re-derive the value itself.
        assertions.append({
            "name": name,
            "evaluator": "json_pointer_equals",
            "artifact_path": next(a["path"] for a in artifacts
                                  if a["path"].endswith(pathlib.Path(assertion["artifact_path"]).name)),
            "artifact_json_pointer": assertion["artifact_json_pointer"],
            "expected": assertion["expected"],
        })
    if not assertions:
        raise EvidenceError(f"{gate}/{identifier}: an observation must carry structured assertions")
    return {"id": identifier, "status": "pass", "method": method,
            "artifacts": artifacts, "assertions": assertions}


def _git(repo: pathlib.Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def bundle_skeleton(root: pathlib.Path) -> dict:
    import datetime as dt
    heads = {}
    for name, relative in REPOSITORY_PATHS.items():
        repo = (root / relative).resolve()
        if _git(repo, "status", "--porcelain", "--untracked-files=all"):
            raise EvidenceError(
                f"{name} worktree is dirty; the heads this bundle records would not cover the "
                "content its artifacts came from")
        heads[name] = _git(repo, "rev-parse", "HEAD")
    return {
        "schema_version": SCHEMA,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "heads": heads,
        "gates": {},
    }


def unevidenced(covered: set[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(gate, identifier)
            for gate, identifiers in LIVE_OBSERVATIONS.items()
            for identifier in identifiers
            if (gate, identifier) not in covered]


def build(root: pathlib.Path, manifest: list[dict]) -> tuple[dict, list[tuple[str, str]]]:
    payload = bundle_skeleton(root)
    covered: set[tuple[str, str]] = set()
    for entry in manifest:
        gate = entry["gate"]
        observation = build_observation(root, entry)
        payload["gates"].setdefault(gate, {"status": "pass", "observations": []})
        payload["gates"][gate]["observations"].append(observation)
        covered.add((gate, entry["id"]))
    # A gate is only claimed when every observation the evaluator demands for it is present.
    for gate in list(payload["gates"]):
        present = {o["id"] for o in payload["gates"][gate]["observations"]}
        if set(LIVE_OBSERVATIONS.get(gate, ())) - present:
            payload["gates"][gate]["status"] = "partial"
    return payload, unevidenced(covered)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parents[1]))
    parser.add_argument("--manifest",
                        default="datasets/validation/conformance/parity-evidence-manifest.json")
    parser.add_argument("--out", default="artifacts/parity-evidence/evidence.json")
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root).resolve()
    manifest_path = root / args.manifest
    if not manifest_path.is_file():
        print(f"error: no manifest at {args.manifest}", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))["observations"]
    try:
        payload, missing = build(root, manifest)
    except EvidenceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    out = root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    claimed = sum(1 for g in payload["gates"].values() if g["status"] == "pass")
    print(f"==> wrote {args.out}: {claimed} gate(s) fully evidenced, "
          f"{len(payload['gates']) - claimed} partial")
    if missing:
        print(f"==> {len(missing)} live observation(s) still have no evidence:")
        for gate, identifier in missing:
            print(f"    {gate}  {identifier}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
