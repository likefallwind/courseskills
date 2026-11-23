from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prepare_course.py"
SPEC = importlib.util.spec_from_file_location("ppt2video_prepare_course", SCRIPT_PATH)
assert SPEC and SPEC.loader
prepare = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = prepare
SPEC.loader.exec_module(prepare)


def page(number: int, body: str, title: str = "标题", duration: str = "0:00—0:10") -> str:
    return (
        f"=== PAGE {number:03d} ===\n"
        f"TITLE: {title}\n"
        f"REFERENCE_TIME: {duration}\n"
        "=== NARRATION ===\n"
        f"{body}\n"
        "=== END PAGE ==="
    )


class NormalizedTranscriptTests(unittest.TestCase):
    def test_parse_preserves_narration_and_metadata(self) -> None:
        text = page(1, "第一段。\r\n\r\n**第二段** 保留。", "封面") + "\r\n" + page(2, "下一页。")
        pages = prepare.parse_normalized_transcript(text)
        self.assertEqual([p.number for p in pages], [1, 2])
        self.assertEqual(pages[0].title, "封面")
        self.assertEqual(pages[0].reference_time, "0:00—0:10")
        self.assertEqual(pages[0].narration, "第一段。\n\n**第二段** 保留。")
        self.assertEqual(pages[1].stem, "002")

    def test_raw_keyword_transcript_is_rejected(self) -> None:
        with self.assertRaisesRegex(prepare.PrepareError, "PAGE"):
            prepare.parse_normalized_transcript("## 第1页｜封面\n### 本页逐字稿\n你好。")

    def test_missing_end_marker_is_rejected(self) -> None:
        with self.assertRaisesRegex(prepare.PrepareError, "END PAGE"):
            prepare.parse_normalized_transcript(
                "=== PAGE 001 ===\n=== NARRATION ===\n正文"
            )

    def test_narration_before_page_is_rejected(self) -> None:
        with self.assertRaisesRegex(prepare.PrepareError, "PAGE"):
            prepare.parse_normalized_transcript("=== NARRATION ===\n正文")

    def test_duplicate_page_is_rejected(self) -> None:
        with self.assertRaisesRegex(prepare.PrepareError, "duplicate"):
            prepare.parse_normalized_transcript(page(1, "甲") + "\n" + page(1, "乙"))

    def test_empty_narration_is_rejected(self) -> None:
        with self.assertRaisesRegex(prepare.PrepareError, "empty"):
            prepare.parse_normalized_transcript(page(1, "  \n  "))

    def test_reserved_marker_inside_narration_is_rejected(self) -> None:
        with self.assertRaisesRegex(prepare.PrepareError, "reserved"):
            prepare.parse_normalized_transcript(page(1, "甲\n=== PAGE 002 ===\n乙"))

    def test_unknown_header_metadata_is_rejected(self) -> None:
        text = page(1, "正文").replace("TITLE: 标题", "建议时间：一分钟")
        with self.assertRaisesRegex(prepare.PrepareError, "metadata"):
            prepare.parse_normalized_transcript(text)

    def test_validate_pages_requires_complete_ordered_mapping(self) -> None:
        pages = prepare.parse_normalized_transcript(page(2, "乙") + "\n" + page(1, "甲"))
        with self.assertRaisesRegex(prepare.PrepareError, "order"):
            prepare.validate_pages(pages, 2)

        pages = prepare.parse_normalized_transcript(page(1, "甲") + "\n" + page(3, "丙"))
        with self.assertRaisesRegex(prepare.PrepareError, "missing"):
            prepare.validate_pages(pages, 3)

    def test_validate_pages_rejects_extra_pages(self) -> None:
        pages = prepare.parse_normalized_transcript(page(1, "甲") + "\n" + page(2, "乙"))
        with self.assertRaisesRegex(prepare.PrepareError, "match"):
            prepare.validate_pages(pages, 1)


class PrepareOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="ppt2video prepare tests ")
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)

    def test_write_outputs_creates_plain_text_and_default_audio_config(self) -> None:
        pages = prepare.parse_normalized_transcript(page(1, "只读正文。", "封面"))
        prepare.write_outputs(self.root, pages)
        self.assertEqual((self.root / "narration" / "001.txt").read_text(), "只读正文。")
        self.assertIn(
            prepare.DEFAULT_VOICE,
            (self.root / "audio.md").read_text(),
        )
        self.assertTrue((self.root / "pages.json").is_file())

    def test_render_slides_uses_single_dash_libreoffice_profile_option(self) -> None:
        pptx = self.root / "deck.pptx"
        pptx.write_bytes(b"pptx")
        commands = []

        def fake_run(command, operation):
            commands.append(command)
            if command[0] == "soffice":
                output = Path(command[command.index("--outdir") + 1])
                (output / "deck.pdf").write_bytes(b"pdf")
            else:
                prefix = Path(command[-1])
                (prefix.parent / "slide-1.png").write_bytes(b"png")

        with (
            patch.object(prepare.shutil, "which", return_value="/usr/bin/tool"),
            patch.object(prepare, "run_command", side_effect=fake_run),
        ):
            self.assertEqual(prepare.render_slides(pptx, self.root / "slides"), 1)
        self.assertTrue(any(arg.startswith("-env:UserInstallation=") for arg in commands[0]))
        self.assertFalse(any(arg.startswith("--env:") for arg in commands[0]))

    def test_collect_rendered_slides_uses_numeric_order(self) -> None:
        for name in ("slide-10.png", "slide-2.png", "slide-1.png"):
            (self.root / name).write_bytes(b"png")
        # Remove the gap so the fixture exercises ordering rather than gap validation.
        for number in range(3, 10):
            (self.root / f"slide-{number}.png").write_bytes(b"png")
        slides = prepare.collect_rendered_slides(self.root)
        self.assertEqual([p.name for p in slides[:3]], ["slide-1.png", "slide-2.png", "slide-3.png"])
        self.assertEqual(slides[-1].name, "slide-10.png")

    def test_collect_rendered_slides_rejects_missing_page(self) -> None:
        for number in (1, 3):
            (self.root / f"slide-{number}.png").write_bytes(b"png")
        with self.assertRaisesRegex(prepare.PrepareError, "sequence"):
            prepare.collect_rendered_slides(self.root)


if __name__ == "__main__":
    unittest.main()
