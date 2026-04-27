# codex2course

Two [Claude Code](https://claude.ai/code) skills for turning a course topic into a full narrated lecture video:

| Skill | What it does |
|---|---|
| **codex2course** | Topic / outline → handout → slide images → PDF |
| **pdf2video** | Slide deck → per-slide narration → TTS audio → mp4 |

Each skill can be installed and used independently. `pdf2video` assumes the output layout produced by `codex2course`.

---

## Install

Requires [Node.js](https://nodejs.org/). Skills are installed to `~/.claude/skills/`. Restart Claude Code after installing.

### codex2course only

```bash
npx skills add likefallwind/codex2course --skill codex2course
```

### pdf2video only

```bash
npx skills add likefallwind/codex2course --skill pdf2video
```

### Both skills

```bash
npx skills add likefallwind/codex2course
```

<details>
<summary>Manual install (no Node.js)</summary>

```bash
# codex2course
curl -fsSL https://raw.githubusercontent.com/likefallwind/codex2course/main/skills/codex2course/SKILL.md \
  -o ~/.claude/skills/codex2course.md

# pdf2video
curl -fsSL https://raw.githubusercontent.com/likefallwind/codex2course/main/skills/pdf2video/SKILL.md \
  -o ~/.claude/skills/pdf2video.md
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

---

## Usage

Start a conversation in Claude Code and describe your goal. The skills trigger automatically from natural language:

```
# codex2course
Create a 6-hour Python async course for backend engineers.

# pdf2video  
Turn the course in ./course/ into a narrated lecture video, voice: male-qn-qingse.

# Full pipeline (both skills)
Build a course on LLM prompt engineering, then produce a narrated mp4.
```

Both skills are incremental — they inspect what already exists and pick up at the next missing stage, so you can stop, review, and resume without redoing approved work.

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
