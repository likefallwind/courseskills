---
name: makecourse
description: Use when publishing an AI-generated course directory into the aistudy101 website. The user provides the generated course path and says which curriculum course it corresponds to; Codex must register the course, keep the source repo link, copy generated lesson videos into website assets through sync, update data, run build verification, and leave source videos untouched.
---

# Makecourse

## Scope

Use this skill when a user says an AI-generated course should go online on the aistudy101 website, especially when they provide a path such as `/home/likefallwind/code/course-outline/stage2/03-ai-concept` and a curriculum placement such as `初中 机器学习概念入门（通识）`.

This skill is for **publishing an already generated course**, not for creating handouts, slides, or narration. If the user asks to generate course content first, use the relevant course-generation skills before returning here.

## Website Contract

The website root is normally:

```text
/home/likefallwind/code/aistudy101-website
```

Publishing requires both:

- `course-sources.yaml`: course registry and source repo metadata. The sync step clones the repo and reads `README.md`, `introduction.md`, `syllabus.md`, `lesson*/outline.md`, `lesson*/handout.md`, and `lesson*/project.md`.
- `course-assets.local.yaml`: local media source config. The sync step copies local videos into `static/course-assets/<course-id>/<lesson-id>/video/<lesson-id>-intro.mp4`.

Generated videos must be **copied**, never moved or deleted. Source course files and source videos should remain in place.

## Inputs To Infer

Infer these before asking questions:

| Field | Source |
|---|---|
| Course root | User path, current directory, or nearest parent with `lessonN/` folders |
| Website root | `/home/likefallwind/code/aistudy101-website` unless user says otherwise |
| Course id | `course.yaml:id`, else folder name without leading `NN-`, e.g. `03-ai-concept` -> `ai-concept` |
| Repo URL | `git remote get-url origin`; keep SSH form such as `git@gitee.com:owner/repo.git` when available |
| Branch | `git branch --show-current`, default `master` |
| Title | User wording first, else `course.yaml:title`, else course info in `introduction.md`, else first H1 |
| Stage | User wording first, else path segment: `stage1` 小学, `stage2` 初中, `stage3` 高中 |
| Track | User wording: `通识` -> `AI 通识`; otherwise infer conservatively |
| Status | User wording first; if they say uploaded/ready/上线, usually `已发布`; otherwise `待审核` |
| Hours | `总课时：N 节` from course text, else count `lessonN/` directories |
| Video globs | `lesson*/deck/*.mp4`, `lesson*/video/*.mp4`, `lesson*/*.mp4` |

Ask only when a required field cannot be inferred safely, or when the course id/title would be ambiguous.

## Preferred Helper

Use the bundled helper so config edits are consistent:

```bash
python /home/likefallwind/code/courseskills/skills/makecourse/scripts/publish_ai_course.py \
  --source /path/to/generated-course \
  --dry-run
```

Apply after reviewing the dry-run:

```bash
python /home/likefallwind/code/courseskills/skills/makecourse/scripts/publish_ai_course.py \
  --source /path/to/generated-course \
  --title "机器学习概念入门" \
  --stage 初中 \
  --track "AI 通识" \
  --status 已发布
```

Useful overrides:

| Option | Use |
|---|---|
| `--course-id ai-concept` | Set website course id |
| `--repo-url git@gitee.com:likefallwind/aistudy-stage2-03-ai-concept.git` | Prefer SSH repo URL to avoid HTTPS username prompts |
| `--branch master` | Set source branch |
| `--title "机器学习概念入门"` | Match curriculum course title |
| `--stage 初中` | Match curriculum stage |
| `--track "AI 通识"` | Match curriculum track |
| `--status 已发布` | Publish immediately |
| `--theme-line 机器学习` | Add one or more theme lines |
| `--video-glob "lesson*/deck/*.mp4"` | Override video discovery |

The helper updates only website-side files:

- `<website>/course-sources.yaml`
- `<website>/course-assets.local.yaml`

It does **not** edit, move, delete, commit, or push the generated course repo.

## Workflow

1. Inspect the course root:

```bash
find <course-root> -maxdepth 3 -type f | sort | sed -n '1,160p'
git -C <course-root> remote -v
git -C <course-root> branch --show-current
```

2. Confirm lesson count and videos. There should usually be one mp4 per lesson. Video files often have Chinese names under `lessonN/deck/`; that is fine because sync publishes them as ASCII names.

3. Run the helper dry-run. Check:

- course id
- title
- stage / track / status
- repo URL, preferably SSH
- branch
- hours
- video globs

4. Apply the helper with overrides from the user’s curriculum mapping.

5. Run website sync:

```bash
cd /home/likefallwind/code/aistudy101-website
npm run sync
```

Expected effect:

- source Markdown appears in `src/data/course-content.json`
- local videos are copied to `static/course-assets/<course-id>/lessonN/video/<lessonN>-intro.mp4`
- source mp4 files remain untouched

6. Verify data and assets:

```bash
node -e 'const fs=require("fs"); const id="<course-id>"; const c=JSON.parse(fs.readFileSync("src/data/courses.json","utf8")).find(x=>x.id===id); const cc=JSON.parse(fs.readFileSync("src/data/course-content.json","utf8")).courses.find(x=>x.courseId===id); console.log({title:c?.title,status:c?.status,repo:c?.links?.repo,lessons:cc?.lessons?.length,videos:cc?.lessons?.reduce((n,l)=>n+l.videos.length,0)});'
find static/course-assets/<course-id> -path '*/video/*.mp4' -type f | sort
```

7. Build verification:

```bash
npm run typecheck
npm run build
rg "开始学习|/courses/<course-id>/learn|statusBadge--已发布" build/courses/<course-id>/index.html
```

If `开始学习` is missing but `src/data/courses.json` says `已发布`, rerun `npm run build`; Docusaurus static pages may still contain stale data from a previous build.

## SSH Repo Rule

Prefer SSH repo URLs in `course-sources.yaml` when the source repo is on Gitee and SSH works:

```yaml
repo: git@gitee.com:likefallwind/aistudy-stage2-03-ai-concept.git
```

Do not normalize SSH to HTTPS for sync. The frontend can display the SSH string while linking to the HTTPS web page; the learning page can convert SSH to HTTPS raw URLs for image fallback.

If sync fails with an HTTPS username prompt, switch the course source to SSH and rerun `npm run sync`.

## Manual Fallback

If the helper is unavailable, edit website config directly.

`course-sources.yaml`:

```yaml
  - id: ai-concept
    type: gitee
    repo: git@gitee.com:likefallwind/aistudy-stage2-03-ai-concept.git
    branch: master
    fallback:
      title: 机器学习概念入门
      stage: 初中
      education_phase: 基础教育
      track: AI 通识
      status: 已发布
      version: "0.1"
      hours: 10
      theme_lines: [AI 素养, 机器学习]
```

`course-assets.local.yaml`:

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

Then run `npm run sync`, `npm run typecheck`, and `npm run build`.

## Common Mistakes

- Only copying videos without registering `course-sources.yaml`; the course page will lack lesson text.
- Moving source mp4 files; always copy through sync.
- Keeping Gitee HTTPS when the repo requires credentials; prefer SSH.
- Forgetting `course-assets.local.yaml`; generated mp4 files outside the repo layout will not publish.
- Assuming `已发布` immediately changes `build/`; Docusaurus needs rebuild.
- Letting `deck/slides` images with Chinese filenames enter public assets; sync should ignore deck internals and publish only needed lesson assets and videos.
- Overwriting unrelated registry formatting or user changes; keep diffs focused.
