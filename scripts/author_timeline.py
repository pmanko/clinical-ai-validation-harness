#!/usr/bin/env python3
"""Author a demo-video timeline from measured milestones.

`demo-milestones.ts` records when each beat of a demo actually happened, so a
cut can be paced from measurement instead of by scrubbing the capture by
hand -- but the half that consumed those numbers was never written, and the
recording guide's "note the wall-clock second of each turn boundary" put the
eyeballing back. This is that missing half.

Two facts make it more than arithmetic:

* Playwright starts recording at *context creation*, marginally before the
  test body runs, so video time is milestone time plus a small constant. That
  constant is recovered from the rendered capture's duration rather than
  assumed to be zero: the last milestone should land at the end of the video,
  and whatever is left over is the lead-in.
* A span between two milestones is either something a viewer must read
  (typing, SQL, a result table) or something they must merely believe is
  happening (a model generating). The plan below labels each span, and the
  labels decide the speed -- reading stays at 1x, waiting compresses.

Usage:
    python3 scripts/author_timeline.py PLAN.json \
        --milestones demo-milestones/full-scenario-demo.json \
        --source /tmp/full-scenario-raw.webm \
        --output timeline.json

The plan names the cards and captions; the milestones supply every number.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

# A wait compressed past this reads as a hard cut -- the viewer stops
# believing the system did any work. Nothing is sped up beyond it.
MAX_SPEED = 8.0
# Below this a "wait" is not worth compressing; leave it alone.
MIN_COMPRESSIBLE_SECONDS = 4.0


def probe_duration(path: str | Path) -> float:
    """Length of a media file in seconds, via ffprobe."""
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def marks_by_label(milestones: dict[str, Any]) -> dict[str, float]:
    return {mark["label"]: float(mark["at"]) for mark in milestones["marks"]}


def recording_offset(milestones: dict[str, Any], video_duration: float) -> float:
    """Seconds of video before the test body's first action.

    The capture starts at context creation and ends after the last milestone
    plus teardown, so the lead-in is what the video has that the test clock
    does not. Never negative: a shorter video than test run means the capture
    was cut short, and shifting backwards would land every cut in the wrong
    place.
    """
    test_duration = float(milestones["testDuration"])
    return max(0.0, video_duration - test_duration)


def resolve_span(
    marks: dict[str, float],
    start_label: str,
    end_label: str,
    offset: float,
) -> tuple[float, float]:
    """Video-time (start, end) for the span between two milestones."""
    for label in (start_label, end_label):
        if label not in marks:
            raise ValueError(f"milestone {label!r} was never recorded")
    start, end = marks[start_label] + offset, marks[end_label] + offset
    if end <= start:
        raise ValueError(
            f"milestone {end_label!r} ({end:.2f}s) does not follow "
            f"{start_label!r} ({start:.2f}s)"
        )
    return start, end


def speed_for(span_seconds: float, kind: str, target: float | None) -> float:
    """How fast to play a span.

    `read` spans always play at 1x. `wait` spans compress toward `target`
    seconds of screen time, bounded by MAX_SPEED, and are left alone when
    they are already short.
    """
    if kind == "read":
        return 1.0
    if span_seconds < MIN_COMPRESSIBLE_SECONDS or not target:
        return 1.0
    return min(MAX_SPEED, max(1.0, span_seconds / target))


def build_timeline(
    plan: dict[str, Any],
    milestones: dict[str, Any],
    video_duration: float,
) -> dict[str, Any]:
    """Turn a plan plus measured milestones into a renderable timeline."""
    marks = marks_by_label(milestones)
    offset = recording_offset(milestones, video_duration)
    segments: list[dict[str, Any]] = []
    for entry in plan["segments"]:
        if entry["type"] == "card":
            segments.append({k: v for k, v in entry.items()})
            continue
        start, end = resolve_span(marks, entry["from"], entry["to"], offset)
        kind = entry.get("kind", "read")
        clipped_end = min(end, video_duration)
        if start >= clipped_end:
            raise ValueError(
                f"milestone {entry['from']!r} starts at {start:.2f}s, "
                f"at or after the capture ends at {video_duration:.2f}s"
            )
        clip: dict[str, Any] = {
            "type": "clip",
            "start": round(start, 2),
            "end": round(clipped_end, 2),
            "speed": round(
                speed_for(
                    clipped_end - start,
                    kind,
                    entry.get("target_seconds"),
                ),
                2,
            ),
        }
        if entry.get("caption"):
            clip["caption"] = entry["caption"]
        segments.append(clip)
    return {
        **{k: v for k, v in plan.items() if k != "segments"},
        "segments": segments,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, help="cards + captions + span kinds")
    parser.add_argument("--milestones", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True, help="raw capture")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    milestones = json.loads(args.milestones.read_text(encoding="utf-8"))
    timeline = build_timeline(plan, milestones, probe_duration(args.source))
    args.output.write_text(json.dumps(timeline, indent=2) + "\n", encoding="utf-8")

    clips = [s for s in timeline["segments"] if s["type"] == "clip"]
    cards = [s for s in timeline["segments"] if s["type"] == "card"]
    screen = sum(s["duration"] for s in cards) + sum(
        (s["end"] - s["start"]) / s["speed"] for s in clips
    )
    print(
        f"wrote {args.output} — {len(cards)} cards, {len(clips)} clips, "
        f"{int(screen // 60)}:{screen % 60:04.1f} on screen"
    )


if __name__ == "__main__":
    main()
