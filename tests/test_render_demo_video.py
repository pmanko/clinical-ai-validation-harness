"""Tests for the demo-video render pipeline (scripts/render_demo_video.py).

The pipeline turns a raw Playwright capture plus a timeline JSON into a
published demo cut: full-frame title/section cards between footage segments,
per-segment speed control, and burned-in caption pills.
"""

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "render_demo_video", ROOT / "scripts" / "render_demo_video.py"
)
rdv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rdv)


def minimal_timeline(**overrides):
    timeline = {
        "width": 1280,
        "height": 720,
        "fps": 25,
        "segments": [
            {
                "type": "card",
                "duration": 2.0,
                "kicker": "CATALYST DEMO",
                "heading": "OpenELIS laboratory data",
                "lines": ["Plain-language question to checked SQL."],
            },
            {
                "type": "clip",
                "start": 0.0,
                "end": 8.0,
                "speed": 1.0,
                "caption": "The question is typed in plain language.",
            },
            {"type": "clip", "start": 8.0, "end": 20.0, "speed": 4.0},
        ],
    }
    timeline.update(overrides)
    return timeline


def test_validate_timeline_rejects_clip_whose_end_precedes_start():
    timeline = minimal_timeline()
    rdv.validate_timeline(timeline)  # the well-formed baseline passes

    timeline["segments"][1]["end"] = 0.0
    with pytest.raises(ValueError, match="end"):
        rdv.validate_timeline(timeline)


def test_validate_timeline_rejects_a_card_with_non_positive_duration():
    timeline = minimal_timeline()
    rdv.validate_timeline(timeline)  # the well-formed baseline passes

    timeline["segments"][0]["duration"] = 0.0
    with pytest.raises(ValueError, match="duration"):
        rdv.validate_timeline(timeline)


def test_final_duration_sums_cards_and_speed_adjusted_clips():
    # 2.0s card + 8.0s clip at 1x + 12.0s clip at 4x = 2 + 8 + 3 = 13.0
    assert rdv.final_duration(minimal_timeline()) == pytest.approx(13.0)


def test_final_duration_includes_clip_hold_time():
    timeline = minimal_timeline()
    timeline["segments"][1]["hold"] = 2.5
    # base 13.0 (see above) + the extra 2.5s frozen-frame hold
    assert rdv.final_duration(timeline) == pytest.approx(15.5)


def test_card_heading_is_written_to_a_textfile_and_referenced(tmp_path):
    graph = rdv.build_filtergraph(minimal_timeline(), tmp_path)
    assert "textfile=" in graph
    written = [p.read_text(encoding="utf-8") for p in tmp_path.glob("*.txt")]
    assert "OpenELIS laboratory data" in written


def test_filtergraph_trims_speeds_concatenates_and_burns_text(tmp_path):
    graph = rdv.build_filtergraph(minimal_timeline(), tmp_path)

    # Footage windows are trimmed and speed-adjusted.
    assert "trim=start=0.0:end=8.0" in graph
    assert "trim=start=8.0:end=20.0" in graph
    # PTS must be rebased to the trim, or a clip cut from deep in the source
    # keeps its huge original timestamps and corrupts the concat downstream.
    assert "(PTS-STARTPTS)/4.0" in graph
    # Every segment (2 clips + 1 card) joins one concat.
    assert "concat=n=3:v=1:a=0" in graph
    # The card heading is written to a plain textfile, not embedded inline.
    written = {p.read_text(encoding="utf-8") for p in tmp_path.glob("*.txt")}
    assert "OpenELIS laboratory data" in written
    # The clip caption is burned in as the house-styled purple pill, its
    # text written to a plain textfile like the card text above.
    assert "The question is typed in plain language." in written
    assert "box=1" in graph
    assert "boxcolor=0x24133F" in graph


def test_card_rule_is_centred_on_the_frame_not_on_itself(tmp_path):
    """Inside drawbox, `w` is the box's own width, not the frame's.

    Centring with x=(w-rule)/2 therefore evaluates to zero and pins the rule
    to the left edge -- which still renders, still encodes, and still ships,
    looking broken. Only an eye on the frame or this assertion catches it.
    """
    graph = rdv.build_filtergraph(minimal_timeline(), tmp_path)
    rule = next(part for part in graph.split(",") if part.startswith("drawbox="))
    assert "x=(iw-" in rule, f"rule is not centred on the frame: {rule}"


def test_card_fades_in_and_out_so_sections_do_not_blink(tmp_path):
    graph = rdv.build_filtergraph(minimal_timeline(), tmp_path)
    assert "fade=t=in:st=0:d=0.40" in graph
    # A 2.0s card with a 0.40s fade starts fading out at 1.60s.
    assert "fade=t=out:st=1.60:d=0.40" in graph


def test_caption_box_is_padded_away_from_its_text(tmp_path):
    """Without boxborderw the box is drawn tight against the glyphs."""
    graph = rdv.build_filtergraph(minimal_timeline(), tmp_path)
    assert "boxborderw=" in graph
    assert "boxborderw=0" not in graph


