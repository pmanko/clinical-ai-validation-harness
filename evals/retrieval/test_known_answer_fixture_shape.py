from pathlib import Path

import yaml


def test_known_answer_fixture_has_cases() -> None:
    fixture = Path("datasets/fixtures/known_answer_cases.yaml")
    payload = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    assert payload["version"]
    assert len(payload["cases"]) >= 1
