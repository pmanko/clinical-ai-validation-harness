"""The provider interface reference is the one place both engine interfaces and the wire
vocabulary are written down. These tests keep it from drifting away from the code it describes:
every TurnEventType wire name and every hub SSE event the module maps must appear in the document,
and the document must name the OpenAI endpoints each hop uses."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "specs/artifacts/planning/openmrs-provider-interface-reference.md"
PROVIDER = ROOT / "targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/provider"


def _doc() -> str:
    assert DOC.is_file(), f"missing {DOC.relative_to(ROOT)}"
    return DOC.read_text(encoding="utf-8")


def test_every_turn_event_wire_name_is_documented():
    src = (PROVIDER / "TurnEventType.java").read_text(encoding="utf-8")
    wire_names = re.findall(r'^\s+[A-Z_]+\("([a-z_]+)"\)', src, re.M)
    assert len(wire_names) >= 10, wire_names
    doc = _doc()
    missing = [n for n in wire_names if f"`{n}`" not in doc]
    assert missing == [], f"TurnEventType wire names absent from the reference: {missing}"


def test_every_hub_sse_event_the_module_maps_is_documented():
    src = (PROVIDER / "HubClinicalAnswerProvider.java").read_text(encoding="utf-8")
    mapped = set(re.findall(r'case "([a-z_]+)":', src)) | {"error", "done"}
    assert {"answer_done", "answer_validation", "indepth_done"} <= mapped, mapped
    doc = _doc()
    missing = sorted(e for e in mapped if f"`{e}`" not in doc)
    assert missing == [], f"hub SSE events absent from the reference: {missing}"


def test_the_openai_endpoints_of_each_hop_are_named():
    doc = _doc()
    for endpoint in ("/v1/chat/completions", "/v1/models", "/tokenize", "/v1/chat/completions/input_tokens"):
        assert f"`{endpoint}`" in doc, endpoint
    for extension in ("patient", "request_id", "session", "require_product_profile", "context"):
        assert f"`{extension}`" in doc, extension
