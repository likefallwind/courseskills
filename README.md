# codex2course

[Claude Code](https://claude.ai/code) skills for course creation — from design to narrated lecture video:

| Skill | What it does |
|---|---|
| **ai-tutorials** | Design AI course syllabus, lectures, and hands-on projects |
| **codex2course** | Topic / outline → handout → slide images → PDF |
| **pdf2video** | Slide deck → per-slide narration → TTS audio → mp4 |
| **makecourse** | Publish existing course repos to aistudy101 and orchestrate the full generation pipeline when artifacts are missing |
| **movecourse** | Low-level video-only helper for copying generated lesson mp4 files into the website `course-assets` tree |

Each skill can be installed and used independently. `pdf2video` assumes the output layout produced by `codex2course`. `makecourse` can be used directly from an existing course repo for website publishing, and can also drive the full generation pipeline by shelling out to the `codex` CLI when artifacts are missing.

---

## Install

Requires [Node.js](https://nodejs.org/). Skills are installed to `~/.claude/skills/`. Restart Claude Code after installing.

### Single skill

```bash
npx skills add likefallwind/courseskills --skill ai-tutorials
npx skills add likefallwind/courseskills --skill codex2course
npx skills add likefallwind/courseskills --skill pdf2video
npx skills add likefallwind/courseskills --skill makecourse
npx skills add likefallwind/courseskills --skill movecourse
```

### All skills

```bash
npx skills add likefallwind/courseskills
```

<details>
<summary>Manual install (no Node.js)</summary>

```bash
# ai-tutorials
curl -fsSL https://raw.githubusercontent.com/likefallwind/courseskills/main/skills/ai-tutorials/SKILL.md \
  -o ~/.claude/skills/ai-tutorials.md

# codex2course
curl -fsSL https://raw.githubusercontent.com/likefallwind/courseskills/main/skills/codex2course/SKILL.md \
  -o ~/.claude/skills/codex2course.md

# pdf2video
curl -fsSL https://raw.githubusercontent.com/likefallwind/courseskills/main/skills/pdf2video/SKILL.md \
  -o ~/.claude/skills/pdf2video.md

# makecourse
curl -fsSL https://raw.githubusercontent.com/likefallwind/courseskills/main/skills/makecourse/SKILL.md \
  -o ~/.claude/skills/makecourse.md

# movecourse
curl -fsSL https://raw.githubusercontent.com/likefallwind/courseskills/main/skills/movecourse/SKILL.md \
  -o ~/.claude/skills/movecourse.md
```

</details>

---

## Prerequisites

### codex2course

- Claude Code with **imagegen** skill installed (used to render slide images)
- Python 3 + [Pillow](https://pillow.readthedocs.io/) for PDF assembly:
  ```bash
  pip install Pillow
  ```

### pdf2video

- Everything above, plus:
- [ffmpeg](https://ffmpeg.org/) on `PATH` (video assembly)
- [MINIMAX](https://www.minimaxi.com/) account + API key (TTS)
- Python 3 + `requests`:
  ```bash
  pip install requests
  ```
- Set your key before running:
  ```bash
  export MINIMAX_API_KEY=your_key_here
  ```

### makecourse

- For publishing existing courses: a local course repository with `lessonN/` folders and the aistudy101 website checkout at `/home/likefallwind/code/aistudy101-website`.
- For generating missing artifacts: everything above, plus the inner skills installed and [Codex CLI](https://github.com/openai/codex) on `PATH`.

### movecourse

- An AI-generated course directory containing `lessonN/*.mp4` files.
- The aistudy101 website checkout at `/home/likefallwind/code/aistudy101-website`.

---

## Usage

Start a conversation in Claude Code and describe your goal. The skills trigger automatically from natural language:

```
# ai-tutorials
Design a 10-lesson LLM application development course for CS undergrads.

# codex2course
Create a 6-hour Python async course for backend engineers.

# pdf2video  
Turn the course in ./course/ into a narrated lecture video, voice: male-qn-qingse.

# Full pipeline
Design a Vibe Coding course, then build slides and produce a narrated mp4.

# Publish an existing course repo
Publish this course repo to aistudy101.

# Publish generated videos only
Move only this generated course's videos to aistudy101 course-assets as ai-enlightenment.
```

These skills are incremental — they inspect what already exists and pick up at the next missing stage, so you can stop, review, and resume without redoing approved work.

### Course publishing and full pipeline (`makecourse`)

When an existing course repo should appear on the website, run `makecourse` from the course root. It first wires `course-sources.yaml` for lesson text and `course-assets.local.yaml` for local generated videos:

```bash
python ~/.agents/skills/makecourse/scripts/publish_course.py --source . --dry-run
python ~/.agents/skills/makecourse/scripts/publish_course.py --source . --write-course-yaml
```

When an automation agent (openclaw, hermes, …) needs to produce missing courseware first, it should load the same skill and shell out to the Codex CLI per stage:

```bash
codex exec --cd ./course --sandbox workspace-write \
  "Use the ai-tutorials skill to generate a complete course on '<topic>' …"

codex exec --cd ./course/lesson1 --sandbox workspace-write \
  "Use the codex2course skill on this directory …"

codex exec --cd ./course/lesson1 --sandbox workspace-write \
  "Use the pdf2video skill on this directory. TTS provider: edge …"
```

The skill itself documents the exact prompts, per-lesson loop, and verification checks. See [`skills/makecourse/SKILL.md`](skills/makecourse/SKILL.md).

---

## Output layout

```text
course/
├── outline.md          # Course info + image-gen settings
├── handout.md          # Full teaching notes (source of truth)
├── slide-units/        # Per-slide content, derived from handout.md
├── slides/             # Rendered .png pages (000-cover … zzz-ending)
├── course-deck.pdf     # Assembled slide deck
├── audio.md            # TTS voice / padding settings  (pdf2video)
├── narration/          # Per-slide spoken text          (pdf2video)
├── audio/              # Per-slide .mp3 files           (pdf2video)
└── course-video.mp4    # Final narrated lecture video   (pdf2video)
```

---

## Scripts

Several skills ship helper scripts used internally — you can also run them directly:

| Script | Purpose |
|---|---|
| `skills/codex2course/scripts/split_handout.py` | Slice `handout.md` into `slide-units/` |
| `skills/codex2course/scripts/images2pdf.py` | Combine `slides/*.png` into a PDF |
| `skills/pdf2video/scripts/synth_audio.py` | Call MINIMAX TTS for each narration file |
| `skills/pdf2video/scripts/assemble_video.py` | Pair slides + audio into `course-video.mp4` |
| `skills/movecourse/scripts/movecourse.py` | Copy or move `lessonN/*.mp4` into website course-assets |

```bash
python skills/codex2course/scripts/split_handout.py course/handout.md
python skills/codex2course/scripts/images2pdf.py course/slides course/course-deck.pdf
python skills/pdf2video/scripts/synth_audio.py course/
python skills/pdf2video/scripts/assemble_video.py course/
python skills/movecourse/scripts/movecourse.py --course ai-enlightenment --source course/ --dry-run
```
