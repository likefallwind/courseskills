---
name: makecourse
description: Use when an agent (e.g. openclaw, hermes) is asked to produce a complete narrated course end-to-end from a topic or rough outline — handout + slide deck + lecture video. The agent drives the pipeline by shelling out to the `codex` CLI, which in turn invokes `ai-tutorials`, `codex2course`, and `pdf2video` in that order.
---

# Makecourse

## Overview

`makecourse` is an **orchestration skill for agents** (openclaw, hermes, or any agent that can run shell commands). It does not write course content itself. Instead it tells the agent how to chain three existing Codex skills via the `codex` CLI:

1. **`ai-tutorials`** → writes the lecture material (`introduction.md`, `syllabus.md`, `lesson{i}/{outline,handout,project}.md`).
2. **`codex2course`** → turns a per-lesson handout into a slide deck (`slide-units/`, `slides/*.png`, `<title>.pdf`).
3. **`pdf2video`** → turns the deck into a narrated mp4 (`narration/`, `audio/`, `<title>.mp4`).

The agent stays the orchestrator. Each stage runs in its own `codex exec` invocation so the heavy lifting (file I/O, image generation, TTS, ffmpeg) happens inside Codex with the right skill loaded.

**Core rule:** never reimplement the inner skills. Just call `codex exec` with a focused prompt and the stage's working directory, then verify the expected output files exist before moving on.

## When to Use

Use this skill when:
- A user (or upstream agent task) asks for a "complete course", "narrated lecture", "AI 课程视频", "讲义+课件+视频", or similar full-pipeline deliverable.
- You are an automation agent (openclaw, hermes, scheduled bot) that needs to produce courseware unattended.
- You already have a topic, rough outline, or a partially-built course directory and need to fill in the remaining stages.

Do **not** use this skill when:
- The user only wants one stage (just a handout, just slides, just a video). Call that single skill directly via `codex exec` instead.
- The user wants a live human-in-the-loop tutorial design session — the inner skills have hard stops for review (`ai-tutorials` Step 3/5, `codex2course` Step 4, `pdf2video` Step 4) that this orchestration must respect; running fully unattended will violate those stops unless the user has explicitly authorized auto-approval.
- The environment has no `codex` CLI on PATH or no API credentials configured.

## Pipeline Contract

```
┌─ Stage 1: ai-tutorials ─┐   ┌─ Stage 2: codex2course ─┐   ┌─ Stage 3: pdf2video ─┐
│ topic / outline         │ → │ lesson{i}/handout.md    │ → │ <course-title>.pdf   │ → <course-title>.mp4
│ → introduction.md       │   │ → outline.md            │   │ → narration/         │
│ → syllabus.md           │   │ → slide-units/          │   │ → audio/             │
│ → lesson{i}/handout.md  │   │ → slides/*.png          │   │ → <course-title>.mp4 │
│ → lesson{i}/project.md  │   │ → <course-title>.pdf    │   │                      │
└─────────────────────────┘   └─────────────────────────┘   └──────────────────────┘
```

The directory layouts of the three skills do not match perfectly: `ai-tutorials` organizes content by `lesson{i}/`, while `codex2course` and `pdf2video` operate on a single course directory with `outline.md` + `handout.md` at its root. The agent must reconcile this — see "Per-lesson loop" below.

## Required inputs

Gather from the calling context before running anything:

| Field | Required? | Notes |
|---|---|---|
| Course topic / title | yes | Free-form; `ai-tutorials` will turn it into `introduction.md` |
| Workspace directory | yes | All three stages run with this as cwd; create it empty if it doesn't exist |
| Per-lesson scope | yes | Either "all lessons in syllabus" or an explicit list like `lesson1,lesson3` |
| TTS provider | yes | `edge` (free, default) or `minimax` (paid). `pdf2video` will ask if not set |
| Voice id | recommended | Provider-specific. Skip → `pdf2video` will ask |
| Auto-approve human gates | optional | If true, the orchestrator bypasses inner-skill review stops. Default: false |

If any required field is missing, ask the user once before starting — do not start a stage with placeholder data, since the inner skills will then ask the user themselves and the orchestration will deadlock.

## Workflow

Each stage is independently invocable. Inspect the workspace and skip stages whose outputs already exist — the inner skills are themselves resumable, but skipping the outer call saves a `codex` round-trip.

### Stage 0 — Preflight

Before stage 1, verify:

