"""Acquire reviewed evaluation assets without starting services or restoring data."""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit, urlunsplit

from harness.evaluation_setup import SetupError, verify_baseline
from harness.validate.dump_provenance import sha256_file


def _copy_source(source: str, destination: Path) -> None:
    url = urlsplit(source)
    if url.scheme:
        if url.scheme != "https" or not url.hostname:
            raise SetupError("Remote assets require an HTTPS source.")
        result = subprocess.run(
            [
                "curl",
                "--fail",
                "--location",
                "--silent",
                "--show-error",
                "--proto",
                "=https",
                "--proto-redir",
                "=https",
                "--connect-timeout",
                "20",
                "--max-time",
                "3600",
                "--output",
                str(destination),
                "--url",
                source,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            # Source URLs and server responses may include private access tokens.
            raise SetupError(
                f"Asset download failed (curl exit {result.returncode}); check source access."
            )
    else:
        shutil.copyfile(Path(source).expanduser(), destination)


def _sidecar_source(source: str) -> str:
    url = urlsplit(source)
    if not url.scheme:
        return f"{source}.provenance.json"
    return urlunsplit(url._replace(path=f"{url.path}.provenance.json"))


def _install(pairs: list[tuple[Path, Path]]) -> None:
    installed = []
    try:
        for staged, target in pairs:
            # Linking within one filesystem installs complete bytes and refuses
            # to overwrite a file created by a concurrent setup process.
            os.link(staged, target)
            installed.append((staged, target))
    except OSError as error:
        for staged, target in installed:
            if target.exists() and target.samefile(staged):
                target.unlink()
        raise SetupError(
            "Asset destination changed or could not be installed; inspect it before retrying."
        ) from error


def _prepare_file(
    path: Path,
    *,
    source: str | None,
    expected_sha: str,
    fetch: bool,
    portable: bool = False,
) -> dict:
    def verify(candidate: Path) -> str:
        if not candidate.is_file():
            raise SetupError(
                f"Asset missing: {candidate}; no existing file was replaced."
            )
        actual = sha256_file(candidate)
        if actual != expected_sha:
            raise SetupError(
                f"Asset checksum mismatch: {path}; existing files are never replaced."
            )
        if portable:
            verify_baseline(candidate)
        return actual

    sidecar = Path(f"{path}.provenance.json")
    existing = path.exists() or path.is_symlink()
    if portable:
        existing = existing or sidecar.exists() or sidecar.is_symlink()
    if existing or not fetch:
        verify(path)
    else:
        if not source:
            raise SetupError(
                "No reviewed baseline source is configured; supply --baseline-source."
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".asset-", dir=path.parent) as directory:
            staged = Path(directory) / path.name
            _copy_source(source, staged)
            pairs = [(staged, path)]
            if portable:
                staged_sidecar = Path(f"{staged}.provenance.json")
                _copy_source(_sidecar_source(source), staged_sidecar)
                pairs.append((staged_sidecar, sidecar))
            verify(staged)
            _install(pairs)
    return {
        "status": "verified",
        "path": str(path),
        "sha256": expected_sha,
        "bytes": path.stat().st_size,
    }


def prepare_assets(
    root: Path,
    *,
    model: str | None = None,
    baseline: Path | None = None,
    baseline_source: str | None = None,
    fetch: bool = False,
) -> dict:
    """Check by default; an explicit fetch installs only the selected assets."""
    if not model and baseline is None and not baseline_source:
        raise SetupError(
            "Select --model or --baseline (or --baseline-source); no asset was guessed."
        )
    report = {"status": "assets_verified", "readiness": "not_checked"}
    if model:
        # Reuse the reviewed identities without invoking Catalyst's deployment.
        catalog = root / "scripts/catalyst-model-router.models.tsv"
        with catalog.open() as stream:
            records = {
                row[0]: row
                for row in csv.reader(stream, delimiter="\t")
                if row and not row[0].startswith("#")
            }
        if model not in records or Path(model).name != model:
            raise SetupError(
                f"No pinned source for model {model}; configure it explicitly, without substitution."
            )
        _, _, sha, source = records[model]
        directory = Path(
            os.environ.get("LLAMA_MODEL_DIR") or "~/.cache/llama-router-models"
        ).expanduser()
        report["model"] = _prepare_file(
            directory / f"{model}.gguf", source=source, expected_sha=sha, fetch=fetch
        )
    if baseline is not None or baseline_source:
        identity = json.loads(
            (root / "datasets/sources/evaluation-baseline.json").read_text()
        )
        path = baseline or root / "artifacts/demo-data" / identity["filename"]
        report["baseline"] = _prepare_file(
            path.expanduser(),
            source=baseline_source or identity.get("source"),
            expected_sha=identity["sha256"],
            fetch=fetch,
            portable=True,
        )
    return report
