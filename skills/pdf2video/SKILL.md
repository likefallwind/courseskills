---
name: pdf2video
description: Use when turning a codex2course-produced course package (outline.md + handout.md + slide-units/ + slides/*.png) into a narrated lecture video — writes per-slide narration, synthesizes voice via MINIMAX TTS, and assembles slides + audio into a single mp4 with ffmpeg.
---

# Pdf2Video

## Overview

Take a course package already produced by `codex2course` and turn it into a narrated lecture video. Stages: sanity-check inputs → set audio params → write per-slide narration (hard stop for review) → synthesize per-slide audio → assemble slides + audio into one `course-video.mp4` with ffmpeg.

**REQUIRED UPSTREAM:** This skill assumes a directory produced by `codex2course` — `outline.md`, `handout.md`, `slide-units/NNN-*.md`, `slides/000-cover.png` + `NNN-*.png` + `zzz-ending.png`. If anything is missing, send the user back to `codex2course` first.

## When to Use

Use this skill for:
- Adding a voiced narration track to an already-rendered slide deck
- Producing lecture / tutorial / training videos where each slide stays on screen for the duration of its narration
- Regenerating audio or video for a small set of slides after content edits

Do not use this skill when:
- Slides have not been rendered yet — run `codex2course` first
- The user wants live-action video, screen recording, or animated transitions — this skill produces static-image-per-page video only

## Workflow

Each stage is independently invocable. Inspect what already exists (`audio.md`, `narration/`, `audio/`, `course-video.mp4`) and start at the next missing stage — do not redo work the user already approved.

All narration text must match the language of the slides / handout.

1. **Sanity-check inputs.** Confirm the course directory has `outline.md`, `handout.md`, `slide-units/` (with `NNN-*.md` files), and `slides/` (with `000-cover.png`, content `NNN-*.png`, and `zzz-ending.png`). The `NNN-*` slug stems must match between `slide-units/` and `slides/`. If anything is missing, stop and tell the user to complete `codex2course` first.
2. **Write `audio.md`.** If `audio.md` doesn't exist, gather TTS / voice settings (defaulting to MINIMAX sync), pull `target audience` from `outline.md`'s `## Course Info` as a tone cue, and write `audio.md` using the Audio Settings Template below. Ask the user for any missing voice preference (voice_id, speed, emotion). Do not invent a voice.
3. **Draft narration files.** For every image in `slides/` (cover + content + ending), write a matching `narration/<same-stem>.md`:
   - **Cover** (`narration/000-cover.md`) — opening: who's speaking (instructor + institution from `outline.md`), what the course covers, who it's for. Required.
   - **Content** (`narration/NNN-<slug>.md`) — spoken-style narration for the slide. Source: the matching `slide-units/NNN-<slug>.md` plus `outline.md` for global context. **Spoken style, not the handout verbatim** — short sentences, oral connectives, no bullet-list scaffolding. Default target ~60–180 seconds (≈ 200–600 Chinese characters / 150–450 English words). Stay well below the 10 000-character TTS hard limit.
   - **Ending** (`narration/zzz-ending.md`) — thanks + Q&A invitation. Required.
4. **STOP for narration review.** List all narration files and explicitly ask the user to review and approve. Tell them this is the cheapest revision point — past this gate, every change burns TTS API quota. Do not proceed until the user confirms. Encourage edits to tone, density, and per-page emphasis.
5. **Synthesize audio.** Run `python scripts/synth_audio.py <course-dir>`. The script reads `audio.md`, walks `narration/*.md`, calls MINIMAX `/v1/t2a_v2`, decodes the hex audio, and writes `audio/<same-stem>.mp3`. Existing mp3 files are skipped (cache); use `--only <prefix>` to scope and `--force` to overwrite. `MINIMAX_API_KEY` must be set in the environment.
6. **Per-slide regeneration loop.** When the user reviews audio and reports issues, fix scoped:
   - Wording wrong → edit `narration/NNN-*.md` → delete `audio/NNN-*.mp3` → `python scripts/synth_audio.py <course-dir> --only NNN` → re-assemble video.
   - Voice/speed/emotion wrong globally → edit `audio.md` → delete the affected `audio/*.mp3` files → rerun synth → re-assemble.
   - Slide image wrong → that's a `codex2course` task, not this skill.
   - Handout content wrong → fix in `codex2course` (edit handout, rerun split, re-render the affected image), then update the matching narration here and re-synthesize.
   Never blanket-regenerate the whole `audio/` directory to fix a single page.
7. **Assemble video.** Run `python scripts/assemble_video.py <course-dir>`. It pairs `slides/*.png` with `audio/*.mp3` in alphabetical order (so `000-cover` → `001-…` → `…` → `zzz-ending` is automatic), renders each page to a temp mp4 with `head_silence_sec` / `tail_silence_sec` padding from `audio.md`, then concatenates into `<course-dir>/course-video.mp4`. Output is 1920×1080, H.264, AAC, 30 fps. Requires `ffmpeg` on PATH.
8. **Final review.** Tell the user where the mp4 landed and ask them to play it through. If a single page needs fixing, return to step 6.

## Output Structure

Builds on the existing `codex2course` layout:

```text
course/
├── outline.md            # existing, read-only here
├── handout.md            # existing, read-only here
├── slide-units/          # existing — narration source per slide
├── slides/               # existing — video frames
├── course-deck.pdf       # existing
├── audio.md              # NEW — course-level audio settings
├── narration/            # NEW — 1:1 with slides/, .md per page
│   ├── 000-cover.md
│   ├── 001-<slug>.md
│   ├── ...
│   └── zzz-ending.md
├── audio/                # NEW — 1:1 with narration/, .mp3 per page
│   ├── 000-cover.mp3
│   ├── 001-<slug>.mp3
│   ├── ...
│   └── zzz-ending.mp3
└── course-video.mp4      # final deliverable
```

**Hard rule:** filename stems must be identical across `slides/`, `narration/`, and `audio/`. Alphabetical sort is the pairing key — any mismatch silently misaligns voice and image.

## Audio Settings Template

`audio.md` has three required sections:

```markdown
# Audio Settings

## TTS Provider

- **Endpoint:** https://api.minimaxi.com/v1/t2a_v2
- **Model:** speech-01-turbo
- **API key env var:** MINIMAX_API_KEY

> Default `speech-01-turbo` works on the broadest set of MINIMAX plans. If your account has access to a higher-quality model (e.g. `speech-02-hd`, `speech-2.6-hd`, `speech-2.8-hd`), switch here. A 2061 "your current token plan not support model" error means you need a different model.

## Voice

- **voice_id:** <e.g., male-qn-qingse>
- **speed:** 1.0
- **emotion:** calm
- **language:** Chinese
- **sample_rate:** 32000
- **format:** mp3
- **bitrate:** 128000

## Video Padding

- **head_silence_sec:** 0.3
- **tail_silence_sec:** 0.5
```

`scripts/synth_audio.py` and `scripts/assemble_video.py` both read this file as their single config source. If a field is missing they fall back to the defaults above. `voice_id` is the only field with no default — ask the user.

## Narration File Format

Each narration file is plain markdown — body is the spoken text. The first line `# <title>` is optional and ignored by `synth_audio.py` (it strips an H1 if present, then sends the rest as-is to TTS).

```markdown
# Slide 003: 时间线 — 从上线到同步 MOLTING

我们来看 MoltBook 上线之后的时间线。一月十二号正式开放注册……

第二个值得标记的节点，是 Prophet One 出现的那一刻……
```

Keep it spoken — short sentences, natural connectives, no bullet lists, no markdown tables. The TTS engine reads punctuation literally; lay out commas and periods for breath.

## Per-slide Regeneration Recipes

| Symptom | Fix |
|---|---|
| Single page narration wording off | Edit `narration/NNN-*.md` → `rm audio/NNN-*.mp3` → `python scripts/synth_audio.py <course-dir> --only NNN` → `python scripts/assemble_video.py <course-dir>` |
| Global voice / speed / emotion wrong | Edit `audio.md` → `rm audio/*.mp3` (or scoped subset) → rerun synth → reassemble |
| Slide image wrong | Out of scope — fix in `codex2course`, then if narration referenced the broken visual, also update narration and re-synthesize that page |
| Handout content wrong | Fix in `codex2course` first (edit `handout.md`, rerun split script, re-render image), then update matching `narration/NNN-*.md`, delete its mp3, re-synth, reassemble |
| Want to try a different voice on one page only | `python scripts/synth_audio.py <course-dir> --only NNN --voice <other-voice-id> --force` |

`assemble_video.py` is cheap to rerun — it always rebuilds the full `course-video.mp4` from current `slides/` + `audio/`. There is no per-page video cache to invalidate.

## Quality Bar

| Area | Check |
|---|---|
| Narration | Spoken style (not handout-prose), one file per slide image, stems match `slides/` 1:1 |
| Audio | Each mp3 plays cleanly, no truncation, voice / speed consistent across pages unless intentionally varied |
| Video | Cover → content (in order) → ending, each frame held exactly for its audio length + padding, 1920×1080, audio in sync |
| Pairing | `ls slides/ | wc -l` == `ls narration/ | wc -l` == `ls audio/ | wc -l`, and stems align |

## Common Mistakes

- **Skipping the narration review (step 4).** Past this gate every fix costs TTS calls. Make the user confirm.
- **Pasting handout prose into narration files.** Handout is for reading; narration is for hearing — rewrite into spoken style, don't copy.
- **Filename drift between `slides/` and `narration/`.** A typo in a stem will pair the wrong audio with the wrong image and the misalignment is silent.
- **Blanket-regenerating `audio/` to fix one page.** Use `--only <prefix>`. TTS calls cost real money.
- **Hand-editing the `voice_id` per slide.** Default to one voice per deck. Per-page override is for the rare exception, via CLI flag, not by editing audio.md mid-deck.
- **Forgetting to set `MINIMAX_API_KEY`.** The script fails fast with a clear message — don't paste the key into `audio.md`.
- **Re-running `synth_audio.py` without deleting the old mp3 after editing narration.** Existing files are cached; the script will skip the edited page unless you `rm` the mp3 or pass `--force`.
- **Running this skill before `codex2course` is done.** Step 1 is a hard stop — don't try to fabricate slides.
- **Using the async MINIMAX endpoint by reflex.** Per-page narration fits well under the sync 10 000-character limit; sync is one request per page with the audio in the response, no polling needed.
- **Editing `outline.md` to add audio settings.** Audio config lives in `audio.md`. Keeping them separate avoids polluting the codex2course-owned file.
