#!/usr/bin/env python3
"""Publish or verify the design preview from one immutable Catalyst revision.

The design source revision is separate from the deployed application's gitlink.
No runtime pin, application source, or deployment configuration is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/DIGI-UW/catalyst-ai"
SHARED = "docs/specs/staff-workbench-ux"
INTEGRATION = "docs/specs/openelis-reporting-integration"


def expected_files(source: Path, revision: str) -> dict[str, bytes]:
    sha = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "--verify", revision + "^{commit}"],
        text=True,
    ).strip()

    def read(path: str) -> bytes:
        return subprocess.check_output(["git", "-C", str(source), "show", f"{sha}:{path}"])

    # Resolve every source before writing anything, so a missing file fails cleanly.
    files = {
        name: read(f"{SHARED}/{name}")
        for name in ("appearance.css", "appearance.js", "mock.css", "mock.js", "mock.html")
    }
    for name in ("app.html", "app.mjs", "integration.css", "model.mjs", "review.js"):
        content = read(f"{INTEGRATION}/{name}")
        if name == "app.html":
            content = content.replace(b"../staff-workbench-ux/", b"../")
        files[f"integration/{name}"] = content
    approved_spec = f"{REPOSITORY}/blob/{sha}/{SHARED}/spec.md"
    integration_spec = f"{REPOSITORY}/blob/{sha}/{INTEGRATION}/spec.md"
    wrapper = read(f"{INTEGRATION}/index.html").decode()
    wrapper = wrapper.replace("../staff-workbench-ux/", "")
    wrapper = wrapper.replace('src="app.html?', 'src="integration/app.html?')
    wrapper = wrapper.replace('src="review.js"', 'src="integration/review.js"')
    wrapper = wrapper.replace('data-approved-spec="spec.md"', f'data-approved-spec="{approved_spec}"')
    wrapper = wrapper.replace('data-integration-spec="spec.md"', f'data-integration-spec="{integration_spec}"')
    wrapper = wrapper.replace('id="spec-link" href="spec.md"', f'id="spec-link" href="{approved_spec}"')
    wrapper = wrapper.replace(
        'id="source-revision" href="spec.md">Working tree',
        f'id="source-revision" href="{REPOSITORY}/commit/{sha}">{sha[:12]}',
    )
    files["index.html"] = wrapper.encode()
    manifest = {
        "repository": REPOSITORY,
        "revision": sha,
        "integrationSpecification": integration_spec,
        "approvedSpecification": approved_spec,
        "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
    }
    files["source.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "targets/catalyst")
    parser.add_argument("--revision", required=True, help="Exact reviewed Catalyst design commit")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = expected_files(args.source, args.revision)
    destination = ROOT / "site/public/catalyst-design"
    if args.check:
        mismatches = [
            name for name, content in files.items()
            if not (destination / name).is_file() or (destination / name).read_bytes() != content
        ]
        if mismatches:
            print("Design publication differs: " + ", ".join(mismatches))
            return 1
        print(f"Design publication verified: {len(files)} files from {args.revision}")
        return 0
    for name, content in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print(f"Design publication synchronized: {len(files)} files from {args.revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
