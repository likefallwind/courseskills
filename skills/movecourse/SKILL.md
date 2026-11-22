---
name: movecourse
description: Use when registering or publishing AI-generated course lesson mp4 files for the aistudy101 website, especially from lesson*/ directories through course-assets.local.yaml and local video symlinks.
---

# Movecourse

## Overview

Register generated lesson videos from a course-generation workspace for the aistudy101 website. Resolve and validate the course id against `docs/course-id-registry.md` and `course-sources.yaml`, validate `lessonN/*.mp4` in the source course directory, then add or update `course-assets.local.yaml` so `npm run sync` writes video URL metadata.

The default workflow keeps videos out of the website `static/` tree. Local development exposes those videos through `.docusaurus/local-video-assets` symlinks created by `scripts/link_video_assets.py`, which is run by `./scripts/dev.sh` and `npm run start`.

Only use direct static copying for explicit local preview with `npm run sync -- --publish-video-assets` or the helper script's `--publish-static` flag. Delete generated originals only when the user explicitly asks for a true move and `--publish-static` is being used.

When this workflow adjusts or registers course metadata, default the course status to `已发布` after the course is ready, unless the user gives a different status or special instruction.

## When to Use

Use this skill when:
- The user says to move, publish, upload, install, or sync AI-generated course videos to aistudy101.
- The current directory looks like `.../course-outline/.../<course>/lesson1`, `lesson2`, etc.
- Each lesson directory contains one generated `.mp4` that should become website video URL metadata such as `/course-assets/<course-id>/lessonN/video/lessonN-intro.mp4`.

Do not use this skill for slide rendering, narration generation, or video assembly. Use `codex2course` or `pdf2video` first.

## Required Inputs

| Input | Default / source |
|---|---|
| Source course directory | Current working directory, unless user gives a path |
| Course id | Ask the user if not provided; examples: `ai-enlightenment`, `python-intro` |
| Local asset config | `/home/likefallwind/code/aistudy101-website/course-assets.local.yaml` |
| Course registry | `/home/likefallwind/code/aistudy101-website/course-sources.yaml` |
| Course ID registry | `/home/likefallwind/code/aistudy101-website/docs/course-id-registry.md` |
| Website repo root | `/home/likefallwind/code/aistudy101-website` |
| Optional static preview root | `/home/likefallwind/code/aistudy101-website/static/course-assets` |

If the course id is not listed in `course-sources.yaml`, distinguish these cases:

- If the user only gave a Chinese title or curriculum placement, first look it up in `docs/course-id-registry.md`. Reuse that ID when present, even if the course is still marked `预留`.
- If the title is absent from the ID registry, inspect the source directory name, `README.md`, git remote, and `ai-study-101-curriculum-system-v0.3.md`. Choose a conservative lowercase kebab-case id only when it is obvious, then update `docs/course-id-registry.md`; otherwise ask.
- If the user expects this to become a real website course, register it in `course-sources.yaml` before or alongside video registration. Prefer the source repo remote URL when available, and include fallback metadata matching the curriculum placement.
- If the source videos live only on this machine, add or update `course-assets.local.yaml` so `npm run sync` can write video URL metadata from the local source directory.
- Use `--allow-unknown-course` only when the user explicitly wants local/static preview assets for an unregistered course id.

## Default Workflow

1. Inspect the source directory for direct child folders named `lessonN`.
2. In each lesson folder, require exactly one direct `.mp4`; report missing, empty, or duplicate videos before writing anything.
3. Resolve the course id from `docs/course-id-registry.md` when the user gave a Chinese title, then validate it against the ID registry or `course-sources.yaml`.
4. Add or update `course-assets.local.yaml`:

   ```yaml
   courses:
     python-advanced:
       source_dir: /home/likefallwind/code/course-outline/stage3/01-python-advanced
       video_globs:
         - "lesson*/*.mp4"
       video_publish_name: "{lesson_id}-intro{suffix}"
   ```

5. Dry-run first. The helper prints the local config mapping and expected URLs:

   ```text
   /course-assets/<courseId>/<lessonId>/video/<lessonId>-intro.mp4
   ```

6. From the website repo, run `npm run sync` so `src/data/course-content/<courseId>.json`, `src/data/courses.json`, and `src/data/curriculum-map.json` reference the videos.
7. Start local dev with `./scripts/dev.sh` or `npm run start`. Startup runs `scripts/link_video_assets.py`, which exposes local videos under `.docusaurus/local-video-assets`.
8. If course metadata was changed, set the course status to `已发布` by default. Follow the user's explicit status instead if they provide one, such as `待审核` or `AI初稿`.
9. Run `npm run build` when the change should be ready for review or deployment.

`course-assets.local.yaml` is git-ignored; mention it in the final status, but do not expect it to show up in `git diff`.

## Static Preview Escape Hatch

Website videos should not be placed in `static/` by default. For a local static preview only, explicitly run:

