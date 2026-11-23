---
name: ppt2video
description: Use when turning a PowerPoint PPTX and a page-mapped verbatim transcript into a narrated course video, especially PPT/PPT转视频, 逐字稿配音, static lecture slides, and Doubao male-teacher narration.
---

# PPT2Video

## Overview

Convert a `.pptx` plus its original transcript into a 1920×1080, 30 fps H.264/AAC video. Each static slide remains visible for its actual narration length plus padding. Animations, transitions, and embedded media are flattened by the slide export.

The important boundary is **normalize first, parse second**: understand the raw transcript and write one canonical intermediate file. The Python parser accepts only that format; it does not guess raw headings such as `第N页` or `本页逐字稿`.

## Requirements

- Sibling skills `doubao-voice` and `pdf2video` from this repository.
- `soffice` (LibreOffice), `pdftoppm` (Poppler), `ffmpeg`, and `ffprobe` on PATH.
- For real synthesis, the Doubao Gateway configuration documented by **doubao-voice**. Never place credentials in `audio.md`.

Check tools before starting. Keep inputs read-only and write products to a separate course output directory, not the skill directory.

## Workflow

### 1. Normalize the original transcript

Read the original transcript and create `<course-dir>/transcript.normalized.md` in exactly this format:

```text
=== PAGE 001 ===
TITLE: 封面
REFERENCE_TIME: 0:00—0:15
=== NARRATION ===
同学们好，这一章我们进入……
=== END PAGE ===

=== PAGE 002 ===
TITLE: 本章知识地图
REFERENCE_TIME: 0:15—0:30
=== NARRATION ===
本章不要求大家一次记住所有公式……
=== END PAGE ===
```

- Copy only the spoken body into `NARRATION`, verbatim. Do not summarize, polish, or add an introduction.
- Keep page titles and reference times only as optional metadata. Exclude document preambles, production notes, usage instructions, suggested durations, and separators from narration.
- Use ascending, contiguous, zero-padded page numbers. Each marker must occupy its own line; reserved markers cannot occur inside narration.
- If page ownership is ambiguous, a body is missing, or duplicate/missing pages cannot be resolved from the source, stop and ask. Do not renumber guesses or synthesize a partial deck.

### 2. Render and validate

From the repository/plugin root:

```bash
python skills/ppt2video/scripts/prepare_course.py \
  /path/to/input.pptx /path/to/course/transcript.normalized.md /path/to/course
```

This renders PPTX → PDF → `slides/001.png…`, writes plain-text `narration/001.txt…`, `pages.json`, and `audio.md`, then verifies the 1:1 page mapping. No TTS request is made. Existing prepared outputs are protected; use `--force` only with explicit approval. It preserves existing audio, which must then be reviewed for staleness.

Default audio is **渊博小叔 2.0** (`zh_male_yuanboxiaoshu_uranus_bigtts`), speed `1.0`, MP3 at 24 kHz. For alternatives and the official update link, use **doubao-voice** and its `references/voices.md`. `--voice` and `--speed` can override preparation defaults.

### 3. Review and audition before paid synthesis

Show the extracted page mapping for review. Before the first Gateway request, confirm voice, speed, and synthesis usage with the user. Generate only page 1:

```bash
python skills/ppt2video/scripts/synth_audio.py /path/to/course --only 001
```

Stop for the user to listen. Do not proceed to the remaining pages until they approve the audition.

### 4. Synthesize and assemble

After approval:

```bash
python skills/ppt2video/scripts/synth_audio.py /path/to/course
python skills/pdf2video/scripts/assemble_video.py \
  /path/to/course --output /path/to/course/course-video.mp4
```

The synthesis script validates the entire course before any request, skips existing MP3s, and stops on the first failure without retrying. The assembler adds 0.3 seconds before and 0.5 seconds after each narration by default. Reference durations never stretch or truncate audio.

## Single-page revision

After the user approves regenerating that page and its additional usage:

```bash
python skills/ppt2video/scripts/synth_audio.py /path/to/course --only 003 --force
python skills/pdf2video/scripts/assemble_video.py \
  /path/to/course --output /path/to/course/course-video.mp4
```

Edit only `narration/003.txt` for a wording change. Do not use bare `--force` for a one-page fix: it regenerates every selected cached page. Video assembly rebuilds the full MP4 and overwrites its output; preserve a prior video first if the user wants to keep it.

## Output and quality bar

```text
course/
├── transcript.normalized.md
├── slides/001.png…
├── narration/001.txt…
├── audio/001.mp3…
├── pages.json
├── audio.md
└── course-video.mp4
```

- Slide, narration, and audio stems and counts match exactly.
- Narration contains only source body text; reference times and instructions are absent.
- Audio plays completely with one consistent approved voice and speed.
- Final video has the correct page order, duration, 1920×1080/30 fps video, AAC audio, and no missing streams.
- Generated media stays outside the skill directory and is not committed.

## Common mistakes

| Mistake | Correct action |
|---|---|
| Running the parser directly on a raw transcript | Normalize it first; the parser intentionally rejects raw headings |
| Matching more raw keywords in Python | Improve the normalization instructions, not the canonical parser |
| Treating reference duration as target audio length | Use actual audio duration; reference time is metadata only |
| Retrying or switching providers after a Gateway error | Stop, preserve completed takes, and follow **doubao-voice** guidance |
| Regenerating all audio to fix one page | Use `--only NNN --force` with explicit approval |

Run offline checks with `python -m unittest discover -s skills/ppt2video/tests -v`.
