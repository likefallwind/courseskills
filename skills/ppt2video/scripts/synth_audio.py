#!/usr/bin/env python3
"""Synthesize prepared per-page narration through the sibling doubao-voice CLI."""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_VOICE = "zh_male_yuanboxiaoshu_uranus_bigtts"
DOUBAO_SCRIPT = Path(__file__).resolve().parents[2] / "doubao-voice" / "scripts" / "doubao_voice.py"
KEY_RE = re.compile(r"^\s*-\s*\*\*([^*]+):\*\*\s*(.+?)\s*$")
SAMPLE_RATES = {8000, 16000, 22050, 24000, 32000, 44100, 48000}


class AudioError(Exception):
    """A configuration, mapping, or synthesis error safe to show to the user."""


def parse_audio_md(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise AudioError(f"missing audio config: {path}; run prepare_course.py first")
    settings: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = KEY_RE.match(line)
        if match:
            key = match.group(1).strip().lower().replace(" ", "_")
            settings[key] = match.group(2).strip()
    return settings


def load_course(course: Path) -> list[dict]:
    manifest = course / "pages.json"
    if not manifest.is_file():
        raise AudioError(f"missing page manifest: {manifest}; run prepare_course.py first")
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AudioError(f"invalid page manifest: {exc}") from exc
    pages = data.get("pages") if isinstance(data, dict) else None
    if not isinstance(pages, list) or not pages:
        raise AudioError("page manifest contains no pages")

    expected_stems = [f"{number:03d}" for number in range(1, len(pages) + 1)]
    for index, page in enumerate(pages):
        if not isinstance(page, dict) or page.get("number") != index + 1 or page.get("stem") != expected_stems[index]:
            raise AudioError("page manifest must contain complete, ordered pages starting at 001")

    missing: list[str] = []
    for stem in expected_stems:
        if not (course / "slides" / f"{stem}.png").is_file():
            missing.append(f"slides/{stem}.png")
        narration = course / "narration" / f"{stem}.txt"
        if not narration.is_file():
            missing.append(f"narration/{stem}.txt")
        elif not narration.read_text(encoding="utf-8").strip():
            raise AudioError(f"empty narration: narration/{stem}.txt")
    extra = sorted(
        path.name
        for directory, pattern in ((course / "slides", "*.png"), (course / "narration", "*.txt"))
        if directory.is_dir()
        for path in directory.glob(pattern)
        if path.stem not in expected_stems
    )
    if missing:
        raise AudioError("missing course files: " + ", ".join(missing))
    if extra:
        raise AudioError("unexpected slide/narration files: " + ", ".join(extra))
    return pages


def resolve_settings(course: Path, voice: str | None, speed: float | None) -> tuple[str, float, int]:
    settings = parse_audio_md(course / "audio.md")
    if settings.get("provider", "doubao") != "doubao":
        raise AudioError("ppt2video audio.md provider must be doubao")
    if settings.get("format", "mp3") != "mp3":
        raise AudioError("ppt2video requires format mp3 for the existing video assembler")
    resolved_voice = (voice if voice is not None else settings.get("voice_id", DEFAULT_VOICE)).strip()
    if not resolved_voice:
        raise AudioError("voice must not be empty")
    try:
        resolved_speed = speed if speed is not None else float(settings.get("speed", "1.0"))
        sample_rate = int(settings.get("sample_rate", "24000"))
    except ValueError as exc:
        raise AudioError("speed and sample_rate must be numeric") from exc
    if not math.isfinite(resolved_speed) or not 0.5 <= resolved_speed <= 2.0:
        raise AudioError("speed must be between 0.5 and 2.0")
    if sample_rate not in SAMPLE_RATES:
        raise AudioError("unsupported sample_rate")
    return resolved_voice, resolved_speed, sample_rate


def select_pages(pages: list[dict], only: str | None) -> list[dict]:
    if only is None:
        return pages
    stem = f"{int(only):03d}" if only.isdigit() else only
    selected = [page for page in pages if page["stem"] == stem]
    if not selected:
        raise AudioError(f"--only did not match a prepared page: {only}")
    return selected


def build_command(course: Path, stem: str, voice: str, speed: float, sample_rate: int, force: bool) -> list[str]:
    command = [
        sys.executable,
        str(DOUBAO_SCRIPT),
        "speak",
        "--text-file",
        str(course / "narration" / f"{stem}.txt"),
        "--voice",
        voice,
        "--output",
        str(course / "audio" / f"{stem}.mp3"),
        "--format",
        "mp3",
        "--sample-rate",
        str(sample_rate),
        "--speed",
        str(speed),
    ]
    if force:
        command.append("--force")
    return command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("course_dir", type=Path)
    parser.add_argument("--only", help="Synthesize one page stem, for example 003")
    parser.add_argument("--voice", help="Override audio.md voice_id for this run")
    parser.add_argument("--speed", type=float, help="Override audio.md speed for this run")
    parser.add_argument("--force", action="store_true", help="Approve regeneration and additional Gateway usage")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    course = args.course_dir.resolve()
    try:
        pages = load_course(course)
        selected = select_pages(pages, args.only)
        voice, speed, sample_rate = resolve_settings(course, args.voice, args.speed)
        if not DOUBAO_SCRIPT.is_file():
            raise AudioError(f"sibling doubao-voice CLI not found: {DOUBAO_SCRIPT}")
        audio_dir = course / "audio"
        audio_dir.mkdir(exist_ok=True)
        for page in selected:
            stem = page["stem"]
            output = audio_dir / f"{stem}.mp3"
            if output.exists() and not output.is_file():
                raise AudioError(f"audio output exists and is not a file: {output}")
            if output.exists() and not args.force:
                print(f"skip {output} (exists)")
                continue
            print(f"synthesize {stem}")
            command = build_command(course, stem, voice, speed, sample_rate, args.force)
            try:
                subprocess.run(command, check=True)
            except subprocess.CalledProcessError as exc:
                raise AudioError(
                    f"Doubao synthesis failed for {stem}; no automatic retry was made"
                ) from exc
    except (AudioError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
