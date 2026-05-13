from pathlib import Path

from harness.compose import detect_compose_conflicts


def test_detect_compose_conflicts_on_clashing_mysql_image(tmp_path: Path) -> None:
    harness = tmp_path / "harness.yml"
    harness.write_text(
        "services:\n  mysql:\n    image: mysql:8.0\n    ports:\n      - \"3307:3306\"\n",
        encoding="utf-8",
    )
    target = tmp_path / "target.yml"
    target.write_text(
        "services:\n  mysql:\n    image: mysql:5.7\n    ports:\n      - \"3307:3306\"\n",
        encoding="utf-8",
    )
    msgs = detect_compose_conflicts([harness], [("openmrs_chatbot", target)])
    assert any("mysql" in m and "image" in m for m in msgs)


def test_detect_compose_conflicts_on_clashing_ports_same_image(tmp_path: Path) -> None:
    harness = tmp_path / "harness.yml"
    harness.write_text(
        "services:\n  mysql:\n    image: mysql:8.0\n    ports:\n      - \"3307:3306\"\n",
        encoding="utf-8",
    )
    target = tmp_path / "target.yml"
    target.write_text(
        "services:\n  mysql:\n    image: mysql:8.0\n    ports:\n      - \"3308:3306\"\n",
        encoding="utf-8",
    )
    msgs = detect_compose_conflicts([harness], [("querystore", target)])
    assert any("ports" in m for m in msgs)