```bash
npm run sync -- --publish-video-assets
```

or use the helper's direct-copy mode:

```bash
python ~/.agents/skills/movecourse/scripts/movecourse.py --course ai-enlightenment --publish-static
```

This writes the same `course-assets.local.yaml` entry, then copies videos to:

```text
static/course-assets/<course-id>/lessonN/video/lessonN-intro.mp4
```

Use `--overwrite` when replacing existing preview files. Use `--move` only when the user explicitly asked to remove the source videos; it requires `--publish-static`.

## New Course Registration

When the user says a source course "corresponds to" a curriculum item, treat the task as both course registration and video registration.

1. Check whether the curriculum item already exists as a clickable course in `src/data/curriculum-map.json`.
2. If it is still a non-clickable placeholder, add a `course-sources.yaml` entry with:
   - `id`: the stable ID from `docs/course-id-registry.md`; add a registry row first if the curriculum item is new.
   - `type: gitee`
   - `repo`: the source repo URL from `git -C <source> remote -v` when present.
   - `fallback`: title, stage, education phase, track, status, hours, and theme lines. Use `status: 已发布` by default after the course has been adjusted, unless the user explicitly specifies another status.
3. If the source repo cannot be cloned due to Gitee credentials, keep the registry entry and rely on `course-assets.local.yaml` for the local source fallback.
4. After `npm run sync`, confirm the course appears in:
   - `src/data/courses.json`
   - `src/data/course-content/<courseId>.json`
   - `src/data/curriculum-map.json`

## Helper Script

Prefer the bundled script because it preflights all lessons before writing:

```bash
python ~/.agents/skills/movecourse/scripts/movecourse.py --course ai-enlightenment --dry-run
python ~/.agents/skills/movecourse/scripts/movecourse.py --course-title "Python 编程进阶" --dry-run
python ~/.agents/skills/movecourse/scripts/movecourse.py --course ai-enlightenment
```

Useful options:

| Option | Use |
|---|---|
| `--source PATH` | Source course directory; defaults to `pwd` |
| `--course ID` | Course id to update in `course-assets.local.yaml` |
| `--course-title TITLE` | Resolve a Chinese curriculum title through `docs/course-id-registry.md` |
| `--dry-run` | Print planned local config and expected URLs without writing |
| `--video-publish-name '{lesson_id}-intro{suffix}'` | Filename template stored in local config |
| `--video-glob 'lesson*/*.mp4'` | Video glob stored in local config; may be repeated |
| `--publish-static` | Copy videos into `static/course-assets` for local preview only |
| `--overwrite` | Replace existing static preview mp4 files |
| `--move` | Delete source mp4 after verified static copy; requires `--publish-static` |
| `--allow-unknown-course` | Continue when course id is absent from both `course-sources.yaml` and the ID registry |

After updating local config, verify the website data:

```bash
npm run sync
rg -n "python-advanced|Python 编程进阶" src/data/courses.json src/data/course-content src/data/curriculum-map.json
./scripts/dev.sh
```

If `npm run sync` reports a Gitee clone/auth failure but then says it used `course-assets.local.yaml`, that is acceptable for local publishing. The final sync summary should have `error: 0`.

## Manual Fallback

If the script is unavailable, validate course id and mp4 counts first, then add or update:

```yaml
courses:
  ai-enlightenment:
    source_dir: /absolute/path/to/generated/course
    video_globs:
      - "lesson*/*.mp4"
    video_publish_name: "{lesson_id}-intro{suffix}"
```

Then run:

```bash
cd /home/likefallwind/code/aistudy101-website
npm run sync
./scripts/dev.sh
```

For static preview only:

```bash
npm run sync -- --publish-video-assets
```

## Common Mistakes

- **Copying videos into `static/` by default.** Keep large videos outside the website repo; use local config plus sync URL metadata.
- **Using the Chinese source filename as the publish name.** Use English/ASCII-safe names; default `lessonN-intro.mp4` is acceptable and matches existing courses.
- **Skipping the course ID registry.** `ai-enlightenment` is a course id; the Chinese title `AI 启蒙体验` should be resolved through `docs/course-id-registry.md`, not guessed from a folder name.
- **Publishing videos without registering a new course.** Local video config can exist while the course map remains non-clickable. Add `course-sources.yaml` and run `npm run sync`.
- **Forgetting local dev symlinks.** After sync, use `./scripts/dev.sh` or `npm run start` so `scripts/link_video_assets.py` exposes local videos.
- **Treating Gitee clone failures as fatal when a local source exists.** If sync falls back to `course-assets.local.yaml` and ends with `error: 0`, report the warning but continue verification.
- **Copying after the first valid lesson without preflight.** Validate every lesson first to avoid a partial config or preview publish.
- **Overwriting existing preview videos silently.** Use dry-run and require `--overwrite` when static preview files already exist.
- **Deleting generated originals by default.** Treat "move to server position" as publishing metadata unless the user explicitly asks to remove the source files.
