---
name: movecourse
description: Use when publishing AI-generated course lesson mp4 files into the aistudy101 website course-assets tree, especially from lesson*/ directories into static/course-assets/<course-id>/lesson*/video.
---

# Movecourse

## Overview

Move or publish generated lesson videos from a course-generation workspace into the aistudy101 website assets tree. Validate the requested course id against `course-sources.yaml`, map `lessonN/*.mp4` to the matching website lesson folder, and use English filenames.

Default behavior is a safe publish copy. Delete the generated originals only when the user explicitly asks for a true move.

## When to Use

Use this skill when:
- The user says to move, publish, upload, install, or sync AI-generated course videos to aistudy101.
- The current directory looks like `.../course-outline/.../<course>/lesson1`, `lesson2`, etc.
- Each lesson directory contains one generated `.mp4` that should land under `/home/likefallwind/code/aistudy101-website/static/course-assets/<course-id>/lessonN/video/`.

Do not use this skill for slide rendering, narration generation, or video assembly. Use `codex2course` or `pdf2video` first.

## Required Inputs

| Input | Default / source |
|---|---|
| Source course directory | Current working directory, unless user gives a path |
| Course id | Ask the user if not provided; examples: `ai-enlightenment`, `python-intro` |
| Destination root | `/home/likefallwind/code/aistudy101-website/static/course-assets` |
| Course registry | `/home/likefallwind/code/aistudy101-website/course-sources.yaml` |

If the course id is not listed in `course-sources.yaml`, stop and tell the user it may be a typo. Proceed only after explicit confirmation.

## Workflow

1. Inspect the source directory for direct child folders named `lessonN`.
2. In each lesson folder, require exactly one direct `.mp4`; report missing or duplicate videos before copying anything.
3. Validate the course id against `course-sources.yaml`.
4. Create missing destination folders: `<dest-root>/<course-id>/lessonN/video/`.
5. Write English filenames. Default to the existing website convention: `lessonN-intro.mp4`.
6. Dry-run first, then execute the copy or true move.
7. Verify every destination file exists and has a non-zero size. Print a source-to-destination manifest.

## Helper Script

Prefer the bundled script because it preflights all lessons before writing:

```bash
python ~/.agents/skills/movecourse/scripts/movecourse.py --course ai-enlightenment --dry-run
python ~/.agents/skills/movecourse/scripts/movecourse.py --course ai-enlightenment
```

Useful options:

| Option | Use |
|---|---|
| `--source PATH` | Source course directory; defaults to `pwd` |
| `--course ID` | Required course id under `course-assets` |
| `--dry-run` | Print planned operations without writing |
| `--overwrite` | Replace existing destination mp4 files |
| `--move` | Delete source mp4 after verified copy; use only when user explicitly asked |
| `--allow-unknown-course` | Continue when course id is absent from `course-sources.yaml` |
| `--filename-template '{lesson}-intro.mp4'` | English output pattern |

## Manual Fallback

If the script is unavailable, validate course id and mp4 counts first, then:

```bash
COURSE_ID="ai-enlightenment"
SRC="$PWD"
DST="/home/likefallwind/code/aistudy101-website/static/course-assets/$COURSE_ID"

for lesson_dir in "$SRC"/lesson*; do
  lesson="$(basename "$lesson_dir")"
  video_dir="$DST/$lesson/video"
  mkdir -p "$video_dir"
  cp -p "$lesson_dir"/*.mp4 "$video_dir/$lesson-intro.mp4"
done
```

## Common Mistakes

- **Using the Chinese source filename in the website tree.** Rename to English; default `lessonN-intro.mp4` is acceptable and matches existing courses.
- **Skipping course-id validation.** `ai-enlightenment` is a course id; the Chinese title `AI 启蒙体验` is not the destination folder name.
- **Copying after the first valid lesson without preflight.** Validate every lesson first to avoid a half-published course.
- **Overwriting existing videos silently.** Use dry-run and require `--overwrite` when destination files already exist.
- **Deleting generated originals by default.** Treat "move to server position" as a publish copy unless the user explicitly asks to remove the source files.
