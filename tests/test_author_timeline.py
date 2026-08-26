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


def test_an_unknown_clip_kind_is_rejected_instead_of_becoming_a_wait():
    plan = {
        "segments": [
            {
                "type": "clip",
                "from": "a",
                "to": "b",
                "kind": "waait",
                "target_seconds": 2.0,
            }
        ]
    }

    with pytest.raises(
        ValueError,
        match="clip 'kind' must be 'read' or 'wait'; got 'waait'",
    ):
        at.build_timeline(plan, milestones(a=0.0, b=10.0), video_duration=11.0)


@pytest.mark.parametrize(
    "plan",
    [{}, {"segments": None}, {"segments": {}}, {"segments": "clip"}, []],
    ids=["missing", "null", "object", "string", "non-object-plan"],
)
def test_plan_segments_must_be_a_list(plan):
    with pytest.raises(ValueError, match="plan 'segments' must be a list"):
        at.build_timeline(plan, milestones(a=0.0), video_duration=1.0)


def test_every_plan_segment_must_be_an_object():
    with pytest.raises(ValueError, match="segment 0 must be an object"):
        at.build_timeline(
            {"segments": [None]},
            milestones(a=0.0),
            video_duration=1.0,
        )


@pytest.mark.parametrize(
    "entry",
    [{"type": "caption"}, {}],
    ids=["unknown", "missing"],
)
def test_an_unknown_or_missing_segment_type_has_a_clear_error(entry):
    with pytest.raises(
        ValueError,
        match="segment 0: 'type' must be 'card' or 'clip'",
    ):
        at.build_timeline(
            {"segments": [entry]},
            milestones(a=0.0),
            video_duration=1.0,
        )


@pytest.mark.parametrize(
    "card",
    [
        {"type": "card"},
        {"type": "card", "duration": 0.0},
        {"type": "card", "duration": -1.0},
        {"type": "card", "duration": True},
        {"type": "card", "duration": "3"},
        {"type": "card", "duration": float("nan")},
        {"type": "card", "duration": float("inf")},
    ],
    ids=["missing", "zero", "negative", "boolean", "string", "nan", "infinity"],
)
def test_card_duration_must_be_a_positive_finite_number(card):
    with pytest.raises(
        ValueError,
        match="segment 0: card 'duration' must be a positive finite number",
    ):
        at.build_timeline(
            {"segments": [card]},
            milestones(a=0.0),
            video_duration=1.0,
        )


@pytest.mark.parametrize(
    ("entry", "missing"),
    [
        ({"type": "clip", "to": "b"}, "from"),
        ({"type": "clip", "from": "a"}, "to"),
    ],
)
def test_a_clip_missing_a_boundary_names_the_segment_and_key(entry, missing):
    with pytest.raises(
        ValueError,
        match=f"segment 0: clip requires 'from' and 'to'; missing '{missing}'",
    ):
        at.build_timeline(
            {"segments": [entry]},
            milestones(a=0.0, b=1.0),
            video_duration=2.0,
        )


@pytest.mark.parametrize(
    "target",
    [0.0, -1.0, True, "5", float("nan"), float("inf")],
    ids=["zero", "negative", "boolean", "string", "nan", "infinity"],
)
def test_an_explicit_invalid_wait_target_is_rejected(target):
    plan = {
        "segments": [
            {
                "type": "clip",
                "from": "a",
                "to": "b",
                "kind": "wait",
                "target_seconds": target,
            }
        ]
    }

    with pytest.raises(
        ValueError,
        match="clip 'target_seconds' must be a positive finite number",
    ):
        at.build_timeline(plan, milestones(a=0.0, b=10.0), video_duration=11.0)


def test_a_wait_without_a_target_remains_uncompressed():
    plan = {
        "segments": [
            {"type": "clip", "from": "a", "to": "b", "kind": "wait"}
        ]
    }

    timeline = at.build_timeline(
        plan, milestones(a=0.0, b=10.0), video_duration=11.0
    )

    assert timeline["segments"][0]["speed"] == 1.0


def test_cut_points_shift_by_the_recording_lead_in():
    """The capture duration minus testDuration estimates the clock offset."""
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


def test_a_clip_starting_after_the_capture_fails_with_the_milestone_named():
    plan = {
        "segments": [
            {"type": "clip", "from": "late", "to": "later", "kind": "read"}
        ]
    }
    data = milestones(late=5.0, later=8.0)

    with pytest.raises(
        ValueError,
        match=(
            "milestone 'late' starts at 5.00s, at or after the capture "
            "ends at 4.00s"
        ),
    ):
        at.build_timeline(plan, data, video_duration=4.0)


def test_a_clipped_wait_uses_only_the_footage_that_will_render():
    plan = {
        "segments": [
            {
                "type": "clip",
                "from": "start",
                "to": "finished",
                "kind": "wait",
                "target_seconds": 1.0,
            }
        ]
    }
    data = milestones(start=1.0, finished=20.0)

    timeline = at.build_timeline(plan, data, video_duration=5.0)

    clip = timeline["segments"][0]
    assert clip["start"] == 1.0
    assert clip["end"] == 5.0
    assert clip["speed"] == 4.0


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


def test_probe_duration_reads_the_length_ffprobe_reports(monkeypatch):
    """The lead-in is recovered from the capture's real duration, so a
    mis-read here would land every cut in the wrong place."""
    calls = {}

    class _Result:
        stdout = "162.36\n"

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        assert kwargs["check"] is True
        return _Result()

    monkeypatch.setattr(at.subprocess, "run", fake_run)

    assert at.probe_duration("/tmp/raw.webm") == 162.36
    assert calls["cmd"][0] == "ffprobe"
    assert calls["cmd"][-1] == "/tmp/raw.webm"


def _plan_and_milestones(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
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
                        "target_seconds": 5.0,
                        "caption": "Compressed.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    marks = tmp_path / "milestones.json"
    marks.write_text(json.dumps(milestones(a=1.0, b=41.0)), encoding="utf-8")
    return plan, marks


def test_the_cli_writes_a_timeline_and_reports_the_screen_time(
    tmp_path, monkeypatch, capsys
):
    plan, marks = _plan_and_milestones(tmp_path)
    source = tmp_path / "raw.webm"
    source.write_bytes(b"")
    out = tmp_path / "timeline.json"
    monkeypatch.setattr(at, "probe_duration", lambda _path: 43.0)
    monkeypatch.setattr(
        "sys.argv",
        [
            "author_timeline.py",
            str(plan),
            "--milestones",
            str(marks),
            "--source",
            str(source),
            "--output",
            str(out)],
    )

    at.main()

    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["width"] == 1280
    assert [segment["type"] for segment in written["segments"]] == ["card", "clip"]
    # 40s of waiting compressed toward 5s, plus a 3s card.
    assert written["segments"][1]["speed"] == 8.0
    printed = capsys.readouterr().out
    assert str(out) in printed
    assert "1 cards, 1 clips" in printed
    # Minutes floor rather than round: 8s of screen time is 0:08.0, never 1:xx.
    assert "0:08.0 on screen" in printed
