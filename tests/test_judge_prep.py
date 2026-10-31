import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "judge_prep", ROOT / "scripts" / "judge-prep.py"
)
assert SPEC and SPEC.loader
judge_prep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(judge_prep)


def test_in_depth_artifact_reads_hub_native_product_envelope():
    response = {
        "inDepth": {
            "status": "complete",
            "answer": "A checked background claim [2].",
            "validation": {"mode": "enforce", "status": "checked"},
        }
    }

    artifact = judge_prep.in_depth_artifact({}, response, "legacy combined text")

    assert artifact == {
        "answer": "A checked background claim [2].",
        "status": "complete",
        "validation": {"mode": "enforce", "status": "checked"},
        "error": None,
        "latency_ms": None,
        "references": [],
        "citations": [],
        "source": "response.inDepth",
    }


def test_in_depth_artifact_preserves_withheld_product_status_without_content():
    response = {
        "inDepth": {
            "status": "needs_review",
            "answer": "",
            "error": "Every claim was rejected.",
            "validation": {"mode": "enforce", "status": "needs_review"},
        }
    }

    artifact = judge_prep.in_depth_artifact({}, response, "")

    assert artifact["answer"] == ""
    assert artifact["status"] == "needs_review"
    assert artifact["validation"]["status"] == "needs_review"


def test_in_depth_artifact_retains_legacy_separate_call_compatibility():
    row = {
        "indepth": {
            "latency_ms": 1234,
            "response": {"answer": "Legacy background [3]."},
        }
    }

    artifact = judge_prep.in_depth_artifact(row, {}, "")

    assert artifact == {
        "answer": "Legacy background [3].",
        "status": None,
        "validation": None,
        "error": None,
        "latency_ms": 1234,
        "references": [],
        "citations": [],
        "source": "row.indepth",
    }


def test_in_depth_artifact_keeps_which_claims_the_checks_marked():
    response = {
        "inDepth": {
            "status": "complete",
            "answer": "- A claim [1].\n- A questioned claim [2]. *(Check: flagged on review.)*",
            "validation": {
                "status": "needs_review",
                "flagged": [],
                "marked": [2],
                "review_status": "flagged",
                "review_flagged": [2],
                "review_issues": "Claim 2 overstates record 2.",
            },
        }
    }

    artifact = judge_prep.in_depth_artifact({}, response, "")

    assert artifact["validation"]["marked"] == [2]
    assert artifact["validation"]["review_flagged"] == [2]
    assert judge_prep.validation_metadata(response["inDepth"]["validation"]) == {
        "status": "needs_review",
        "flagged": [],
        "marked": [2],
        "review_status": "flagged",
        "review_flagged": [2],
    }


def test_reference_date_comes_from_the_run_meta_then_the_run_event_never_a_guess(tmp_path):
    import json
    run = tmp_path / "run"
    run.mkdir()
    assert judge_prep.reference_date_of(run) is None
    (run / "events.jsonl").write_text(json.dumps({"event_type": "run", "reference_date": "2026-06-20"}) + "\n")
    assert judge_prep.reference_date_of(run) == "2026-06-20"
    (run / "run_meta.json").write_text(json.dumps({"reference_date": "2026-07-01"}))
    assert judge_prep.reference_date_of(run) == "2026-07-01"
