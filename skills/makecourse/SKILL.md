---
name: makecourse
description: Use when publishing an existing AI course repository into the aistudy101 website, wiring course registry/local asset config, syncing lesson text and generated videos, or orchestrating full course generation from topic to handout/slides/video.
---

# Makecourse

## Overview

`makecourse` has two modes:

1. **Publish an existing course repo to aistudy101**: run from a repo like `.../course-outline/stage2/03-ai-concept`; register it in the website, wire local generated videos, run sync, and verify the learning page has lesson text plus video entries.
2. **Generate missing courseware**: when starting from a topic or rough outline, call `ai-tutorials`, `codex2course`, and `pdf2video` through `codex exec` to create handouts, slide decks, and narrated videos.

Default to publishing mode when the current directory already contains `lessonN/` folders. Do not treat publishing as "copy videos only": the website needs both `course-sources.yaml` for lesson text and `course-assets.local.yaml` for generated media that lives outside the remote repo layout.

## Publishing Existing Courses

### What the Website Reads

The aistudy101 website builds a course from two places:

- `course-sources.yaml`: remote repo metadata. Sync clones the repo and reads `README.md`, `introduction.md`, `syllabus.md`, `lesson*/outline.md`, `lesson*/handout.md`, and `lesson*/project.md`.
- `course-assets.local.yaml`: local generated media. Use this when videos are in `lesson*/deck/*.mp4` or another local-only render directory. Sync copies them to `static/course-assets/<course-id>/<lesson-id>/video/<lesson-id>-intro.mp4`.

If lesson text is local but not pushed to the remote repo, website sync will not see it. Commit and push source-repo content before expecting new text to appear on the site. Local video files do not need to be pushed if `course-assets.local.yaml` points to them.

### Inputs to Infer

Infer these before asking the user:

| Field | Source |
|---|---|
| Course root | Current directory or nearest parent containing `lessonN/` |
| Website root | `/home/likefallwind/code/aistudy101-website` unless user says otherwise |
| Course id | `course.yaml:id`, else folder name with leading `NN-` removed, e.g. `03-ai-concept` -> `ai-concept` |
| Repo URL | `git remote get-url origin`, converted from `git@gitee.com:owner/repo.git` to HTTPS |
| Branch | `git branch --show-current`, default `master` |
| Title | `course.yaml:title`, first H1 in `README.md`, `introduction.md`, or `syllabus.md` |
| Stage | path segment (`stage1` -> 小学, `stage2` -> 初中, `stage3` -> 高中), else course text |
| Hours | `总课时：N 节` from course text, else number of `lessonN/` folders |
| Video globs | `lesson*/deck/*.mp4`, `lesson*/video/*.mp4`, `lesson*/*.mp4` |

Ask the user only when a required field cannot be inferred safely, or when the inferred stage is `待确认`.

### Helper Script

Prefer the bundled script; it handles inference and edits both website config files consistently.

Dry-run first:

```bash
python ~/.agents/skills/makecourse/scripts/publish_course.py --source . --dry-run
```

Apply after reviewing the dry-run:

```bash
python ~/.agents/skills/makecourse/scripts/publish_course.py --source . --write-course-yaml
```

Useful overrides:

| Option | Use |
|---|---|
| `--course-id ai-concept` | Override inferred website id |
| `--repo-url https://gitee.com/likefallwind/aistudy-stage2-03-ai-concept` | Use when git origin is missing/private |
| `--stage 初中` | Override stage inference |
| `--track "AI 通识"` | Set website track |
| `--status 待审核` | Set course status |
| `--theme-line 机器学习` | Add one or more theme lines |
| `--video-glob 'lesson*/deck/*.mp4'` | Override local video discovery |
| `--write-course-yaml` | Create source `course.yaml` if it is missing |

The script updates:

- `<website>/course-sources.yaml`
- `<website>/course-assets.local.yaml`
- `<course>/course.yaml` only when `--write-course-yaml` is passed and the file does not already exist

### Publish Workflow

