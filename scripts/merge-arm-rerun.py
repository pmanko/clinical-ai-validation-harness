#!/usr/bin/env python3
"""Merge a re-run of ONE backend arm into a prior multi-arm run, producing a
fresh unified single-run report.

When one arm of a comparison fails (e.g. HIGH timed out) and is re-run on its
own, its results land in a separate run dir. This stitches the good arms from
the original run together with the re-run's rows for the patched arm, so the
report renders all arms side by side again — without re-running the arms that
already succeeded.

    python scripts/merge-arm-rerun.py <orig_run_dir> <patch_run_dir> <arm_backend_id>

Writes a new run dir under artifacts/validate/<uuid>/ (manifest + events from
the original, results = original-minus-arm + patch's arm rows) and builds its
report.html. The original run dir is left untouched.
"""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

from harness.validate.report import build_report


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit(f"usage: {sys.argv[0]} <orig_run_dir> <patch_run_dir> <arm_backend_id>")
    orig, patch, arm = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]

    manifest = json.loads((orig / "run_manifest.json").read_text(encoding="utf-8"))
    run_id = manifest.get("run_id", "")

    orig_rows = _read_jsonl(orig / "results.jsonl")
    patch_rows = _read_jsonl(patch / "results.jsonl")

    kept = [r for r in orig_rows if r.get("backend_id") != arm]
    arm_rows = [r for r in patch_rows if r.get("backend_id") == arm]
    if not arm_rows:
        sys.exit(f"patch run {patch} has no rows for backend {arm!r}")
    # The patched rows carry the patch run's id; rewrite to the unified run's id
    # so every row references one run (projection contract).
    for r in arm_rows:
        r["run_id"] = run_id
    merged = kept + arm_rows  # good arms keep their original order; patched arm last

    out = Path("artifacts/validate") / str(uuid.uuid4())
    out.mkdir(parents=True)
    shutil.copy(orig / "run_manifest.json", out / "run_manifest.json")
    # events.jsonl from the original already carries a backend_selected event (with
    # the column label) for every arm; the report reads only those for labels.
    if (orig / "events.jsonl").exists():
        shutil.copy(orig / "events.jsonl", out / "events.jsonl")
    (out / "results.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in merged), encoding="utf-8")

    report = build_report(out)
    arms = sorted({r.get("backend_id") for r in merged})
    print(f"merged {len(kept)} kept + {len(arm_rows)} {arm} = {len(merged)} rows")
    print(f"arms: {arms}")
    print(f"unified run dir: {out}")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
