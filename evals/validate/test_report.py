import json
import re
from pathlib import Path

from harness.validate.report import build_multi_report, build_report

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
    body = re.search(
        r"<script type='application/json' id='report-data'>(.*?)</script>", html, re.DOTALL
    ).group(1)
    cells = json.loads(body)["runs"][0]["scenarios"][0]["turns"][0]["cells"]

    # The fallback envelope is flagged degraded via the precomputed boolean (the JS
    # keys the ⚠ chip on it); the real gemma answer is not. The chip HTML is emitted
    # exactly once across the run.
    assert cells["med-agent-team"]["degraded"] is True
    assert cells["gemma-local"]["degraded"] is False
    assert "⚠ degraded" in html
    assert html.count("⚠ degraded") == 1


def test_report_has_pdf_button_print_styles_and_feedback_seam(tmp_path):
    # Publishing additions: a "Download PDF" button wired to window.print(), a @media print
    # stylesheet (so the saved-PDF drops the interactive controls), and a feedback-capture seam —
    # an optional FEEDBACK_ENDPOINT + submit() that POSTs when set, else keeps the existing
    # client-side download. Red without the additions: none of these strings are in the HTML yet.
    run_dir = tmp_path / "run"
    _write_run(run_dir, [_result("gemma-local", "Lisinopril 10 mg [1]",
                                  [{"index": 1, "resourceType": "MedicationRequest"}])])
    html = build_report(run_dir).read_text(encoding="utf-8")
    assert "id='print-pdf'" in html            # the PDF button
    assert "window.print()" in html            # wired to browser print/save-as-PDF
    assert "@media print" in html              # print stylesheet
    assert "FEEDBACK_ENDPOINT" in html         # feedback seam: optional endpoint
    assert "function submit(" in html          # POST-or-download helper
    assert "function download(" in html        # download kept as the fallback
    # the exports route THROUGH submit (so a configured endpoint actually captures them)
    assert "submit(out.join" in html                # collectFeedback -> submit
    assert "submit(JSON.stringify(payload" in html  # exportRankings -> submit


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
    # Answer markdown is rendered server-side into the inert JSON blob (the JS injects
    # it). Pull the blob; json.loads reverses the \\u003c embedding-escapes for free.
    body = re.search(
        r"<script type='application/json' id='report-data'>(.*?)</script>", html, re.DOTALL
    ).group(1)
    cells = json.loads(body)["runs"][0]["scenarios"][0]["turns"][0]["cells"]
    team = cells["med-agent-team"]["answer_html"]
    gemma = cells["gemma-local"]["answer_html"]

    # The bold **In Depth** header renders as a <strong> tag, and the raw "**In Depth**"
    # markdown is gone (not shown verbatim).
    assert "<strong>In Depth</strong>" in team
    assert "<strong>Answer</strong>" in team
    assert "**In Depth**" not in team
    assert "**Answer**" not in team
    # The ATX "## In Depth" heading renders as a real heading tag, not escaped text.
    assert "<h3>In Depth</h3>" in gemma
    assert "## In Depth" not in gemma


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
    # The rendered answer lives in the JSON blob; pull it (the blob carries the
    # answer already normalized, so the literal backslash-n is gone from answer_html).
    body = re.search(
        r"<script type='application/json' id='report-data'>(.*?)</script>", html, re.DOTALL
    ).group(1)
    ans = json.loads(body)["runs"][0]["scenarios"][0]["turns"][0]["cells"]["med-agent-team"]["answer_html"]
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
    # blocks[] tables are rendered server-side into blocks_html in the JSON blob.
    body = re.search(
        r"<script type='application/json' id='report-data'>(.*?)</script>", html, re.DOTALL
    ).group(1)
    blocks = json.loads(body)["runs"][0]["scenarios"][0]["turns"][0]["cells"]["med-agent-team"]["blocks_html"]

    # The block's title, column labels, and cell texts render. Key on block-specific
    # content (NOT a bare "<table") because the summary table exists already.
    assert "Medications Ordered" in blocks
    assert ">Medication</th>" in blocks
    assert ">Action</th>" in blocks
    assert "Lamivudine" in blocks
    assert "Nevirapine" in blocks
    # Cell-level chart-record refs render as ref chips inside the table cell.
    assert "<span class='ref'>[29]</span>" in blocks


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
    # Rendering is server-side (escape-FIRST), so the blob carries the model text
    # already escaped. Pull answer_html + blocks_html and assert no raw tag leaked.
    body = re.search(
        r"<script type='application/json' id='report-data'>(.*?)</script>", html, re.DOTALL
    ).group(1)
    cell = json.loads(body)["runs"][0]["scenarios"][0]["turns"][0]["cells"]["med-agent-team"]
    answer, blocks = cell["answer_html"], cell["blocks_html"]

    # No raw injected markup leaks from either channel; the chars come out escaped.
    assert "<script>x</script>" not in answer and "<script>x</script>" not in blocks
    assert "<b>now</b>" not in answer
    assert "&lt;script&gt;x&lt;/script&gt;" in blocks
    assert "&lt;b&gt;now&lt;/b&gt;" in answer
    assert "&amp;" in answer
    # The escaped ampersand in the column label survives too.
    assert "Labs &amp; Vitals" in blocks


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


def test_report_embeds_multiple_runs_with_run_selector(tmp_path):
    # build_multi_report embeds N runs as one blob; the run <select> gets one option
    # per run; the first run is the default active one.
    a = tmp_path / "runA"
    b = tmp_path / "runB"
    _write_run(a, [_result("gemma-local", "answer a", [])])
    _write_run(b, [_result("gemma-local", "answer b", [])])
    manifest_b = json.loads((b / "run_manifest.json").read_text(encoding="utf-8"))
    manifest_b["run_id"] = "r2"
    (b / "run_manifest.json").write_text(json.dumps(manifest_b), encoding="utf-8")

    html = build_multi_report([a, b], tmp_path / "multi.html").read_text(encoding="utf-8")
    body = re.search(
        r"<script type='application/json' id='report-data'>(.*?)</script>", html, re.DOTALL
    ).group(1)
    blob = json.loads(body)

    assert len(blob["runs"]) == 2
    assert blob["runs"][0]["run_id"] == "r1"
    assert blob["runs"][1]["run_id"] == "r2"
    # A run selector exists; the JS populates one option per DATA.runs entry.
    assert "<select id='run-select'>" in html


def test_report_blob_is_embedding_safe_against_script_breakout(tmp_path):
    # A model answer containing </script> must not break out of the inert JSON
    # <script> element. The blob is emitted with < > & neutralised to \\uXXXX, so no
    # literal </script> appears inside the report-data element, yet the blob
    # round-trips via json.loads (the escapes are JSON-valid).
    run_dir = tmp_path / "run"
    _write_run(run_dir, [
        _result("med-agent-team", "before </script><script>alert(1)</script> after", []),
    ])

    html = build_report(run_dir).read_text(encoding="utf-8")
    body = re.search(
        r"<script type='application/json' id='report-data'>(.*?)</script>", html, re.DOTALL
    ).group(1)
    # No raw "</script>" survives inside the data element (it would close it early).
    assert "</script>" not in body
    # And the blob still parses; the escapes reverse transparently to the raw text,
    # which the server-side escape-first render then neutralises into the answer.
    blob = json.loads(body)
    assert "&lt;/script&gt;" in blob["runs"][0]["scenarios"][0]["turns"][0]["cells"]["med-agent-team"]["answer_html"]