def test_clip_hold_freezes_the_final_frame_for_extra_seconds(tmp_path):
    timeline = minimal_timeline()
    timeline["segments"][1]["hold"] = 2.5
    graph = rdv.build_filtergraph(timeline, tmp_path)
    assert "tpad=stop_mode=clone:stop_duration=2.5" in graph


def test_clip_is_scaled_and_padded_to_the_timeline_canvas_size(tmp_path):
    graph = rdv.build_filtergraph(minimal_timeline(width=1280, height=720), tmp_path)
    assert "scale=1280:720" in graph
    assert "pad=1280:720" in graph


def test_card_kicker_and_lines_are_written_to_textfiles_too(tmp_path):
    rdv.build_filtergraph(minimal_timeline(), tmp_path)
    written = {p.read_text(encoding="utf-8") for p in tmp_path.glob("*.txt")}
    assert "CATALYST DEMO" in written
    assert "Plain-language question to checked SQL." in written


def test_build_command_uses_ffmpeg_bin_env_override(monkeypatch):
    monkeypatch.setenv("FFMPEG_BIN", "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")
    cmd = rdv.build_command(minimal_timeline(), source="raw.webm", output="out.mp4")
    assert cmd[0] == "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"


def test_build_command_produces_publishable_encode_settings(monkeypatch):
    monkeypatch.delenv("FFMPEG_BIN", raising=False)
    timeline = minimal_timeline()
    cmd = rdv.build_command(timeline, source="raw.webm", output="out.mp4")

    assert cmd[0] == "ffmpeg"
    assert "raw.webm" in cmd
    assert cmd[-1] == "out.mp4"
    joined = " ".join(cmd)
    assert "-movflags +faststart" in joined
    assert "-an" in cmd
    assert "-pix_fmt yuv420p" in joined
    assert "libx264" in cmd


def _ffmpeg_has_drawtext() -> bool:
    binary = os.environ.get("FFMPEG_BIN", "ffmpeg")
    if shutil.which(binary) is None:
        return False
    listing = subprocess.run(
        [binary, "-hide_banner", "-filters"], capture_output=True, text=True
    ).stdout
    return "drawtext" in listing


@pytest.mark.skipif(
    not _ffmpeg_has_drawtext(),
    reason="ffmpeg lacks drawtext (needs a libfreetype build, e.g. ffmpeg-full)",
)
def test_smoke_render_produces_expected_duration_and_poster(tmp_path):
    source = tmp_path / "raw.mp4"
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-f", "lavfi",
            "-i", "testsrc=duration=6:size=320x180:rate=25",
            "-pix_fmt", "yuv420p", str(source),
        ],
        check=True,
    )
    timeline = {
        "width": 320,
        "height": 180,
        "fps": 25,
        "segments": [
            {"type": "card", "duration": 1.5, "heading": "Smoke demo"},
            {"type": "clip", "start": 0.0, "end": 4.0, "speed": 2.0, "caption": "sped up"},
        ],
    }
    timeline_path = tmp_path / "timeline.json"
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
    output = tmp_path / "out.mp4"
    poster = tmp_path / "poster.jpg"

    rdv.main(
        [
            str(timeline_path),
            "--source", str(source),
            "--output", str(output),
            "--poster", str(poster),
            "--poster-time", "1.7",
        ]
    )

    assert output.is_file() and poster.is_file()
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    # 1.5s card + 4.0s clip at 2x = 1.5 + 2.0 = 3.5s
    assert float(probe.stdout.strip()) == pytest.approx(3.5, abs=0.4)


@pytest.mark.skipif(
    not _ffmpeg_has_drawtext(),
    reason="ffmpeg lacks drawtext (needs a libfreetype build, e.g. ffmpeg-full)",
)
def test_smoke_render_survives_an_apostrophe_followed_by_another_segment(tmp_path):
    # A regression case: a card whose text contains an apostrophe, followed
    # by another chain in the same -filter_complex graph. A naive backslash
    # escape parses fine in isolation but corrupts ffmpeg's quote-nesting
    # state, breaking every chain that follows it.
    source = tmp_path / "raw.mp4"
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-f", "lavfi",
            "-i", "testsrc=duration=2:size=320x180:rate=25",
            "-pix_fmt", "yuv420p", str(source),
        ],
        check=True,
    )
    timeline = {
        "width": 320,
        "height": 180,
        "fps": 25,
        "segments": [
            {"type": "card", "duration": 1.0, "heading": "The patient's chart"},
            {"type": "card", "duration": 1.0, "heading": "A second card after it"},
        ],
    }
    output = tmp_path / "out.mp4"
    subprocess.run(rdv.build_command(timeline, source=str(source), output=str(output)), check=True)
    assert output.is_file()


def test_drawtext_escape_neutralizes_ffmpeg_metacharacters():
    # drawtext_escape only ever runs on a plain (unquoted) textfile path, so
    # it needs no quote handling — only the ffmpeg filtergraph
    # metacharacters that are special regardless of quoting.
    escaped = rdv.drawtext_escape("100%: a,b[c];\\d")
    assert "\\:" in escaped
    assert "\\%" in escaped
    assert "\\," in escaped
    assert "\\[" in escaped and "\\]" in escaped
    assert "\\;" in escaped
    assert "\\\\" in escaped
