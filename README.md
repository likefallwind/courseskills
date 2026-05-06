# codex2course

[Claude Code](https://claude.ai/code) skills for course creation — from design to narrated lecture video:

| Skill | What it does |
|---|---|
| **ai-tutorials** | Design AI course syllabus, lectures, and hands-on projects |
| **codex2course** | Topic / outline → handout → slide images → PDF |
| **pdf2video** | Slide deck → per-slide narration → TTS audio → mp4 |
| **makecourse** | Orchestration skill for agents — chains the three skills above end-to-end via `codex exec` |

Each skill can be installed and used independently. `pdf2video` assumes the output layout produced by `codex2course`. `makecourse` is intended for automation agents (e.g. openclaw, hermes) that drive the full pipeline by shelling out to the `codex` CLI.

---

## Install

Requires [Node.js](https://nodejs.org/). Skills are installed to `~/.claude/skills/`. Restart Claude Code after installing.

### Single skill

```bash
npx skills add likefallwind/courseskills --skill ai-tutorials
npx skills add likefallwind/courseskills --skill codex2course
npx skills add likefallwind/courseskills --skill pdf2video
npx skills add likefallwind/courseskills --skill makecourse
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

- Everything above (the inner skills must be installed and reachable to `codex`).
- [Codex CLI](https://github.com/openai/codex) on `PATH` — the skill drives the pipeline by shelling out to `codex exec`.
- Run from an agent runtime that can execute shell commands (openclaw, hermes, scheduled bots, etc.). It is not designed for direct human invocation — call the inner skills directly instead.

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
```

All four skills are incremental — they inspect what already exists and pick up at the next missing stage, so you can stop, review, and resume without redoing approved work.

### Agent-driven full pipeline (`makecourse`)

When an automation agent (openclaw, hermes, …) needs to produce a full course unattended, it should load the `makecourse` skill and shell out to the Codex CLI per stage:

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

Both skills ship helper scripts used internally — you can also run them directly:

| Script | Purpose |
|---|---|
| `skills/codex2course/scripts/split_handout.py` | Slice `handout.md` into `slide-units/` |
| `skills/codex2course/scripts/images2pdf.py` | Combine `slides/*.png` into a PDF |
| `skills/pdf2video/scripts/synth_audio.py` | Call MINIMAX TTS for each narration file |
| `skills/pdf2video/scripts/assemble_video.py` | Pair slides + audio into `course-video.mp4` |

```bash
python skills/codex2course/scripts/split_handout.py course/handout.md
python skills/codex2course/scripts/images2pdf.py course/slides course/course-deck.pdf
python skills/pdf2video/scripts/synth_audio.py course/
python skills/pdf2video/scripts/assemble_video.py course/
```
