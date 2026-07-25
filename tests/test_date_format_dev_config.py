from pathlib import Path
import importlib.util
import json


ROOT = Path(__file__).resolve().parents[1]


def test_date_format_analyzer_separates_malformed_dates_from_localized_citations():
    spec = importlib.util.spec_from_file_location(
        "analyze_date_format_run", ROOT / "scripts" / "analyze-date-format-run.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    text = "Good 2026-01-07, bad D2025_11_09 and 2025-11_12, citation [ ٣٦ ]."
    assert mod._bad_date_hits(text) == ["2025-11_12", "D2025_11_09"]
    assert mod.LOCALIZED_DIGIT_RE.findall(text) == ["٣٦"]

    ugly = "bad 2025-10-//13, 2026-0-[59], 2026-02, 2006\u201105\u201118."
    assert mod._bad_date_hits(ugly) == [
        "2006\u201105\u201118",
        "2025-10-//13",
        "2026-0-[59]",
        "2026-02",
    ]


def test_date_format_analyzer_main_reports_dates_and_gate(tmp_path, capsys):
    spec = importlib.util.spec_from_file_location(
        "analyze_date_format_run", ROOT / "scripts" / "analyze-date-format-run.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    run = tmp_path / "run"
    run.mkdir()
    rows = [
        {
            "scenario_id": "s1",
            "backend_id": "b1",
            "response": {
                "answer": "Weight was written as D2025_11_09 and citation [ ٣٦ ].",
                "blocks": [{
                    "kind": "table",
                    "rows": [{"cells": {"date": {"text": "2025-11_12", "refs": [1]}}}],
                }],
            },
        },
        {"scenario_id": "s2", "backend_id": "b2", "response": "plain 205-12-31"},
    ]
    (run / "results.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    report_data = {
        "runs": [{
            "scenarios": [{
                "scenario_id": "s1",
                "turns": [{
                    "cells": {
                        "b1": {
                            "temporal_gate": {
                                "status": "fail",
                                "applied": "patch",
                                "checks": [
                                    {"id": "date_format", "status": "fail", "reason": "bad date"},
                                    {"id": "window_scope", "status": "warn", "reason": "strict window"},
                                    {"id": "already_ok", "status": "pass", "reason": "ignore"},
                                ],
                            }
                        }
                    }
                }],
            }]
        }]
    }
    (run / "report.html").write_text(
        "<script type='application/json' id='report-data'>"
        + json.dumps(report_data)
        + "</script>",
        encoding="utf-8",
    )

    assert mod.main(["analyze-date-format-run.py", str(run)]) == 0
    out = capsys.readouterr().out
    assert "run: run" in out
    assert "D2025_11_09" in out
    assert "2025-11_12" in out
    assert "Localized non-ASCII digit hits" in out
    assert "Temporal gate" in out
    assert "date_format" in out
    assert "bad date" in out
