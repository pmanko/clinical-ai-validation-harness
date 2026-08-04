from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "publish-catalyst-profile-comparison.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "publish_catalyst_profile_comparison", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_main_requires_one_run_directory_per_profile(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr("sys.argv", [str(SCRIPT)])

    with pytest.raises(SystemExit, match="run_dir_for_each_of_5_profiles"):
        module.main()


def test_main_stages_report_metadata_and_idempotent_index(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(
        module,
        "build_comparison_report",
        lambda entries, title: f"<html>{title}:{len(entries)}</html>",
    )
    (tmp_path / "reports-index.json").write_text(
        json.dumps({"runs": [{"slug": "existing", "title": "Existing"}]}),
        encoding="utf-8",
    )
    run_dirs = []
    for index in range(len(module.ENTRIES)):
        run_dir = tmp_path / f"run-{index}"
        run_dir.mkdir()
        (run_dir / "results.json").write_text(
            json.dumps({"passedCount": index + 1, "resultCount": 12}),
            encoding="utf-8",
        )
        run_dirs.append(run_dir)
    monkeypatch.setattr("sys.argv", [str(SCRIPT), *(str(path) for path in run_dirs)])

    module.main()

    destination = tmp_path / "artifacts" / "reports" / module.SLUG
    assert (
        destination.joinpath("index.html")
        .read_text(encoding="utf-8")
        .endswith(":5</html>")
    )
    metadata = json.loads(destination.joinpath("meta.json").read_text(encoding="utf-8"))
    assert metadata["family"] == "catalyst-profile-comparison"
    assert metadata["run_dirs"] == [path.name for path in run_dirs]
    index = json.loads((tmp_path / "reports-index.json").read_text(encoding="utf-8"))
    assert [entry["slug"] for entry in index["runs"]] == [module.SLUG, "existing"]

    module.main()

    unchanged_index = json.loads(
        (tmp_path / "reports-index.json").read_text(encoding="utf-8")
    )
    assert [entry["slug"] for entry in unchanged_index["runs"]] == [
        module.SLUG,
        "existing",
    ]
    assert "already curated" in capsys.readouterr().out
