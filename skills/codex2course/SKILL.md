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

1. **Confirm input state.** Accept a course topic, rough outline, existing handout, or a request to design the outline.
2. **Generate or refine the outline.** Organize concepts by dependency, teaching rhythm, and difficulty. Ask for confirmation before writing full content unless the user asked for a full draft in one pass.
3. **Write the handout.** Produce knowledge-point explanations that are detailed enough for learning but not a word-for-word script. Prioritize logic, terminology, examples, and order.
4. **Pause for human revision.** Encourage edits to content logic, terminology, emphasis, and teaching sequence. Do not freeze slide units before this review unless explicitly asked.
5. **Slice into slide units.** Each slide unit maps to exactly one page image and includes title, teaching goal, key message, on-slide text, visual direction, and avoid list.
6. **Generate slide images.** Use `imagegen` with one prompt per slide unit. Let Image Gen handle composition, visual metaphor, information layout, and polish.
7. **Inspect and iterate.** Check legibility, factual accuracy, text fidelity, style consistency, and whether the slide teaches the intended point. For local fixes, revise only that slide unit and regenerate that page.
8. **Assemble PDF.** Combine final slide images in order into a PDF. Preserve source slide units so any page can be regenerated later.

## Output Structure

Prefer this structure unless the user provides another destination:

```text
course/
├── outline.md
├── handout.md
├── slide-units.md
├── slides/
│   ├── 001-title.png
│   ├── 002-topic.png
│   └── ...
└── course-deck.pdf
```

## Slide Unit Template

```markdown
## Slide 003: Short Title
- Teaching goal: What the learner should understand after this page
- Key message: One sentence the slide must communicate
- On-slide text: Exact text to render, kept short
- Visual direction: Scene, metaphor, chart, UI mockup, or educational diagram
- Style constraints: Palette, layout rhythm, typography direction, consistency notes
- Avoid: Crowded text, extra slogans, unsupported claims, watermarks
```

## Imagegen Prompt Pattern

For each slide unit, call `imagegen` using a structured prompt:

```text
Use case: scientific-educational
Asset type: image-based course slide page for PDF deck
Primary request: Create one polished course slide image from this slide unit.
Subject: <slide key message>
Text (verbatim): "<short exact on-slide text>"
Visual direction: <scene/metaphor/diagram/layout>
Composition/framing: 16:9 slide, strong hierarchy, readable from presentation distance
Style/medium: modern educational slide, clean bitmap design, consistent with prior slides
Constraints: accurate concepts, no watermark, no extra text, no fake UI unless requested
Avoid: dense paragraphs, tiny labels, decorative clutter
```

## Quality Bar

| Area | Check |
|---|---|
| Handout | Correct terms, coherent order, teachable examples, no unsupported claims |
| Slide units | One teaching goal per page, short text, visual direction is specific |
| Image pages | Text is readable, layout is not crowded, visual metaphor matches content |
| PDF | Pages are ordered, consistent aspect ratio, no missing or stale regenerated pages |

## Common Mistakes

- **Generating `.pptx` by habit.** This workflow produces image pages plus PDF unless the user explicitly asks for editable `.pptx`.
- **Skipping the handout review.** Slide units should reflect the reviewed teaching logic.
- **Making slide units too text-heavy.** Put explanation in `handout.md`; keep page text compact.
- **Using placeholders instead of Image Gen.** If the deliverable needs a slide page image, use `imagegen`.
- **Regenerating the whole deck for one bad page.** Edit the specific slide unit and regenerate only that page.
