import json
import re
from pathlib import Path

from harness.validate.report import build_report

_DEGRADED_ANSWER = "I could not produce a complete answer for this turn. Please try again."


def _write_run(run_dir: Path, results):
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps({
            "run_id": "r1", "component": "validate", "git_sha": "abc123",
            "dataset_id": "demo", "otel": {"gen_ai.provider.name": "lmstudio"},
            "generated_at": "2026-05-30",
        }),
        encoding="utf-8",
    )
    (run_dir / "events.jsonl").write_text(
        json.dumps({"event_type": "backend_selected", "backend_id": "med-agent-team",
                    "modelName": "med-agent-team"}) + "\n"
        + json.dumps({"event_type": "backend_selected", "backend_id": "gemma-local",
                      "modelName": "gemma-4-e2b-it"}) + "\n",
        encoding="utf-8",
    )
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")


def _result(backend, answer, refs, **metrics):
    base = {"latency_ms": 10, "http_status": 200, "json_valid": True,
            "citation_count": len(refs), "references_empty": not refs, "first_turn": True}
    base.update(metrics)
    return {"run_id": "r1", "scenario_id": "s", "backend_id": backend, "turn": 1,
            "request": {"question": "q"}, "response": {"answer": answer, "references": refs},
            "metrics": base}


def test_report_flags_the_degraded_fallback_envelope(tmp_path):
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team", _DEGRADED_ANSWER, []),
        _result("gemma-local", "Lisinopril 10 mg [1]",
                [{"index": 1, "resourceType": "MedicationRequest"}]),
    ])

    html = build_report(run_dir).read_text(encoding="utf-8")

    # The team's graceful-fallback envelope (200/valid/0-cites) is flagged degraded
    # exactly once; the real gemma answer is not.
    assert "⚠ degraded" in html
    assert html.count("⚠ degraded") == 1


def test_report_renders_markdown_answer_headings_as_html(tmp_path):
    # v2 synthesis emits the answer as two **bold** markdown headers (per
    # targets/med-agent-hub/server/prompts/v2/synthesis.txt). The task also calls
    # out a `## In Depth` ATX heading. Both must render as real HTML, not show as
    # escaped literal text (today report.py html-escapes the whole answer and
    # white-space:pre-wrap leaves the markdown syntax visible).
    bold_answer = "**Answer**\nHer regimen is no longer first-line [4].\n\n**In Depth**\nThe chart lists a stavudine-based regimen [4]."
    atx_answer = "## In Depth\nGuidance per WHO HIV.\n\nMore detail here."
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team", bold_answer,
                [{"index": 4, "resourceType": "MedicationRequest"}]),
        _result("gemma-local", atx_answer, []),
    ])

    html = build_report(run_dir).read_text(encoding="utf-8")

    # The bold **In Depth** header renders as a <strong> tag, and the raw "**In Depth**"
    # markdown is gone (not shown verbatim).
    assert "<strong>In Depth</strong>" in html
    assert "<strong>Answer</strong>" in html
    assert "**In Depth**" not in html
    assert "**Answer**" not in html
    # The ATX "## In Depth" heading renders as a real heading tag, not escaped text.
    assert "<h3>In Depth</h3>" in html
    assert "## In Depth" not in html


def test_report_normalizes_literal_backslash_n_in_answer(tmp_path):
    # The v2 synthesis prompt's worked examples write their section breaks as a
    # literal backslash-n (JSON-string escaping shown to the model:
    # targets/med-agent-hub/server/prompts/v2/synthesis.txt lines 9, 17). A 4B
    # model frequently copies that escaping verbatim, so a real answer can carry a
    # literal two-char backslash-n. The renderer must normalize it to a true line
    # break — otherwise the visible "\n" garbage masquerades as a v2 quality delta
    # and confounds the A/B. (Python "\\n" -> one backslash + n; json round-trip in
    # _write_run preserves it as the literal two chars.)
    answer = "**Answer**\\nbottom line [4].\\n\\n**In Depth**\\nstavudine regimen [4]."
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team", answer,
                [{"index": 4, "resourceType": "MedicationRequest"}]),
    ])

    html = build_report(run_dir).read_text(encoding="utf-8")

    # Scope to the answer div — the report's own client-side <script> legitimately
    # contains a backslash-n in JS string literals; we only care about the answer.
    ans = re.search(r"<div class='ans'>(.*?)</div>", html, re.DOTALL).group(1)
    # The bold headers still render (the literal-\n didn't block the ** pass) and the
    # literal backslash-n two-char sequence is gone from the answer (normalized to a
    # real newline, which pre-wrap renders as a line break).
    assert "<strong>In Depth</strong>" in ans
    assert "\\n" not in ans


# The real medications-table block the bridge returns (copied from an actual run:
# artifacts/validate/21b42fd5-.../results.jsonl). A fixture simpler than reality
# would pass green while real nested cells/refs break, so keep the full shape.
_MED_BLOCK = {
    "kind": "table",
    "title": "Medications Ordered",
    "columns": [
        {"key": "medication", "label": "Medication"},
        {"key": "action", "label": "Action"},
        {"key": "urgency", "label": "Urgency"},
    ],
    "rows": [
        {"cells": {
            "medication": {"text": "Lamivudine", "refs": [29, 62, 117]},
            "action": {"text": "NEW", "refs": [29, 62]},
            "urgency": {"text": "ROUTINE", "refs": [29]},
        }},
        {"cells": {
            "medication": {"text": "Nevirapine", "refs": [30, 63]},
            "action": {"text": "NEW", "refs": [30]},
            "urgency": {"text": "ROUTINE", "refs": [30]},
        }},
    ],
}


