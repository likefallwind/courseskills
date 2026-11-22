# Repository Guidelines

## Project Structure & Module Organization

This repository packages course-creation workflows as Codex, Claude Code, and standalone skills. The shared implementation lives in `skills/`, with one directory per skill:

- `skills/*/SKILL.md` contains the user-facing workflow instructions.
- `skills/*/scripts/` contains Python helpers used by those workflows.
- `skills/ai-tutorials/examples/` stores sample course-planning documents.
- `docs/` contains installation and usage notes.
- `.codex-plugin/`, `.claude-plugin/`, and `.agents/plugins/` contain plugin and marketplace manifests.

Keep new skill assets close to the skill that owns them. Avoid committing generated course outputs, videos, audio, or `__pycache__/` files.

## Build, Test, and Development Commands

There is no compiled build step and `package.json` currently defines metadata only. Useful local checks are direct script runs:

```bash
python skills/codex2course/scripts/split_handout.py course/handout.md
python skills/codex2course/scripts/images2pdf.py course/slides course/course-deck.pdf
python skills/api2course/scripts/generate_openai_image.py --prompt-file course/prompt.txt --out course/slides/001.png
python skills/pdf2video/scripts/synth_audio.py course/
python skills/pdf2video/scripts/assemble_video.py course/
python skills/movecourse/scripts/movecourse.py --course ai-enlightenment --source course/ --dry-run
```

Use `--dry-run` when validating publishing or copy behavior.

## Coding Style & Naming Conventions

Write Markdown in concise, task-oriented language. Skill directories use kebab-case names such as `codex2course` or `ai-tutorials`; keep script names snake_case, for example `split_handout.py`. Python scripts should be compatible with Python 3, prefer standard-library APIs unless a dependency is already documented, and use clear CLI arguments for paths and provider settings.

## Testing Guidelines

No automated test suite is currently configured. For script changes, test with a small fixture course directory and verify `movecourse` updates `course-assets.local.yaml` by default; only `--publish-static` should copy mp4 files into `static/course-assets` for local preview. For generated course packages, verify the documented layout: `outline.md`, `handout.md`, `slide-units/`, `slides/`, `course-deck.pdf`, `narration/`, `audio/`, and `course-video.mp4`. For manifest or install-documentation changes, validate paths against `README.md` and `docs/codex-install.md`.

## Commit & Pull Request Guidelines

Recent commits use short, imperative summaries, for example `Add Codex install guide` and `Document Codex marketplace install path`. Follow that style and keep each commit focused.

Pull requests should include a brief description, affected skills or manifests, manual validation performed, and any required environment variables such as `OPENAI_API_KEY` or `MINIMAX_API_KEY`. Include screenshots or sample output only when changing generated visual or video workflows.

## Security & Configuration Tips

Do not commit API keys, generated media, or local machine paths except when a documented workflow requires a fixed path. Keep provider-specific credentials in environment variables.
