---
name: codex2course
description: Use when generating course handouts, lecture notes, slide-unit plans, image-based PPT pages, or PDF course decks from a course topic or outline, especially when slide visuals should be produced with Image Gen rather than .pptx shapes.
---

# Codex2Course

## Overview

Create a course package from a topic or outline: detailed teaching handouts first, then slide units, then one generated image per slide, then a PDF assembled from those images. The core rule is that slides are image pages, not `.pptx` files.

**REQUIRED SUB-SKILL:** Use `imagegen` for every generated slide page, cover image, visual metaphor, diagram-like bitmap, or style variant.

## When to Use

Use this skill for:
- Course handouts, lecture notes, tutorials, workshops, training materials
- Turning an outline into teachable content and visual slide pages
- Producing "PPT" as page images combined into a PDF
- Regenerating individual unsatisfactory pages from revised slide units

Do not use this skill when the user specifically needs editable `.pptx`; use `pptx` instead.

## Workflow

Each stage below is independently invocable. Inspect what artifacts already exist (`outline.md`, `handout.md`, `slide-units/`, `slides/`) and start at the next missing stage — do not redo work the user already approved.

All output (handout text, on-slide text, image text) must match the language of the user's input.

1. **Identify entry point and confirm input state.** Accept a course topic, rough outline, existing handout, finalized slide units, or a generated deck that needs targeted regeneration. If you will need to write or extend `outline.md`, also gather any missing metadata up front: instructor, institution, target audience, course goal, art style preference (ask the user for whatever is missing).
2. **Generate or refine the outline.** Use the structured template in the Outline Template section below — three required sections: `## Course Info` (cover-slide source), `## Outline` (drives handout writing), `## Image Generation Settings` (imagegen prefix source). Organize the outline body by dependency, teaching rhythm, and difficulty. Ask for confirmation before writing full content unless the user asked for a full draft in one pass.
3. **Write the handout.** Produce knowledge-point explanations that are detailed enough for learning but not a word-for-word script. Prioritize logic, terminology, examples, and order.
4. **STOP for human revision.** Output the handout and explicitly ask the user to review and approve it. Do not proceed to slide units until the user confirms. Encourage edits to content logic, terminology, emphasis, and teaching sequence.
5. **Annotate handout with slide markers, then materialize slide units.** Insert `<!-- slide: 标题 -->` markers at the points in `handout.md` where each slide should begin (see Slide Marker Convention below). This is the key human decision in this stage — present the resulting slide list to the user for review before moving on. Then run `python scripts/split_handout.py course/handout.md` to mechanically materialize `course/slide-units/NNN-slug.md`. The script is the single way to produce slide-units; never hand-author or hand-edit those files. If `handout.md` is later edited, rerun the script to refresh `slide-units/` before regenerating any image.
6. **Generate slide images.** Reuse the course-level prefix from `outline.md`'s `## Image Generation Settings` verbatim for every imagegen call. Generate three groups in this order:
   - **Cover** → `slides/000-cover.png`. Content payload built from `## Course Info` (course title from `outline.md`'s H1, instructor, institution, target audience as a tone cue), with an explicit instruction that this is the deck's cover.
   - **Content** → `slides/NNN-slug.png`, mirroring `slide-units/` filenames 1:1. For each slide-unit file, payload is the file's verbatim content.
   - **Ending** → `slides/zzz-ending.png`. Short closing slide (e.g., "谢谢 / Q&A" in the course language). Custom ending text can be added by the user in `## Image Generation Settings`.
7. **Batch review, then targeted regeneration.** After all slides (cover + content + ending) are generated, present the deck to the user for review in one pass. The user identifies which specific slides need changes and provides per-slide revision feedback. Regenerate only those slides, one at a time, by re-running `imagegen` with the same prefix + payload plus the user's revision note appended. Overwrite the same `slides/` filename so PDF assembly picks up the latest version. Never regenerate a slide without an explicit per-slide instruction from the user. If the user's feedback is actually about content (not visuals) for a content slide, edit `handout.md` and rerun the split script first; for cover/ending content fixes, edit `outline.md`.
8. **Assemble PDF.** Use Pillow to combine slide images in filename order:

   ```python
   from PIL import Image
   from pathlib import Path
   paths = sorted(Path("course/slides").glob("*.png"))
   imgs = [Image.open(p).convert("RGB") for p in paths]
   imgs[0].save("course/course-deck.pdf", save_all=True, append_images=imgs[1:])
   ```

## Output Structure

Prefer this structure unless the user provides another destination:

```text
course/
├── outline.md          # 3 sections: Course Info, Outline, Image Generation Settings
├── handout.md          # source of truth, contains <!-- slide: ... --> markers
├── slide-units/        # DERIVED from handout.md by scripts/split_handout.py — never hand-edit
│   ├── 001-title.md
│   ├── 002-topic.md
│   └── ...
├── slides/             # cover + content (mirrors slide-units/ 1:1) + ending
│   ├── 000-cover.png
│   ├── 001-title.png
│   ├── 002-topic.png
│   ├── ...
│   └── zzz-ending.png
└── course-deck.pdf
```

## Outline Template

`outline.md` has three required sections. Section names matter — downstream steps and the imagegen call all reference them by exact heading.

```markdown
# 课程标题: <Course Title>

## Course Info

- **Instructor:** <name>
- **Institution:** <institution / 单位>
- **Target audience:** <e.g., 工作 1-3 年的后端工程师，没有 LLM 使用经验>
- **Course goal:** <one line: what learners walk away with>
- **Duration:** <e.g., 一天 / 6 hours>

## Outline

1. Module 1: ...
   - Topic 1.1
   - Topic 1.2
2. Module 2: ...

## Image Generation Settings

- **Course brief:** <one-paragraph summary used as imagegen prefix; can be derived from Course Info + Course goal>
- **Art style:** <one shared style line, e.g., modern educational slide, soft pastel palette, clean sans-serif, generous whitespace>
- **Resolution:** <e.g., 1920×1080 (16:9)>
- **Language:** <e.g., Chinese>
- **Ending text (optional):** <override the default "谢谢 / Q&A" closing>
```

If any field in `Course Info` or `Image Generation Settings` is missing in step 1's input, ask the user before drafting the outline. Do not invent an instructor, institution, or audience.

## Slide Marker Convention

`handout.md` is the single source of truth. It is organized for teaching/reading — heading hierarchy follows pedagogical logic, not slide structure. Slide boundaries are an orthogonal annotation layer added in step 5 using HTML comments (invisible in rendered markdown):

```markdown
<!-- slide: 什么是 prompt engineering -->

它是一种通过设计输入来引导模型行为的实践……

## 三个核心原则

<!-- slide: 原则一：明确意图 -->

模型不会读心。明确意图意味着……
```

Rules:

- Every `<!-- slide: 标题 -->` marker opens a new slide. Slide content is everything from that marker up to the next marker (or end of file).
- Slide numbering is implicit (sequential by appearance order). Reordering slides means moving markers, not renumbering.
- The title in the marker becomes the slide filename suffix (slugified) and the slide-unit file's H1 heading.
- A heading like `## 三个核心原则` between markers belongs to whichever slide's range it falls into — handout structure and slide structure are decoupled.

## Slide Unit File Format (derived)

`scripts/split_handout.py` mechanically generates `slide-units/NNN-slug.md` from `handout.md`. Each file looks like:

```markdown
# Slide 003: Short Title

<verbatim handout content between this slide's marker and the next>
```

These files are **derived artifacts** — never hand-author or hand-edit them. To change slide content or boundaries, edit `handout.md` and rerun the script.

Run the script:

```bash
python scripts/split_handout.py course/handout.md
# defaults --out to course/slide-units
```

It clears stale `NNN-*.md` files in the output directory and rewrites all slides, so removing a marker correctly removes its slide.

## Imagegen Call Pattern

Each `imagegen` call has two parts in this order:

1. **Course-level prefix** — pulled verbatim from `outline.md`'s `## Image Generation Settings` (course brief, art style, resolution, language). Reused unchanged across every slide (cover, content, ending). Do not re-derive per call.
2. **Per-slide payload** — depends on slide kind:

| Slide kind | Payload source |
|---|---|
| Cover (`000-cover.png`) | An explicit cover-instruction line + the H1 course title + `## Course Info` fields (instructor, institution, target audience as tone cue) |
| Content (`NNN-slug.png`) | The slide-unit file's verbatim contents |
| Ending (`zzz-ending.png`) | An explicit ending-instruction line + the optional ending text from `## Image Generation Settings`, defaulting to "谢谢 / Q&A" in the course language |

Do not over-structure the prompt — `gpt-image-2` handles composition, layout, and visual metaphor on its own. When regenerating a single slide in step 7, append the user's per-slide revision note after the payload. Keep the prefix unchanged.

## Quality Bar

| Area | Check |
|---|---|
| Handout | Correct terms, coherent order, teachable examples, no unsupported claims |
| Slide units | One file per slide, filename mirrors `slides/` 1:1, body is verbatim handout content |
| Image pages | Text is readable, layout is not crowded, visual metaphor matches content |
| Cover/Ending | Cover shows title + instructor + institution clearly; ending is simple and uncluttered; both share style with content slides |
| PDF | Cover first, ending last, content in order, consistent aspect ratio, no missing or stale regenerated pages |

## Common Mistakes

- **Generating `.pptx` by habit.** This workflow produces image pages plus PDF unless the user explicitly asks for editable `.pptx`.
- **Skipping the handout review.** Slide units should reflect the reviewed teaching logic. Step 4 is a hard stop.
- **Drifting from the confirmed outline** when writing the handout or slicing slide units.
- **Over-structuring the imagegen prompt.** Passing only the course-level prefix + the verbatim slide-unit content beats elaborate prompt scaffolds.
- **Re-deriving the course brief per slide.** Generate it once in step 2, store it in `outline.md`'s `## Image Generation Settings`, reuse verbatim.
- **Hand-editing files in `slide-units/`.** Those are derived from `handout.md` — edit handout and rerun `scripts/split_handout.py` instead. Hand-edits get wiped on the next run.
- **Forgetting to rerun the split script after editing `handout.md`.** Stale `slide-units/` will produce slides that no longer match the source.
- **Using placeholders instead of imagegen.** If the deliverable needs a slide page image, use `imagegen`.
- **Regenerating slides without explicit per-slide feedback** from the user, or regenerating the whole deck when only a few pages need fixes.
- **Restarting the workflow from step 1** when a reviewed handout or slide-unit file already exists. Pick up at the next missing stage.
- **Inventing instructor/institution/audience** when `outline.md` doesn't specify them. Ask the user.
- **Skipping cover or ending slides.** Every deck has both, named `000-cover.png` and `zzz-ending.png` so PDF assembly orders them by alphabetical glob.
