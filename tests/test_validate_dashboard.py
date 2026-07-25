from pathlib import Path
import json
import subprocess


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


def test_dashboard_keeps_flagged_model_output_visible_for_manual_review():
    assert "confidence inversion" not in DASHBOARD_SOURCE
    assert "Removed In-Depth claims" in DASHBOARD_SOURCE
    assert "not part of the final clinical response" in DASHBOARD_SOURCE
    assert "<details open class=reviewdraft>" not in DASHBOARD_SOURCE
    assert "function indepthReviewDraft" not in DASHBOARD_SOURCE
    assert "const draft=(t.review_draft||'').trim()" in DASHBOARD_SOURCE
    assert "renderOriginalAnswer(validation,currentAnswer)" in DASHBOARD_SOURCE
    assert "current answer above remains flagged for review" in DASHBOARD_SOURCE
    assert "Original-answer sources (not final evidence)" in DASHBOARD_SOURCE
    assert '"answer_confidence_display": answer_confidence_display' in DASHBOARD_SOURCE
    assert "const answerConf=t.answer_confidence_display" in DASHBOARD_SOURCE
    assert "<details class=collapse><summary>show '+title.toLowerCase()" not in DASHBOARD_SOURCE


def test_dashboard_renderer_shows_flagged_output_and_citation_only_original():
    esc_line = "const esc=" + DASHBOARD_SOURCE.split("const esc=", 1)[1].split("\n", 1)[0]
    confidence_js = DASHBOARD_SOURCE[
        DASHBOARD_SOURCE.index("const CONF_COLORS=") : DASHBOARD_SOURCE.index(
            "function renderReviewDraft"
        )
    ]
    original_js = DASHBOARD_SOURCE[
        DASHBOARD_SOURCE.index("function renderOriginalAnswer") : DASHBOARD_SOURCE.index(
            "function renderTrace"
        )
    ]
    script = f"""
{esc_line}
{confidence_js}
const renderBlocks=()=>'';
{original_js}
const flagged=confSection(
  'Answer',
  'Flagged model output [1].',
  {{level:'red',label:'Self-check low',note:'Check the date.',note_treatment:'prominent'}},
  {{status:'needs_review',label:'Needs review',tone:'danger'}}
);
const original=renderOriginalAnswer(
  {{status:'edited',originalAnswer:'Flagged model output [1].',originalReferences:[{{index:1}}]}},
  'Flagged model output [1].'
);
process.stdout.write(JSON.stringify({{flagged,original}}));
"""
    rendered = json.loads(subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    ).stdout)

    assert "Check the date." in rendered["flagged"]
    assert "Flagged model output [1]." in rendered["flagged"]
    assert "<details" not in rendered["flagged"]
    assert "show answer" not in rendered["flagged"].lower()
    assert rendered["flagged"].index("Check the date.") < rendered["flagged"].index(
        "Flagged model output [1]."
    )
    assert "Original model answer" in rendered["original"]
    assert "answer or its supporting citations was changed" in rendered["original"]
