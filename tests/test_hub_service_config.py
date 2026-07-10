from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_querystore_credentials_have_no_privileged_compose_defaults():
    compose = (ROOT / "compose/openmrs-2.8-refapp.yml").read_text(encoding="utf-8")

    assert "QUERYSTORE_BASE_URL: ${QUERYSTORE_BASE_URL:-}" in compose
    assert "QUERYSTORE_USERNAME: ${QUERYSTORE_USERNAME:-}" in compose
    assert "QUERYSTORE_PASSWORD: ${QUERYSTORE_PASSWORD:-}" in compose
    assert "QUERYSTORE_USERNAME:-admin" not in compose
    assert "QUERYSTORE_PASSWORD:-Admin123" not in compose


def test_chartsearch_example_documents_explicit_least_privileged_querystore_auth():
    example = (ROOT / ".env.chartsearch.example").read_text(encoding="utf-8")

    assert "QUERYSTORE_BASE_URL=" in example
    assert "QUERYSTORE_USERNAME=" in example
    assert "QUERYSTORE_PASSWORD=" in example
    assert "Get Patients" in example
    assert "least-privileged" in example