- `command -v codex` succeeds. If not, abort with a message asking the user to install Codex CLI.
- `<workspace>` exists or can be created.
- For each inner skill referenced below, confirm the skill is installed (`ls ~/.agents/skills/<name>/SKILL.md` or `ls ~/.claude/skills/<name>/SKILL.md`). If missing, surface the gap to the user — do not try to run the pipeline anyway.

### Stage 1 — Generate handout via `ai-tutorials`

Invoke Codex with a prompt that names the skill explicitly so it loads:

```bash
codex exec \
  --cd "<workspace>" \
  --sandbox workspace-write \
  "Use the ai-tutorials skill to generate a complete course on the topic:
  '<COURSE_TOPIC>'.
  Target audience: <AUDIENCE>.
  Total lessons: <N>.
  Run all of Step 0 through Step 7 of the ai-tutorials workflow.
  When you reach a confirmation gate (knowledge points, syllabus), $GATE_INSTRUCTION.
  Stop after Step 7. Do not run Step 8 (cover images) — the orchestrator handles cover images downstream."
```

Where `$GATE_INSTRUCTION` is one of:

- Default (human in the loop): `"stop and print the artifact path so the orchestrator can relay it to the user for approval"`.
- Auto-approve mode: `"proceed automatically using your best judgment; do not pause for confirmation"`. Only set this when the calling user has explicitly authorized it.

**Verify** before continuing:

```bash
test -f "<workspace>/syllabus.md" \
  && ls "<workspace>"/lesson*/handout.md
```

If the syllabus or any expected `lesson{i}/handout.md` is missing, do **not** proceed — re-invoke stage 1 with `"continue from where you stopped per Step 0 detection"` instead.

### Stage 2 — Build slide deck per lesson via `codex2course`

`codex2course` operates on a single course directory containing `outline.md` and `handout.md` at its root. The `ai-tutorials` output uses `lesson{i}/handout.md` per lesson. Treat **each lesson as its own codex2course course**.

Per-lesson loop (run sequentially, not in parallel — image generation is heavy):

```bash
for LESSON in <selected lessons>; do
  LESSON_DIR="<workspace>/${LESSON}"

  codex exec \
    --cd "$LESSON_DIR" \
    --sandbox workspace-write \
    "Use the codex2course skill on this directory.
    The lesson handout already exists at handout.md and the lesson outline at outline.md.
    Treat the existing outline.md as the codex2course outline (extend it to include the
    three required sections: Course Info, Outline, Image Generation Settings — ask the
    user only for fields you cannot infer from ../introduction.md or ../studentprofile.md).
    Run from Step 5 (slide marker annotation) through Step 8 (PDF assembly).
    Use sequential sub-agent batching if there are more than 10 slides."

  # Verify
  test -d "$LESSON_DIR/slide-units" \
    && ls "$LESSON_DIR"/slides/000-cover.png "$LESSON_DIR"/slides/zzz-ending.png \
    && ls "$LESSON_DIR"/*.pdf
done
```

Notes:

- `codex2course` itself is resumable — if `slide-units/` exists it will skip earlier steps. The orchestrator does not need to track stage progress beyond "did the PDF land?".
- The `Course Info` block in `outline.md` should reuse `introduction.md` (instructor, institution, target audience). If those are absent, the inner skill will ask — relay the question to the user or fail hard in unattended mode.
- Do **not** run two `codex2course` invocations in parallel against different lessons unless you have confirmed the image-generation backend tolerates it. Default: serial.

### Stage 3 — Render narrated video per lesson via `pdf2video`

For every lesson directory that completed stage 2 successfully:

```bash
for LESSON in <selected lessons>; do
  LESSON_DIR="<workspace>/${LESSON}"

  codex exec \
    --cd "$LESSON_DIR" \
    --sandbox workspace-write \
    "Use the pdf2video skill on this directory.
    TTS provider: <edge|minimax>.
    Voice id: <voice_id>.
    Speed: <speed, default 1.0>.
    Run from Step 1 (sanity-check) through Step 8 (final review).
    When you reach the narration review gate (Step 4), $GATE_INSTRUCTION."

  # Verify
  ls "$LESSON_DIR"/*.mp4
done
```

The mp4 filename comes from the lesson's `outline.md` H1 (same rule as `codex2course`). If the H1 was extended to a course title rather than the lesson title, the filenames will reflect that — adjust upstream if you need lesson-titled outputs.

### Stage 4 — Aggregate

After all lessons complete:

