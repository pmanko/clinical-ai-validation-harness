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
        if segment["type"] == "card" and segment["duration"] <= 0:
            raise ValueError(f"segment {i}: card 'duration' must be positive")


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


def build_filtergraph(timeline: dict, tmp_dir: "Path | None" = None) -> str:
    """Build the ffmpeg -filter_complex graph for the whole timeline.

    Human-authored text is written to plain UTF-8 files under `tmp_dir`
    (a fresh temp directory by default) and referenced via ffmpeg's
    `textfile=` rather than embedded inline — see drawtext_escape's
    docstring for why inline text is unsafe.
    """
    if tmp_dir is None:
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp())
    # A fontconfig generic alias, not a specific family: "Helvetica Neue"
    # renders on macOS but is absent on Linux CI runners, so the default has
    # to be something fontconfig can always resolve to *some* sans-serif.
    font = timeline.get("font", "sans-serif")
    filters = []
    labels = []
    for i, segment in enumerate(timeline["segments"]):
        label = f"s{i}"
        if segment["type"] == "card":
            h = timeline["height"]
            w = timeline["width"]
            duration = segment["duration"]
            chain = (
                f"color=c=0x24133F:size={w}x{h}"
                f":rate={timeline.get('fps', 25)}:duration={duration}"
            )
            if segment.get("kicker"):
                kicker_path = Path(tmp_dir) / f"{label}-kicker.txt"
                kicker_path.write_text(segment["kicker"], encoding="utf-8")
                chain += (
                    f",drawtext=font='{font}'"
                    f":textfile={drawtext_escape(str(kicker_path))}"
                    f":fontcolor=0xF2C75C:fontsize={int(h * 0.028)}"
                    f":x=(w-text_w)/2:y=(h/2)-{int(h * 0.13)}"
                )
                # A short gold rule under the kicker. Centred text alone reads
                # as a slide someone typed; the rule is what makes the card
                # look composed rather than defaulted.
                # `iw`, not `w`: inside drawbox `w` is the box's own width, so
                # x=(w-rule_w)/2 evaluates to zero and pins the rule to the
                # left edge instead of centring it.
                rule_w = int(w * 0.075)
                chain += (
                    f",drawbox=x=(iw-{rule_w})/2:y={int(h * 0.5 - h * 0.072)}"
                    f":w={rule_w}:h=3:color=0xF2C75C@0.9:t=fill"
                )
            heading_path = Path(tmp_dir) / f"{label}-heading.txt"
            heading_path.write_text(segment["heading"], encoding="utf-8")
            chain += (
                f",drawtext=font='{font}'"
                f":textfile={drawtext_escape(str(heading_path))}"
                f":fontcolor=white:fontsize={int(h * 0.058)}"
                f":x=(w-text_w)/2:y=(h-text_h)/2"
            )
            for j, line in enumerate(segment.get("lines", ())):
                line_path = Path(tmp_dir) / f"{label}-line{j}.txt"
                line_path.write_text(line, encoding="utf-8")
                chain += (
                    f",drawtext=font='{font}'"
                    f":textfile={drawtext_escape(str(line_path))}"
                    f":fontcolor=0xCFC6E0:fontsize={int(h * 0.030)}"
                    f":x=(w-text_w)/2:y=(h/2)+{int(h * (0.1 + j * 0.055))}"
                )
            # These mp4s get shared on their own, not only embedded in the
            # page they were made for, so each card carries where it came from.
            footer = timeline.get("footer")
            if footer:
                footer_path = Path(tmp_dir) / f"{label}-footer.txt"
                footer_path.write_text(footer, encoding="utf-8")
                chain += (
                    f",drawtext=font='{font}'"
                    f":textfile={drawtext_escape(str(footer_path))}"
                    f":fontcolor=0xCFC6E0@0.55:fontsize={int(h * 0.024)}"
                    f":x=(w-text_w)/2:y=h-text_h-{int(h * 0.06)}"
                )
            # Fade the card in and out so sections arrive instead of blinking.
            fade = min(0.4, duration / 4)
            chain += (
                f",fade=t=in:st=0:d={fade:.2f}"
                f",fade=t=out:st={duration - fade:.2f}:d={fade:.2f}"
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
                caption_path = Path(tmp_dir) / f"{label}-caption.txt"
                caption_path.write_text(segment["caption"], encoding="utf-8")
                # boxborderw matters more than it sounds: without padding the
                # box is drawn tight to the glyphs and reads as a bug rather
                # than a lower third.
                chain += (
                    f",drawtext=font='{font}'"
                    f":textfile={drawtext_escape(str(caption_path))}"
                    f":fontcolor=white:fontsize={int(h * 0.030)}"
                    f":box=1:boxcolor=0x24133F@0.92:boxborderw={int(h * 0.022)}"
                    f":x={int(w * 0.035)}:y=h-text_h-{int(h * 0.075)}"
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


def drawtext_escape(path: str) -> str:
    """Escape ffmpeg filter-option metacharacters in a plain path string.

    Human-authored text (headings, captions, ...) is never embedded inline
    in the filtergraph — a quoted ffmpeg option value has its own fragile,
    multi-layered escaping grammar (colons split key=value pairs, commas
    split filter options, semicolons split chains, and a literal single
    quote cannot simply be backslash-escaped inside a '...'-quoted value).
    Text instead goes into a `textfile=` referencing a plain temp file,
    sidestepping that grammar entirely. This escape runs only on the
    resulting (unquoted) file path, so it escapes ffmpeg's structural
    metacharacters but not quotes.
    """
    escaped = path.replace("\\", "\\\\")
    for ch in ":,;[]%":
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
                os.environ.get("FFMPEG_BIN", "ffmpeg"),
                "-y", "-ss", str(args.poster_time), "-i", args.output,
                "-vframes", "1", "-q:v", "2", args.poster,
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
