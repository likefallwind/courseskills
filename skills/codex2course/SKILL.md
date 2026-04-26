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

1. **Identify entry point and confirm input state.** Accept a course topic, rough outline, existing handout, finalized slide units, or a generated deck that needs targeted regeneration.
2. **Generate or refine the outline.** Organize concepts by dependency, teaching rhythm, and difficulty. Append a final `## Image Generation Settings` section to `outline.md` (course brief, resolution, shared style line — see the Imagegen Call Pattern section). Ask for confirmation before writing full content unless the user asked for a full draft in one pass.
3. **Write the handout.** Produce knowledge-point explanations that are detailed enough for learning but not a word-for-word script. Prioritize logic, terminology, examples, and order.
4. **STOP for human revision.** Output the handout and explicitly ask the user to review and approve it. Do not proceed to slide units until the user confirms. Encourage edits to content logic, terminology, emphasis, and teaching sequence.
5. **Annotate handout with slide markers, then materialize slide units.** Insert `<!-- slide: 标题 -->` markers at the points in `handout.md` where each slide should begin (see Slide Marker Convention below). This is the key human decision in this stage — present the resulting slide list to the user for review before moving on. Then run `python scripts/split_handout.py course/handout.md` to mechanically materialize `course/slide-units/NNN-slug.md`. The script is the single way to produce slide-units; never hand-author or hand-edit those files. If `handout.md` is later edited, rerun the script to refresh `slide-units/` before regenerating any image.
6. **Generate slide images.** For each file in `slide-units/`, call `imagegen` with the course-level prefix from `outline.md`'s `## Image Generation Settings` section followed by the slide-unit file's content. Reuse the prefix verbatim across every slide — do not re-derive it per call.
7. **Batch review, then targeted regeneration.** After all slides are generated, present the deck to the user for review in one pass. The user identifies which specific slides need changes and provides per-slide revision feedback. Regenerate only those slides, one at a time, by re-running `imagegen` with the same prefix + slide-unit content plus the user's revision note appended. Overwrite the same `slides/` filename so PDF assembly picks up the latest version. Never regenerate a slide without an explicit per-slide instruction from the user. If the user's feedback is actually about content (not visuals), edit `handout.md` and rerun the split script first.
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
├── outline.md          # ends with a ## Image Generation Settings section
├── handout.md          # source of truth, contains <!-- slide: ... --> markers
├── slide-units/        # DERIVED from handout.md by scripts/split_handout.py — never hand-edit
│   ├── 001-title.md
│   ├── 002-topic.md
│   └── ...
├── slides/             # filenames mirror slide-units/ 1:1
│   ├── 001-title.png
│   ├── 002-topic.png
│   └── ...
└── course-deck.pdf
```

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

1. **Course-level prefix** — pulled verbatim from `outline.md`'s `## Image Generation Settings` section. Generated once at outline time (step 2) and reused for every slide. Contains:
   - A one-paragraph course brief (what this course is, who it's for, the teaching goal)
   - Resolution — ask the user; if `outline.md` already specifies one, use that; default to 16:9, e.g. 1920×1080
   - One shared style line, e.g. `modern educational slide, soft pastel palette, clean sans-serif, generous whitespace`
   - Output language (matches the handout)

2. **Slide content** — the contents of the slide-unit file (title + raw handout content), used verbatim.

Do not re-derive the prefix per slide. Do not over-structure the prompt — `gpt-image-2` handles composition, layout, and visual metaphor on its own.

When regenerating a single slide in step 7, append the user's per-slide revision note after the slide content. Keep the prefix unchanged.

Example `## Image Generation Settings` block in `outline.md`:

```markdown
## Image Generation Settings

**Course brief:** A one-day workshop on prompt engineering for working software engineers, focused on practical patterns rather than theory. Learners walk away with a small toolkit they can apply the next day.

**Resolution:** 1920×1080 (16:9)

**Style:** modern educational slide, soft pastel palette, clean sans-serif, generous whitespace

**Language:** Chinese
```

## Quality Bar

| Area | Check |
|---|---|
| Handout | Correct terms, coherent order, teachable examples, no unsupported claims |
| Slide units | One file per slide, filename mirrors `slides/` 1:1, body is verbatim handout content |
| Image pages | Text is readable, layout is not crowded, visual metaphor matches content |
| PDF | Pages are ordered, consistent aspect ratio, no missing or stale regenerated pages |

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
