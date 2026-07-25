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
