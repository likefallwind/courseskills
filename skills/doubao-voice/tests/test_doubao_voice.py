from __future__ import annotations

import importlib.util
import io
import json
import os
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "doubao_voice.py"
SPEC = importlib.util.spec_from_file_location("doubao_voice", SCRIPT_PATH)
assert SPEC and SPEC.loader
voice = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(voice)

GATEWAY_ENV = {"DOUBAO_VOICE_GATEWAY_API_KEY": "gateway-test-token"}
VOICE_ID = "zh_female_vv_uranus_bigtts"


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200, content_type: str = "application/json"):
        self.body = body
        self.status = status
        self.headers = {"Content-Type": content_type, "X-Request-Id": "test-request-id"}

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class DoubaoVoiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="doubao voice tests ")
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.output = self.root / "output audio.mp3"

    def invoke(self, args: list[str], env: dict[str, str], response=None, error=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(voice.urllib.request, "urlopen") as urlopen,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            if error is not None:
                urlopen.side_effect = error
            elif response is not None:
                urlopen.return_value = response
            code = voice.main(args)
        return code, urlopen, stdout.getvalue(), stderr.getvalue()

    def speak_args(self, *extra: str) -> list[str]:
        return [
            "speak", "--text", "你好。", "--voice", VOICE_ID,
            "--output", str(self.output), *extra,
        ]

    def test_gateway_url_normalization(self) -> None:
        for base in (
            "http://127.0.0.1:8111",
            "http://127.0.0.1:8111/",
            "http://127.0.0.1:8111/v1",
            "http://127.0.0.1:8111/v1/",
        ):
            with self.subTest(base=base):
                self.assertEqual(
                    voice.gateway_speech_url(base),
                    "http://127.0.0.1:8111/v1/audio/speech",
                )

    def test_speak_uses_gateway_and_writes_audio(self) -> None:
        payload = b"ID3-audio-bytes"
        code, urlopen, stdout, stderr = self.invoke(
            self.speak_args("--speed", "1.2"),
            {
                **GATEWAY_ENV,
                "DOUBAO_VOICE_GATEWAY_BASE_URL": "http://127.0.0.1:8111/v1/",
            },
            FakeResponse(payload, content_type="audio/mpeg"),
        )
        self.assertEqual((code, stdout, stderr), (0, "", ""))
        self.assertEqual(self.output.read_bytes(), payload)
        urlopen.assert_called_once()
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8111/v1/audio/speech")
        self.assertEqual(request.headers["Authorization"], "Bearer gateway-test-token")
        self.assertNotIn("X-api-key", request.headers)
        body = json.loads(request.data)
        self.assertEqual(body["model"], "doubao-seed-tts-2.0")
        self.assertEqual(body["input"], "你好。")
        self.assertEqual(body["voice"], VOICE_ID)
        self.assertEqual(body["speed"], 1.2)
        self.assertEqual(body["sample_rate"], 24000)

    def test_existing_api_gateway_environment_is_accepted(self) -> None:
        code, urlopen, _, _ = self.invoke(
            self.speak_args(),
            {"API_GATEWAY": "existing-gateway-token"},
            FakeResponse(b"ID3-audio-bytes", content_type="audio/mpeg"),
        )
        self.assertEqual(code, 0)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.headers["Authorization"], "Bearer existing-gateway-token")

    def test_existing_output_skips_network_even_without_credentials(self) -> None:
        self.output.write_bytes(b"approved-audio")
        code, urlopen, stdout, _ = self.invoke(self.speak_args(), {})
        self.assertEqual(code, 0)
        self.assertIn("skip", stdout.lower())
        self.assertEqual(self.output.read_bytes(), b"approved-audio")
        urlopen.assert_not_called()

    def test_non_audio_http_200_preserves_existing_output(self) -> None:
        self.output.write_bytes(b"approved-audio")
        code, _, _, stderr = self.invoke(
            self.speak_args("--force"),
            GATEWAY_ENV,
            FakeResponse(b'{"error":{"message":"not audio"}}'),
        )
        self.assertEqual(code, 1)
        self.assertIn("content-type", stderr.lower())
        self.assertEqual(self.output.read_bytes(), b"approved-audio")
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_missing_credentials_and_invalid_options_stop_before_network(self) -> None:
        cases = [
            (self.speak_args(), {}),
            (self.speak_args("--speed", "2.1"), GATEWAY_ENV),
            (self.speak_args("--format", "ogg_opus"), GATEWAY_ENV),
            (self.speak_args("--voice", "   "), GATEWAY_ENV),
            (self.speak_args("--text", "   "), GATEWAY_ENV),
        ]
        for args, env in cases:
            with self.subTest(args=args):
                code, urlopen, _, _ = self.invoke(args, env)
                self.assertEqual(code, 1)
                urlopen.assert_not_called()

    def test_timeout_is_not_retried_and_leaves_no_output(self) -> None:
        code, urlopen, _, stderr = self.invoke(
            self.speak_args(),
            GATEWAY_ENV,
            error=urllib.error.URLError("timed out"),
        )
        self.assertEqual(code, 1)
        self.assertEqual(urlopen.call_count, 1)
        self.assertIn("status", stderr.lower())
        self.assertFalse(self.output.exists())

    def test_clone_workflow_is_not_part_of_this_skill(self) -> None:
        stderr = io.StringIO()
        with (
            patch.dict(os.environ, GATEWAY_ENV, clear=True),
            patch.object(voice.urllib.request, "urlopen") as urlopen,
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as raised:
                voice.main(["clone", "status", "--speaker-id", "S_test"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("invalid choice", stderr.getvalue())
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
