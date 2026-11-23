#!/usr/bin/env python3
"""Render PPTX slides and extract narration from a normalized transcript."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

DEFAULT_VOICE = "zh_male_yuanboxiaoshu_uranus_bigtts"
PAGE_RE = re.compile(r"=== PAGE (\d{3}) ===")
RENDERED_RE = re.compile(r"(\d+)$")
NARRATION_MARKER = "=== NARRATION ==="
END_PAGE_MARKER = "=== END PAGE ==="
RESERVED_RE = re.compile(r"=== (?:PAGE \d{3}|NARRATION|END PAGE) ===")


class PrepareError(Exception):
    """An input or rendering error safe to show to the user."""


@dataclass(frozen=True)
class Page:
    number: int
    title: str
    reference_time: str
    narration: str

    @property
    def stem(self) -> str:
        return f"{self.number:03d}"


def line_error(line: int, message: str) -> PrepareError:
    return PrepareError(f"line {line}: {message}")


def parse_normalized_transcript(text: str) -> list[Page]:
    """Parse only the canonical marker format, never raw transcript headings."""
    pages: list[Page] = []
    seen: set[int] = set()
    state = "page"
    number = 0
    title = ""
    reference_time = ""
    narration_lines: list[str] = []

    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if state == "page":
            if not stripped:
                continue
            match = PAGE_RE.fullmatch(stripped)
            if not match:
                raise line_error(lineno, "expected === PAGE NNN ===")
            number = int(match.group(1))
            if number == 0:
                raise line_error(lineno, "page numbers start at 001")
            if number in seen:
                raise line_error(lineno, f"duplicate page {number:03d}")
            seen.add(number)
            title = ""
            reference_time = ""
            state = "header"
            continue

        if state == "header":
            if not stripped:
                continue
            if stripped == NARRATION_MARKER:
                narration_lines = []
                state = "narration"
            elif stripped == END_PAGE_MARKER:
                raise line_error(lineno, "expected === NARRATION === before END PAGE")
            elif stripped.startswith("TITLE:"):
                title = stripped.removeprefix("TITLE:").strip()
            elif stripped.startswith("REFERENCE_TIME:"):
                reference_time = stripped.removeprefix("REFERENCE_TIME:").strip()
            else:
                raise line_error(lineno, "unsupported metadata; expected TITLE, REFERENCE_TIME, or NARRATION")
            continue

        if stripped == END_PAGE_MARKER:
            narration = "\n".join(narration_lines).strip()
            if not narration:
                raise line_error(lineno, f"page {number:03d} has empty narration")
            pages.append(Page(number, title, reference_time, narration))
            state = "page"
        elif RESERVED_RE.fullmatch(stripped):
            raise line_error(lineno, "reserved marker inside narration; close the page first")
        else:
            narration_lines.append(raw)

    if state == "narration":
        raise PrepareError(f"page {number:03d}: expected === END PAGE === at end of input")
    if state == "header":
        raise PrepareError(f"page {number:03d}: expected === NARRATION === at end of input")
    if not pages:
        raise PrepareError("normalized transcript contains no pages")
    return pages


def validate_pages(pages: list[Page], slide_count: int) -> None:
    numbers = [p.number for p in pages]
    expected = list(range(1, slide_count + 1))
    missing = sorted(set(expected) - set(numbers))
    extra = sorted(set(numbers) - set(expected))
    if missing or extra or len(numbers) != len(expected):
        details = []
        if missing:
            details.append("missing pages: " + ", ".join(f"{n:03d}" for n in missing))
        if extra:
            details.append("unexpected pages: " + ", ".join(f"{n:03d}" for n in extra))
        if not details:
            details.append("page counts differ")
        raise PrepareError(
            f"slide/narration pages do not match ({len(numbers)} transcript, {slide_count} slides); "
            + "; ".join(details)
        )
    if numbers != expected:
        raise PrepareError("normalized transcript pages are out of order; expected 001, 002, ...")


def collect_rendered_slides(directory: Path) -> list[Path]:
    numbered: list[tuple[int, Path]] = []
    for path in directory.glob("*.png"):
        match = RENDERED_RE.search(path.stem)
        if match:
            numbered.append((int(match.group(1)), path))
    if not numbered:
        raise PrepareError(f"no rendered PNG pages found in {directory}")
    ordered = [path for _, path in sorted(numbered)]
    numbers = [number for number, _ in sorted(numbered)]
    if numbers != list(range(1, len(numbers) + 1)):
        raise PrepareError("rendered slide filenames are not a complete 1-based sequence")
    return ordered


def run_command(command: list[str], operation: str) -> None:
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise PrepareError(f"{operation} failed" + (f": {detail}" if detail else "")) from exc
    except OSError as exc:
        raise PrepareError(f"{operation} failed: {exc}") from exc


def render_slides(pptx: Path, slides_dir: Path) -> int:
    if not pptx.is_file() or pptx.suffix.lower() != ".pptx":
        raise PrepareError(f"PPTX input not found or unsupported: {pptx}")
    for tool in ("soffice", "pdftoppm"):
        if shutil.which(tool) is None:
            raise PrepareError(f"{tool} not found on PATH; install LibreOffice and Poppler")

    with tempfile.TemporaryDirectory(prefix="ppt2video-render-") as temporary:
        root = Path(temporary)
        pdf_dir = root / "pdf"
        rendered_dir = root / "rendered"
        profile = root / "libreoffice-profile"
        pdf_dir.mkdir()
        rendered_dir.mkdir()
        profile.mkdir()
        run_command(
            [
                "soffice",
                f"-env:UserInstallation={profile.as_uri()}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(pdf_dir),
                str(pptx.resolve()),
            ],
            "PPTX to PDF conversion",
        )
        pdf = pdf_dir / f"{pptx.stem}.pdf"
        if not pdf.is_file():
            raise PrepareError(f"LibreOffice did not create the expected PDF: {pdf.name}")
        run_command(
            ["pdftoppm", "-png", "-r", "150", str(pdf), str(rendered_dir / "slide")],
            "PDF to PNG conversion",
        )
        rendered = collect_rendered_slides(rendered_dir)
        slides_dir.mkdir(parents=True, exist_ok=True)
        for number, source in enumerate(rendered, 1):
            shutil.copyfile(source, slides_dir / f"{number:03d}.png")
        return len(rendered)


def write_outputs(course_dir: Path, pages: list[Page], voice: str = DEFAULT_VOICE, speed: float = 1.0) -> None:
    narration_dir = course_dir / "narration"
    narration_dir.mkdir(parents=True, exist_ok=True)
    (course_dir / "audio").mkdir(exist_ok=True)
    manifest_pages = []
    for page in pages:
        (narration_dir / f"{page.stem}.txt").write_text(page.narration, encoding="utf-8")
        manifest_pages.append({
            "number": page.number,
            "stem": page.stem,
            "title": page.title,
            "reference_time": page.reference_time,
            "slide": f"slides/{page.stem}.png",
            "narration": f"narration/{page.stem}.txt",
            "audio": f"audio/{page.stem}.mp3",
        })
    (course_dir / "pages.json").write_text(
        json.dumps({"version": 1, "pages": manifest_pages}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (course_dir / "audio.md").write_text(
        "# Audio Settings\n\n"
        "- **provider:** doubao\n"
        f"- **voice_id:** {voice}\n"
        f"- **speed:** {speed}\n"
        "- **sample_rate:** 24000\n"
        "- **format:** mp3\n"
        "- **head_silence_sec:** 0.3\n"
        "- **tail_silence_sec:** 0.5\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx", type=Path)
    parser.add_argument("normalized_transcript", type=Path)
    parser.add_argument("course_dir", type=Path)
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--force", action="store_true", help="Replace prepared slides/narration/config, not audio")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    course = args.course_dir.resolve()
    try:
        if not args.voice.strip():
            raise PrepareError("voice must not be empty")
        if not 0.5 <= args.speed <= 2.0:
            raise PrepareError("speed must be between 0.5 and 2.0")
        targets = [course / "slides", course / "narration", course / "pages.json", course / "audio.md"]
        if not args.force and any(path.exists() for path in targets):
            raise PrepareError("prepared outputs already exist; use --force to replace them (audio is preserved)")
        pages = parse_normalized_transcript(args.normalized_transcript.read_text(encoding="utf-8"))
        course.mkdir(parents=True, exist_ok=True)
        if args.force:
            for pattern in ("slides/*.png", "narration/*.txt"):
                for path in course.glob(pattern):
                    path.unlink()
        slide_count = render_slides(args.pptx, course / "slides")
        validate_pages(pages, slide_count)
        write_outputs(course, pages, args.voice.strip(), args.speed)
    except (PrepareError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"prepared {len(pages)} pages in {course}")
    if (course / "audio").exists() and any((course / "audio").glob("*.mp3")):
        print("warning: existing audio was preserved; re-synthesize changed pages explicitly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