def test_report_renders_blocks_table_with_cells_and_refs(tmp_path):
    # The bridge returns enumerations (med lists, labs) as a blocks[] table that
    # report.py currently DROPS entirely (it reads only response.answer +
    # response.references). Render each table block as an HTML <table>.
    run_dir = tmp_path / "run"
    r = _result("med-agent-team", "See medications table.",
                [{"index": 29, "resourceType": "MedicationRequest"}])
    r["response"]["blocks"] = [_MED_BLOCK]
    _write_run(run_dir, [r])

    html = build_report(run_dir).read_text(encoding="utf-8")

    # The block's title, column labels, and cell texts render. Key on block-specific
    # content (NOT a bare "<table") because the summary/grid tables exist already.
    assert "Medications Ordered" in html
    assert ">Medication</th>" in html
    assert ">Action</th>" in html
    assert "Lamivudine" in html
    assert "Nevirapine" in html
    # Cell-level chart-record refs render as ref chips inside the table cell.
    assert "<span class='ref'>[29]</span>" in html


def test_report_escapes_untrusted_text_in_answer_and_blocks(tmp_path):
    # The renderer escapes FIRST then upgrades markdown, so model text can never
    # inject markup. Guards against a future reorder to format-before-escape, which
    # would let a "<" in the answer or a cell open a real tag. (red-when-broken:
    # flip the order in _render_answer/_render_blocks and the raw tag leaks.)
    block = {
        "kind": "table", "title": "Labs & Vitals",
        "columns": [{"key": "name", "label": "Test"}],
        "rows": [{"cells": {"name": {"text": "CD4 <script>x</script> & co", "refs": [7]}}}],
    }
    run_dir = tmp_path / "run"
    r = _result("med-agent-team", "Result is 5 < 10 & rising <b>now</b>.", [])
    r["response"]["blocks"] = [block]
    _write_run(run_dir, [r])

    html = build_report(run_dir).read_text(encoding="utf-8")

    # No raw injected markup leaks from either channel. Match the exact injected
    # payloads (the report's OWN trailing <script>const RUN_ID...> is legitimate and
    # must not trip this); the chars come out escaped instead.
    assert "<script>x</script>" not in html
    assert "<b>now</b>" not in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "&lt;b&gt;now&lt;/b&gt;" in html
    assert "&amp;" in html
    # The escaped ampersand in the column label survives too.
    assert "Labs &amp; Vitals" in html


def test_report_omits_citation_zero_abstention_proxy(tmp_path):
    # citation_count==0 is NOT an abstention signal — it inverts on safety turns
    # where the correct answer cites an external guideline by free-text (0 chart
    # refs). The report must NOT render the '∅ no refs' chip or a 'no-refs turns'
    # summary column (both were a references_empty proxy the code itself disclaimed).
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team", "Stavudine is no longer first-line per WHO guidance.", []),
    ])

    html = build_report(run_dir).read_text(encoding="utf-8")

    assert "no refs" not in html        # the '∅ no refs' chip is gone
    assert "∅" not in html
    assert "no-refs turns" not in html  # the summary column is gone


def test_report_labels_citation_count_as_chart_refs_not_grounding(tmp_path):
    # A citation COUNT is not a grounding/quality signal — the chip + summary column
    # must read 'chart refs', never 'cites'/'citations' (which imply grounding).
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("gemma-local", "Lisinopril [1]", [{"index": 1, "resourceType": "MedicationRequest"}]),
    ])

    html = build_report(run_dir).read_text(encoding="utf-8")

    assert "chart refs" in html           # relabeled chip + summary header
    assert "cites " not in html           # old misleading chip label gone
    assert "total citations" not in html  # old summary header gone


def test_report_surfaces_backend_config_label(tmp_path):
    # Columns must be self-describing: the per-backend config (prompt variant +
    # orchestrator/expert models), carried in the backend_selected event's `label`,
    # must render — otherwise two team backends with identical modelName are
    # indistinguishable in the report (the exact gap the prior run hit).
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team-c", "ans c", []),
        _result("med-agent-team-d", "ans d", []),
    ])
    # backend_selected events carry the config label (what the runner will emit).
    (run_dir / "events.jsonl").write_text(
        json.dumps({"event_type": "backend_selected", "backend_id": "med-agent-team-c",
                    "modelName": "med-agent-team",
                    "label": "v2 prompt | orch=gemma-4-31b | expert=medgemma-1.5-4b"}) + "\n"
        + json.dumps({"event_type": "backend_selected", "backend_id": "med-agent-team-d",
                      "modelName": "med-agent-team",
                      "label": "v2 prompt | orch=gemma-4-31b | expert=medgemma-27b"}) + "\n",
        encoding="utf-8",
    )

    html = build_report(run_dir).read_text(encoding="utf-8")

    # Both configs render, so the two same-model team columns are distinguishable.
    assert "orch=gemma-4-31b | expert=medgemma-1.5-4b" in html
    assert "orch=gemma-4-31b | expert=medgemma-27b" in html
