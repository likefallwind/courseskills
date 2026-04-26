#!/usr/bin/env python3
"""Synthesize per-slide audio from narration/*.md using MINIMAX sync TTS.

Usage:
    python synth_audio.py <course-dir> [--only PREFIX] [--force]
                                       [--voice VOICE_ID] [--speed FLOAT]
                                       [--emotion STR]

Reads <course-dir>/audio.md for TTS / voice settings, walks
<course-dir>/narration/*.md, calls MINIMAX /v1/t2a_v2 (sync), and writes
<course-dir>/audio/<same-stem>.mp3.

Existing mp3 files are skipped unless --force is given. --only PREFIX
restricts to narration files whose name starts with PREFIX.

Requires: MINIMAX_API_KEY environment variable. No third-party libs.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULTS = {
    "endpoint": "https://api.minimaxi.com/v1/t2a_v2",
    "model": "speech-2.8-hd",
    "api_key_env": "MINIMAX_API_KEY",
    "speed": 1.0,
    "emotion": "calm",
    "language": "Chinese",
    "sample_rate": 32000,
    "format": "mp3",
    "bitrate": 128000,
}

KEY_RE = re.compile(r"^\s*-\s*\*\*([^*]+):\*\*\s*(.+?)\s*$")


def parse_audio_md(path: Path) -> dict:
    """Extract `- **Key:** value` pairs from audio.md into a flat dict.

    Keys are normalized: lowercased, spaces → underscores. Section headings
    are ignored — flat namespace is enough for this config.
    """
    if not path.exists():
        sys.exit(f"audio.md not found at {path}. Write it first (see SKILL.md).")
    cfg: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = KEY_RE.match(line)
        if not m:
            continue
        key = m.group(1).strip().lower().replace(" ", "_")
        cfg[key] = m.group(2).strip()
    return cfg


def resolve_settings(cfg: dict) -> dict:
    """Merge audio.md values over DEFAULTS, coerce numeric fields."""
    s = dict(DEFAULTS)
    for k, v in cfg.items():
        s[k] = v
    s["speed"] = float(s.get("speed", 1.0))
    s["sample_rate"] = int(s.get("sample_rate", 32000))
    s["bitrate"] = int(s.get("bitrate", 128000))
    return s


def strip_h1(md: str) -> str:
    """Drop a leading `# ...` line if present — TTS shouldn't speak the title."""
    lines = md.lstrip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def synthesize(text: str, settings: dict, api_key: str) -> bytes:
    payload = {
        "model": settings["model"],
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": settings["voice_id"],
            "speed": settings["speed"],
            "emotion": settings["emotion"],
        },
        "audio_setting": {
            "sample_rate": settings["sample_rate"],
            "bitrate": settings["bitrate"],
            "format": settings["format"],
            "channel": 1,
        },
    }
    req = urllib.request.Request(
        settings["endpoint"],
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit(f"TTS HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}")
    except urllib.error.URLError as e:
        sys.exit(f"TTS network error: {e.reason}")

    base = body.get("base_resp", {})
    if base.get("status_code", 0) != 0:
        sys.exit(f"TTS error {base.get('status_code')}: {base.get('status_msg')}")
    audio_hex = body.get("data", {}).get("audio")
    if not audio_hex:
        sys.exit(f"TTS response missing data.audio: {json.dumps(body)[:500]}")
    return bytes.fromhex(audio_hex)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("course_dir", type=Path, help="Course directory (contains audio.md, narration/, slides/)")
    parser.add_argument("--only", default=None, help="Only process narration files whose stem starts with this prefix (e.g. 003)")
    parser.add_argument("--force", action="store_true", help="Re-synthesize even if the mp3 already exists")
    parser.add_argument("--voice", default=None, help="Override voice_id from audio.md for this run")
    parser.add_argument("--speed", type=float, default=None, help="Override speed")
    parser.add_argument("--emotion", default=None, help="Override emotion")
    args = parser.parse_args()

    course = args.course_dir.resolve()
    narration_dir = course / "narration"
    audio_dir = course / "audio"
    if not narration_dir.is_dir():
        sys.exit(f"narration/ missing under {course}. Write narration files first (SKILL.md step 3).")
    audio_dir.mkdir(exist_ok=True)

    cfg = parse_audio_md(course / "audio.md")
    settings = resolve_settings(cfg)
    if args.voice:
        settings["voice_id"] = args.voice
    if args.speed is not None:
        settings["speed"] = args.speed
    if args.emotion:
        settings["emotion"] = args.emotion
    if not settings.get("voice_id") or settings["voice_id"].startswith("<"):
        sys.exit("voice_id is missing in audio.md. Set it under ## Voice (no default).")

    api_key_env = settings.get("api_key_env", "MINIMAX_API_KEY")
    api_key = os.environ.get(api_key_env)
    if not api_key:
        sys.exit(f"${api_key_env} is not set. Export it before running.")

    sources = sorted(p for p in narration_dir.iterdir() if p.suffix == ".md")
    if args.only:
        sources = [p for p in sources if p.stem.startswith(args.only)]
    if not sources:
        sys.exit("No narration files matched.")

    for src in sources:
        out = audio_dir / f"{src.stem}.{settings['format']}"
        if out.exists() and not args.force:
            print(f"skip   {out.name} (exists)")
            continue
        text = strip_h1(src.read_text(encoding="utf-8"))
        if not text:
            print(f"skip   {src.name} (empty)")
            continue
        print(f"synth  {src.name} -> {out.name} ({len(text)} chars)")
        audio = synthesize(text, settings, api_key)
        out.write_bytes(audio)


if __name__ == "__main__":
    main()
