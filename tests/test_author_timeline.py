"""Tests for timeline authoring (scripts/author_timeline.py).

The spec records when each beat of a demo actually happened; this turns those
measurements plus a plan of cards and captions into a renderable timeline, so
cut points come from the clock rather than from scrubbing the capture by eye.
"""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "author_timeline", ROOT / "scripts" / "author_timeline.py"
)
at = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(at)


def milestones(**marks):
    ordered = sorted(marks.items(), key=lambda item: item[1])
    return {
        "name": "demo",
        "testDuration": max(marks.values()) + 1.0,
        "marks": [{"label": label, "at": at_} for label, at_ in ordered],
    }


def test_a_wait_compresses_and_a_read_stays_at_real_speed():
    plan = {
        "segments": [
            {"type": "clip", "from": "typed", "to": "generating", "kind": "read"},
            {
                "type": "clip",
                "from": "generating",
                "to": "sql",
                "kind": "wait",
                "target_seconds": 6.0,
            },
        ]
    }
    data = milestones(typed=2.0, generating=8.0, sql=38.0)

    timeline = at.build_timeline(plan, data, video_duration=data["testDuration"])

    read, wait = timeline["segments"]
    assert read["speed"] == 1.0
    # 30s of generation into 6s of screen time, comfortably under the cap.
    assert wait["speed"] == 5.0


def test_no_wait_is_compressed_past_the_believability_cap():
    plan = {
        "segments": [
            {
                "type": "clip",
                "from": "a",
                "to": "b",
                "kind": "wait",
                "target_seconds": 1.0,
            }
        ]
    }
    data = milestones(a=0.0, b=400.0)

    timeline = at.build_timeline(plan, data, video_duration=401.0)

    # 400x would be a hard cut; the viewer must still see work happening.
    assert timeline["segments"][0]["speed"] == at.MAX_SPEED


def test_a_short_wait_is_left_alone():
    plan = {
        "segments": [
            {
                "type": "clip",
                "from": "a",
                "to": "b",
                "kind": "wait",
                "target_seconds": 1.0,
            }
        ]
    }
    data = milestones(a=0.0, b=2.0)

    timeline = at.build_timeline(plan, data, video_duration=3.0)

    assert timeline["segments"][0]["speed"] == 1.0


def test_cut_points_shift_by_the_recording_lead_in():
    """Playwright starts recording before the test body runs, so video time is
    milestone time plus a constant — recovered, not assumed."""
    plan = {"segments": [{"type": "clip", "from": "a", "to": "b", "kind": "read"}]}
    data = milestones(a=1.0, b=5.0)  # testDuration 6.0

    timeline = at.build_timeline(plan, data, video_duration=8.5)

    # 2.5s of lead-in before the first action.
    assert timeline["segments"][0]["start"] == 3.5
    assert timeline["segments"][0]["end"] == 7.5


def test_a_capture_shorter_than_the_run_never_shifts_cuts_backwards():
    plan = {"segments": [{"type": "clip", "from": "a", "to": "b", "kind": "read"}]}
    data = milestones(a=1.0, b=5.0)

    timeline = at.build_timeline(plan, data, video_duration=4.0)

    assert timeline["segments"][0]["start"] == 1.0
    # A clip can never run past the end of the footage.
    assert timeline["segments"][0]["end"] == 4.0


def test_cards_and_captions_pass_through_untouched():
    plan = {
        "width": 1280,
        "footer": "openclinai.org",
        "segments": [
            {
                "type": "card",
                "duration": 3.0,
                "kicker": "CATALYST",
                "heading": "A question becomes SQL",
            },
            {
                "type": "clip",
                "from": "a",
                "to": "b",
                "kind": "read",
                "caption": "The draft is SQL you can read.",
            },
        ],
    }
    data = milestones(a=0.0, b=4.0)

    timeline = at.build_timeline(plan, data, video_duration=5.0)

    assert timeline["width"] == 1280
    assert timeline["footer"] == "openclinai.org"
    assert timeline["segments"][0] == plan["segments"][0]
    assert timeline["segments"][1]["caption"] == "The draft is SQL you can read."
    # The authored clip carries no plan-only keys into the renderer.
    assert "from" not in timeline["segments"][1]
    assert "kind" not in timeline["segments"][1]


def test_a_missing_milestone_is_named_not_silently_skipped():
    plan = {"segments": [{"type": "clip", "from": "a", "to": "never", "kind": "read"}]}

    with pytest.raises(ValueError, match="'never' was never recorded"):
        at.build_timeline(plan, milestones(a=0.0), video_duration=2.0)


def test_milestones_out_of_order_are_rejected():
    """A span whose end precedes its start would render as an empty clip."""
    plan = {"segments": [{"type": "clip", "from": "b", "to": "a", "kind": "read"}]}

    with pytest.raises(ValueError, match="does not follow"):
        at.build_timeline(plan, milestones(a=1.0, b=5.0), video_duration=6.0)


def test_the_authored_timeline_renders():
    """What this writes must be what the renderer accepts."""
    render_spec = importlib.util.spec_from_file_location(
        "render_demo_video", ROOT / "scripts" / "render_demo_video.py"
    )
    rdv = importlib.util.module_from_spec(render_spec)
    render_spec.loader.exec_module(rdv)

    plan = {
        "width": 1280,
        "height": 720,
        "fps": 25,
        "segments": [
            {"type": "card", "duration": 3.0, "heading": "Section"},
            {
                "type": "clip",
                "from": "a",
                "to": "b",
                "kind": "wait",
                "target_seconds": 4.0,
            },
        ],
    }
    timeline = at.build_timeline(
        plan, milestones(a=0.0, b=40.0), video_duration=41.0
    )

    rdv.validate_timeline(timeline)
    assert rdv.final_duration(timeline) > 3.0
