"""Tests for the demo-video render pipeline (scripts/render_demo_video.py).

The pipeline turns a raw Playwright capture plus a timeline JSON into a
published demo cut: full-frame title/section cards between footage segments,
per-segment speed control, and burned-in caption pills.
"""

import importlib.util
import json
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


def test_final_duration_sums_cards_and_speed_adjusted_clips():
    # 2.0s card + 8.0s clip at 1x + 12.0s clip at 4x = 2 + 8 + 3 = 13.0
    assert rdv.final_duration(minimal_timeline()) == pytest.approx(13.0)


def test_final_duration_includes_clip_hold_time():
    timeline = minimal_timeline()
    timeline["segments"][1]["hold"] = 2.5
    # base 13.0 (see above) + the extra 2.5s frozen-frame hold
    assert rdv.final_duration(timeline) == pytest.approx(15.5)


def test_filtergraph_trims_speeds_concatenates_and_burns_text():
    graph = rdv.build_filtergraph(minimal_timeline())

    # Footage windows are trimmed and speed-adjusted.
    assert "trim=start=0.0:end=8.0" in graph
    assert "trim=start=8.0:end=20.0" in graph
    # PTS must be rebased to the trim, or a clip cut from deep in the source
    # keeps its huge original timestamps and corrupts the concat downstream.
    assert "(PTS-STARTPTS)/4.0" in graph
    # Every segment (2 clips + 1 card) joins one concat.
    assert "concat=n=3:v=1:a=0" in graph
    # Card text and the clip caption are burned in, caption as the
    # house-styled purple pill.
    assert "OpenELIS laboratory data" in graph
    assert rdv.drawtext_escape("The question is typed in plain language.") in graph
    assert "box=1" in graph
    assert "boxcolor=0x24133F" in graph


def test_clip_hold_freezes_the_final_frame_for_extra_seconds():
    timeline = minimal_timeline()
    timeline["segments"][1]["hold"] = 2.5
    graph = rdv.build_filtergraph(timeline)
    assert "tpad=stop_mode=clone:stop_duration=2.5" in graph


def test_clip_is_scaled_and_padded_to_the_timeline_canvas_size():
    graph = rdv.build_filtergraph(minimal_timeline(width=1280, height=720))
    assert "scale=1280:720" in graph
    assert "pad=1280:720" in graph


def test_card_renders_kicker_and_supporting_lines_below_heading():
    graph = rdv.build_filtergraph(minimal_timeline())
    assert rdv.drawtext_escape("CATALYST DEMO") in graph
    assert rdv.drawtext_escape("Plain-language question to checked SQL.") in graph


def test_build_command_uses_ffmpeg_bin_env_override(monkeypatch):
    monkeypatch.setenv("FFMPEG_BIN", "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")
    cmd = rdv.build_command(minimal_timeline(), source="raw.webm", output="out.mp4")
    assert cmd[0] == "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"


def test_build_command_produces_publishable_encode_settings():
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
    if shutil.which("ffmpeg") is None:
        return False
    listing = subprocess.run(
        ["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True
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


def test_drawtext_escape_neutralizes_ffmpeg_metacharacters():
    escaped = rdv.drawtext_escape("it's 100%: a,b[c];\\d")
    assert "\\'" in escaped
    assert "\\:" in escaped
    assert "\\%" in escaped
    assert "\\," in escaped
    assert "\\[" in escaped and "\\]" in escaped
    assert "\\;" in escaped
    assert "\\\\" in escaped
