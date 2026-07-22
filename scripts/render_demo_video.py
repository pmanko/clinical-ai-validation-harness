#!/usr/bin/env python3
"""Render a published demo cut from a raw Playwright capture."""

import argparse
import json
import os
import subprocess
from pathlib import Path


def validate_timeline(timeline: dict) -> None:
    """Raise ValueError when the timeline cannot be rendered."""
    for i, segment in enumerate(timeline["segments"]):
        if segment["type"] == "clip" and segment["end"] <= segment["start"]:
            raise ValueError(f"segment {i}: clip 'end' must exceed 'start'")


def final_duration(timeline: dict) -> float:
    """Output duration in seconds: card durations plus speed-adjusted clips."""
    total = 0.0
    for segment in timeline["segments"]:
        if segment["type"] == "card":
            total += segment["duration"]
        else:
            total += (segment["end"] - segment["start"]) / segment.get("speed", 1.0)
            total += segment.get("hold", 0.0)
    return total


def build_filtergraph(timeline: dict) -> str:
    """Build the ffmpeg -filter_complex graph for the whole timeline."""
    filters = []
    labels = []
    for i, segment in enumerate(timeline["segments"]):
        label = f"s{i}"
        if segment["type"] == "card":
            h = timeline["height"]
            chain = (
                f"color=c=0x24133F:size={timeline['width']}x{h}"
                f":rate={timeline.get('fps', 25)}:duration={segment['duration']}"
            )
            if segment.get("kicker"):
                chain += (
                    f",drawtext=text='{drawtext_escape(segment['kicker'])}'"
                    f":fontcolor=0xF2C75C:fontsize={int(h * 0.032)}"
                    f":x=(w-text_w)/2:y=(h/2)-{int(h * 0.11)}"
                )
            chain += (
                f",drawtext=text='{drawtext_escape(segment['heading'])}'"
                f":fontcolor=white:fontsize={int(h * 0.055)}"
                f":x=(w-text_w)/2:y=(h-text_h)/2"
            )
            for j, line in enumerate(segment.get("lines", ())):
                chain += (
                    f",drawtext=text='{drawtext_escape(line)}'"
                    f":fontcolor=0xCFC6E0:fontsize={int(h * 0.032)}"
                    f":x=(w-text_w)/2:y=(h/2)+{int(h * (0.1 + j * 0.06))}"
                )
        else:
            w, h = timeline["width"], timeline["height"]
            chain = f"[0:v]trim=start={segment['start']}:end={segment['end']}"
            speed = segment.get("speed", 1.0)
            chain += f",setpts=(PTS-STARTPTS)/{speed}"
            chain += (
                f",scale={w}:{h}:force_original_aspect_ratio=decrease"
                f",pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x24133F"
            )
            if segment.get("hold"):
                chain += f",tpad=stop_mode=clone:stop_duration={segment['hold']}"
            if segment.get("caption"):
                chain += (
                    f",drawtext=text='{drawtext_escape(segment['caption'])}'"
                    f":fontcolor=white:box=1:boxcolor=0x24133F:x=36:y=h-text_h-36"
                )
        filters.append(f"{chain}[{label}]")
        labels.append(f"[{label}]")
    filters.append(f"{''.join(labels)}concat=n={len(labels)}:v=1:a=0[out]")
    return ";".join(filters)


def build_command(timeline: dict, *, source: str, output: str) -> list[str]:
    """Build the ffmpeg argv that renders the timeline to a publishable mp4."""
    return [
        os.environ.get("FFMPEG_BIN", "ffmpeg"), "-y", "-i", source,
        "-filter_complex", build_filtergraph(timeline),
        "-map", "[out]",
        "-an",
        "-c:v", "libx264", "-preset", "slow", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output,
    ]


def drawtext_escape(text: str) -> str:
    """Escape ffmpeg drawtext metacharacters in literal text."""
    escaped = text.replace("\\", "\\\\")
    for ch in "':,;[]%":
        escaped = escaped.replace(ch, "\\" + ch)
    return escaped


def main(argv: "list[str] | None" = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", help="path to the timeline JSON")
    parser.add_argument("--source", required=True, help="raw Playwright capture")
    parser.add_argument("--output", required=True, help="rendered mp4 path")
    parser.add_argument("--poster", help="poster jpg path")
    parser.add_argument("--poster-time", type=float, default=1.0,
                        help="seconds into the rendered mp4 to grab the poster frame")
    args = parser.parse_args(argv)

    timeline = json.loads(Path(args.timeline).read_text(encoding="utf-8"))
    validate_timeline(timeline)

    subprocess.run(
        build_command(timeline, source=args.source, output=args.output),
        check=True,
    )

    if args.poster:
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", str(args.poster_time), "-i", args.output,
                "-vframes", "1", "-q:v", "3", args.poster,
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