1. Locate the course root and website root.
2. Run the helper script with `--dry-run`.
3. Check the inferred `course_id`, `repo`, `branch`, `stage`, `hours`, and video globs. If any are wrong, rerun with overrides.
4. Apply the script.
5. If `course.yaml` was created or lesson text changed, commit and push the course repo before website sync. Do not auto-push unless the user explicitly asked.
6. Run website sync:

```bash
cd /home/likefallwind/code/aistudy101-website
npm run sync
```

7. Verify generated data and assets:

```bash
rg '"courseId": "<course-id>"' src/data/course-content.json
find static/course-assets/<course-id> -maxdepth 4 -type f | sort
```

Expected result: each lesson appears in `src/data/course-content.json` with outline/handout/project Markdown when those files exist, and generated videos appear under `static/course-assets/<course-id>/lessonN/video/`.

### Manual Fallback

If the helper script is unavailable:

1. Add or update `course-sources.yaml` with a `gitee` source entry and fallback metadata.
2. Add or update `course-assets.local.yaml`:

```yaml
courses:
  ai-concept:
    source_dir: /home/likefallwind/code/course-outline/stage2/03-ai-concept
    video_globs:
      - "lesson*/deck/*.mp4"
      - "lesson*/video/*.mp4"
      - "lesson*/*.mp4"
    video_publish_name: "{lesson_id}-intro{suffix}"
```

3. Run `npm run sync` in the website repo.
4. Verify `src/data/course-content.json` and `static/course-assets/<course-id>/lesson*/video/`.

## Generating Missing Courseware

Use this mode only when the user asks to create or complete course artifacts, not merely publish an existing repo.

### Stage 0: Preflight

- `command -v codex` must succeed.
- `~/.agents/skills/ai-tutorials/SKILL.md`, `codex2course`, and `pdf2video` should exist.
- Confirm whether review gates should stop for user approval or proceed automatically.

### Stage 1: Course Text via `ai-tutorials`

```bash
codex exec --cd "<course-root>" --sandbox workspace-write \
  "Use the ai-tutorials skill to generate or continue this course. Run the course design, syllabus, lesson handout, outline, project, and tool-requirements steps. Stop at review gates unless auto-approval was explicitly authorized."
```

Verify `introduction.md`, `syllabus.md`, and `lesson*/handout.md` exist.

### Stage 2: Slides via `codex2course`

For each selected lesson, use a `deck/` subdirectory so generated slide artifacts do not overwrite source lesson files:

```bash
mkdir -p "lessonN/deck"
cp -p "lessonN/outline.md" "lessonN/deck/outline.md"
cp -p "lessonN/handout.md" "lessonN/deck/handout.md"
codex exec --cd "lessonN/deck" --sandbox workspace-write \
  "Use the codex2course skill on this directory. The handout.md and outline.md already exist. Run slide marker annotation through PDF assembly."
```

Verify `lessonN/deck/slides/000-cover.png`, `zzz-ending.png`, and a `.pdf` exist.

### Stage 3: Video via `pdf2video`

```bash
codex exec --cd "lessonN/deck" --sandbox workspace-write \
  "Use the pdf2video skill on this directory. TTS provider: <edge|minimax>. Voice id: <voice_id if known>. Run sanity-check through final review. Stop at narration review unless auto-approval was explicitly authorized."
```

Verify exactly one non-empty `lessonN/deck/*.mp4` per rendered lesson.

### Stage 4: Publish

After generating videos, use the Publishing Existing Courses workflow above. Do not call the older `movecourse`-style video-only copy unless the user explicitly wants only video assets moved.

## Common Mistakes

- **Only copying videos.** That leaves lesson text invisible unless `course-sources.yaml` also registers the repo and sync runs.
- **Pointing video globs at `lesson*/*.mp4` only.** Most generated videos live under `lesson*/deck/*.mp4`.
- **Expecting local Markdown to sync without a push.** Website sync clones the remote repo for text content.
- **Using Chinese filenames in the public video path.** Publish as ASCII names like `lesson1-intro.mp4`.
- **Overwriting lesson source files with slide-render files.** Put slide/video artifacts in `lessonN/deck/`.
- **Skipping dry-run.** Always inspect the inferred course id and repo URL before writing website config.
