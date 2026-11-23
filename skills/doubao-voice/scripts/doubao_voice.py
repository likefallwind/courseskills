#!/usr/bin/env python3
"""Synthesize official Doubao voices through an API Gateway.

Only the Python standard library is required. The client uses one Gateway
token; provider credentials and protocol conversion stay on the Gateway.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GATEWAY_MODEL = "doubao-seed-tts-2.0"
DEFAULT_GATEWAY_BASE_URL = "http://127.0.0.1:8111"
FORMATS = ("mp3", "wav", "pcm", "ogg_opus")
SAMPLE_RATES = (8000, 16000, 22050, 24000, 32000, 44100, 48000)
CONTENT_TYPES = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "pcm": "audio/L16",
    "ogg_opus": "audio/ogg",
}


class VoiceError(Exception):
    """A validation, transport, or Gateway error safe to show to the user."""


def gateway_api_key() -> str:
    for name in ("DOUBAO_VOICE_GATEWAY_API_KEY", "API_GATEWAY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    raise VoiceError(
        "DOUBAO_VOICE_GATEWAY_API_KEY is not set and API_GATEWAY is unavailable; "
        "no request was made."
    )


def gateway_speech_url(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise VoiceError("DOUBAO_VOICE_GATEWAY_BASE_URL must be an HTTP(S) URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise VoiceError("Gateway URL must not contain credentials, query, or fragment.")
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3]
    root = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
    return root + "/v1/audio/speech"


def read_text(args: argparse.Namespace) -> str:
    if args.text_file is not None:
        text = args.text_file.read_text(encoding="utf-8")
    else:
        text = args.text
    if not text or not text.strip():
        raise VoiceError("Speech input text must not be empty.")
    return text


def validate_audio_options(args: argparse.Namespace) -> None:
    if not math.isfinite(args.speed) or not 0.5 <= args.speed <= 2.0:
        raise VoiceError("speed must be between 0.5 and 2.0.")
    if args.format == "ogg_opus" and args.sample_rate != 48000:
        raise VoiceError("ogg_opus requires --sample-rate 48000.")
    if not args.voice.strip():
        raise VoiceError("voice must be a non-empty official Doubao speaker ID.")


def should_skip_output(output: Path, force: bool) -> bool:
    if output.exists() and not output.is_file():
        raise VoiceError(f"Output exists and is not a file: {output}")
    if output.exists() and not force:
        print(f"skip {output} (exists; use --force only with explicit regeneration approval)")
        return True
    return False


def atomic_write(output: Path, content: bytes) -> None:
    if not content:
        raise VoiceError("Refusing to write empty audio.")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()


def safe_response_message(content: bytes) -> str:
    try:
        data = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "no additional response details"
    if not isinstance(data, dict):
        return "no additional response details"
    error = data.get("error")
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    code = data.get("code")
    message = data.get("message")
    if code is not None and message:
        return f"{code}: {message}"
    if message:
        return str(message)
    return "no additional response details"


def request_raw(
    request: urllib.request.Request,
    timeout: int,
    operation: str,
) -> tuple[bytes, object]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            status = getattr(response, "status", 200)
            headers = response.headers
    except urllib.error.HTTPError as exc:
        body = exc.read()
        request_id = exc.headers.get("X-Request-Id") if exc.headers else None
        suffix = f" (request ID: {request_id})" if request_id else ""
        raise VoiceError(
            f"{operation} returned HTTP {exc.code}: {safe_response_message(body)}{suffix}"
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        reason = exc.reason if isinstance(exc, urllib.error.URLError) else str(exc)
        raise VoiceError(
            f"{operation} failed: {reason}. No automatic retry was made; "
            "review the Gateway status before any further attempt."
        ) from exc
    if status >= 400:
        raise VoiceError(f"{operation} returned HTTP {status}: {safe_response_message(body)}")
    return body, headers


def json_request(url: str, payload: dict) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {gateway_api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )


def speak(args: argparse.Namespace) -> None:
    if should_skip_output(args.output, args.force):
        return
    text = read_text(args)
    validate_audio_options(args)
    payload = {
        "model": GATEWAY_MODEL,
        "input": text,
        "voice": args.voice,
        "response_format": args.format,
        "speed": args.speed,
        "sample_rate": args.sample_rate,
    }
    base_url = os.environ.get("DOUBAO_VOICE_GATEWAY_BASE_URL", DEFAULT_GATEWAY_BASE_URL)
    request = json_request(gateway_speech_url(base_url), payload)
    content, headers = request_raw(request, args.timeout, "Gateway speech")
    content_type = headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    expected = CONTENT_TYPES[args.format].lower()
    if content_type != expected:
        raise VoiceError(
            f"Gateway returned Content-Type {content_type or '<missing>'!r}; expected {expected!r}."
        )
    atomic_write(args.output, content)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    speak_parser = commands.add_parser("speak", help="Synthesize an official voice through the Gateway.")
    text_group = speak_parser.add_mutually_exclusive_group(required=True)
    text_group.add_argument("--text", help="Text to synthesize.")
    text_group.add_argument("--text-file", type=Path, help="UTF-8 file containing synthesis text.")
    speak_parser.add_argument("--voice", required=True, help="Official Doubao speaker ID, not an OpenAI voice.")
    speak_parser.add_argument("--output", type=Path, required=True, help="Destination audio path.")
    speak_parser.add_argument("--format", choices=FORMATS, default="mp3")
    speak_parser.add_argument("--sample-rate", type=int, choices=SAMPLE_RATES, default=24000)
    speak_parser.add_argument("--speed", type=float, default=1.0, help="Speech multiplier, 0.5–2.0.")
    speak_parser.add_argument("--force", action="store_true", help="Approve regeneration and additional Gateway usage.")
    speak_parser.add_argument("--timeout", type=int, default=180, help="Request timeout in seconds (default: 180).")
    speak_parser.set_defaults(func=speak)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        args.func(args)
    except (VoiceError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
