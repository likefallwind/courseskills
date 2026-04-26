#!/usr/bin/env python3
"""Combine slide images from a directory into a single PDF file.

Images are sorted by filename (ascending), so the naming convention
000-cover.png < 001-*.png < ... < zzz-ending.png produces the correct
page order automatically.

Usage:
    python images2pdf.py <slides-dir> [output.pdf]

Default output path is <slides-dir>/../course-deck.pdf.

Supported image formats: PNG, JPG/JPEG, WEBP, BMP, TIFF.
"""
import argparse
import sys
from pathlib import Path

SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}


def collect_images(slides_dir: Path) -> list[Path]:
    paths = sorted(
        p for p in slides_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    )
    return paths


def build_pdf(image_paths: list[Path], output: Path) -> None:
    try:
        from PIL import Image
    except ImportError:
        sys.exit("Pillow is required: pip install Pillow")

    imgs = [Image.open(p).convert("RGB") for p in image_paths]
    output.parent.mkdir(parents=True, exist_ok=True)
    imgs[0].save(output, save_all=True, append_images=imgs[1:])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("slides_dir", help="Directory containing slide images")
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Output PDF path (default: <slides-dir>/../course-deck.pdf)",
    )
    args = parser.parse_args()

    slides_dir = Path(args.slides_dir)
    if not slides_dir.is_dir():
        sys.exit(f"Slides directory not found: {slides_dir}")

    output = Path(args.output) if args.output else slides_dir.parent / "course-deck.pdf"

    image_paths = collect_images(slides_dir)
    if not image_paths:
        sys.exit(f"No supported images found in: {slides_dir}")

    print(f"Found {len(image_paths)} images:")
    for p in image_paths:
        print(f"  {p.name}")

    build_pdf(image_paths, output)
    print(f"\nPDF saved to: {output}")


if __name__ == "__main__":
    main()
