from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_SOURCE = (ROOT / "scripts" / "validate-dashboard.py").read_text(
    encoding="utf-8"
)


def test_dashboard_shows_single_and_multi_actor_judgments_honestly():
    assert '<section><h2>Judged scores</h2><div id=judges></div></section>' in DASHBOARD_SOURCE
    assert "no judged score yet" in DASHBOARD_SOURCE
    assert "Score from one independent judge" in DASHBOARD_SOURCE
    assert "Combined = each cell averaged across independent judges" in DASHBOARD_SOURCE
    assert "(s.n_actors||0)>=1" in DASHBOARD_SOURCE
    assert "no multi-judge score yet" not in DASHBOARD_SOURCE