- Collect every `<workspace>/lesson*/*.mp4` and every `<workspace>/lesson*/*.pdf`.
- Print a manifest to the calling user (or upstream agent) listing:
  - Course root directory
  - Per-lesson PDF and MP4 paths
  - Total lessons completed vs requested
  - Any lessons that failed and at which stage
- If any lesson failed, surface that explicitly. Do not silently skip.

## Codex invocation reference

| Flag | Why this orchestrator uses it |
|---|---|
| `codex exec` | Non-interactive subcommand. Always use `exec`, never the interactive top-level form, when called from another agent. |
| `--cd <dir>` | Sets the working directory the inner skills will see. All three skills key off cwd to find / write artifacts. |
| `--sandbox workspace-write` | Inner skills need to create files (`syllabus.md`, `slides/`, `audio/`, mp4). `read-only` will break stage 1 immediately. Use `danger-full-access` only if a stage needs to install ffmpeg or `edge-tts` and the calling user has authorized it. |
| `-m <model>` | Optional. The default model is fine for handout writing; consider a smaller model for cheap stages and a larger one for image-prompt synthesis. Leave unset unless cost is a constraint. |
| `--add-dir <other>` | Use when the inner stage needs to read a sibling directory (e.g., a shared `studentprofile.md` outside the workspace). Otherwise omit. |
| `-c <key=value>` | Avoid in the orchestrator unless tuning is necessary. Profile drift between stages causes hard-to-debug failures. |

Pass the prompt as a single argument string (not stdin) so quoting and newlines are explicit. For long prompts, store them in a file and pipe via stdin: `codex exec --cd "$LESSON_DIR" - < prompt.txt`.

## Quick reference

| You want to… | Run |
|---|---|
| Fresh course from a topic | Stage 0 → 1 → 2 (loop) → 3 (loop) → 4 |
| Resume after handout but before slides | Stage 0 → skip 1 (verify outputs) → 2 (loop) → 3 (loop) → 4 |
| Re-render only lesson 3's video | Stage 0 → skip 1 & 2 → run stage 3 with `<selected lessons>=lesson3` only |
| Replace the voice across all lessons | Inside each `lesson{i}/`: edit `audio.md`, delete `audio/*.mp3`, rerun stage 3 with the same loop |
| Add a new lesson to an existing course | Stage 1 in continue mode (let `ai-tutorials` Step 0 detect existing state), then stages 2+3 scoped to the new lesson only |

## Common Mistakes

- **Reimplementing inner skills.** If you find yourself writing a slide marker or invoking an image-gen API from the orchestrator, stop. Call `codex exec` and let `codex2course` do it.
- **Running stages in parallel by lesson.** Image generation and TTS are rate-limited and resource-heavy. Serial is the default; parallelize only with explicit user authorization.
- **Skipping the post-stage file checks.** `codex exec` returning success ≠ the artifacts exist. Always `ls` / `test -f` for the expected outputs before advancing.
- **Auto-approving the inner skills' human gates silently.** `ai-tutorials` Step 3/5, `codex2course` Step 4, and `pdf2video` Step 4 exist for a reason (cheapest revision points). Bypass them only when the calling user has explicitly authorized unattended mode, and tell the user what was bypassed.
- **Mixing `--cd` with relative paths in the prompt.** The prompt should reference paths relative to the cwd you set with `--cd`, not absolute paths from the orchestrator. Otherwise the inner skill writes to the wrong place.
- **Forgetting `--sandbox workspace-write`.** Default sandbox is read-only in some Codex configs; the inner skills will appear to "succeed" while writing nothing.
- **Treating `ai-tutorials` output as a single course directory.** It is per-lesson. Stages 2 and 3 must loop over `lesson{i}/`, not run once at the workspace root.
- **Calling stage 3 before stage 2 finished.** `pdf2video` step 1 will hard-stop because `slides/` doesn't have `000-cover.png` and `zzz-ending.png` yet. Always verify the PDF exists before invoking stage 3.
- **Not surfacing partial failures.** If lesson 4 fails at stage 2, the agent must report it. Don't silently skip and produce a "course complete" summary that's missing a lesson.
- **Using interactive `codex` from inside another agent.** Always `codex exec`. The interactive form will hang waiting for a TTY.
- **Burying the inner skill name.** Each prompt must literally say "Use the ai-tutorials skill" / "Use the codex2course skill" / "Use the pdf2video skill" so Codex loads the right one. Do not paraphrase.
