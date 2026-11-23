from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "synth_audio.py"
SPEC = importlib.util.spec_from_file_location("ppt2video_synth_audio", SCRIPT_PATH)
assert SPEC and SPEC.loader
synth = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = synth
SPEC.loader.exec_module(synth)


class SynthAudioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="ppt2video synth tests ")
        self.addCleanup(self.tempdir.cleanup)
        self.course = Path(self.tempdir.name) / "course"
        (self.course / "slides").mkdir(parents=True)
        (self.course / "narration").mkdir()
        (self.course / "audio").mkdir()
        pages = []
        for number in range(1, 4):
            stem = f"{number:03d}"
            (self.course / "slides" / f"{stem}.png").write_bytes(b"png")
            (self.course / "narration" / f"{stem}.txt").write_text(f"第{number}页正文。")
            pages.append({
                "number": number,
                "stem": stem,
                "title": f"第{number}页",
                "reference_time": "",
            })
        (self.course / "pages.json").write_text(json.dumps({"version": 1, "pages": pages}))
        (self.course / "audio.md").write_text(
            "# Audio Settings\n\n"
            "- **provider:** doubao\n"
            f"- **voice_id:** {synth.DEFAULT_VOICE}\n"
            "- **speed:** 1.0\n"
            "- **sample_rate:** 24000\n"
            "- **format:** mp3\n"
            "- **head_silence_sec:** 0.3\n"
            "- **tail_silence_sec:** 0.5\n"
        )

    def invoke(self, *args: str, side_effect=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(synth.subprocess, "run", side_effect=side_effect) as run,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = synth.main([str(self.course), *args])
        return code, run, stdout.getvalue(), stderr.getvalue()

    def test_synthesizes_every_page_with_doubao_cli(self) -> None:
        code, run, _, stderr = self.invoke()
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(run.call_count, 3)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0][1], str(synth.DOUBAO_SCRIPT))
        self.assertEqual(commands[0][2], "speak")
        self.assertEqual(
            commands[0][commands[0].index("--voice") + 1],
            synth.DEFAULT_VOICE,
        )
        self.assertTrue(commands[0][commands[0].index("--text-file") + 1].endswith("001.txt"))
        self.assertTrue(commands[-1][commands[-1].index("--output") + 1].endswith("003.mp3"))

    def test_existing_selected_audio_is_cached(self) -> None:
        (self.course / "audio" / "001.mp3").write_bytes(b"approved")
        code, run, stdout, _ = self.invoke("--only", "001")
        self.assertEqual(code, 0)
        self.assertIn("skip", stdout.lower())
        run.assert_not_called()

    def test_only_force_regenerates_one_page(self) -> None:
        for stem in ("001", "002", "003"):
            (self.course / "audio" / f"{stem}.mp3").write_bytes(stem.encode())
        code, run, _, _ = self.invoke("--only", "003", "--force")
        self.assertEqual(code, 0)
        run.assert_called_once()
        command = run.call_args.args[0]
        self.assertIn("--force", command)
        self.assertTrue(command[command.index("--text-file") + 1].endswith("003.txt"))
        self.assertEqual((self.course / "audio" / "001.mp3").read_bytes(), b"001")
        self.assertEqual((self.course / "audio" / "002.mp3").read_bytes(), b"002")

    def test_cli_voice_and_speed_override_config(self) -> None:
        code, run, _, _ = self.invoke(
            "--only", "002", "--voice", "zh_male_ruyayichen_uranus_bigtts", "--speed", "0.9"
        )
        self.assertEqual(code, 0)
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--voice") + 1], "zh_male_ruyayichen_uranus_bigtts")
        self.assertEqual(command[command.index("--speed") + 1], "0.9")

    def test_invalid_course_mapping_stops_before_any_request(self) -> None:
        (self.course / "narration" / "002.txt").unlink()
        code, run, _, stderr = self.invoke("--only", "001")
        self.assertEqual(code, 1)
        self.assertIn("missing", stderr.lower())
        run.assert_not_called()

    def test_invalid_only_stops_before_any_request(self) -> None:
        code, run, _, stderr = self.invoke("--only", "009")
        self.assertEqual(code, 1)
        self.assertIn("only", stderr.lower())
        run.assert_not_called()

    def test_failure_stops_remaining_pages_without_retry(self) -> None:
        code, run, _, stderr = self.invoke(
            side_effect=[
                subprocess.CompletedProcess(["doubao"], 0),
                subprocess.CalledProcessError(1, ["doubao"]),
            ]
        )
        self.assertEqual(code, 1)
        self.assertEqual(run.call_count, 2)
        self.assertIn("failed", stderr.lower())

    def test_invalid_speed_stops_before_any_request(self) -> None:
        code, run, _, stderr = self.invoke("--speed", "2.1")
        self.assertEqual(code, 1)
        self.assertIn("speed", stderr.lower())
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
