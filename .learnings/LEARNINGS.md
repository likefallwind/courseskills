## [LRN-20260511-001] correction

**Logged**: 2026-05-11T15:23:05+08:00
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
Codex2Course `.gitignore` guidance must ignore only generated intermediates, not pre-existing target repository content.

### Details
When a skill generates files inside another repository, ignore rules must be based on ownership and generation inventory, not filenames alone. Paths that existed before the run, or are already tracked by Git, must remain visible unless the user explicitly confirms they are Codex2Course-owned intermediates.

### Suggested Action
For future generated-artifact ignore guidance, require a preflight check of target paths and add only exact ignore rules for files or directories created by the current workflow.

### Metadata
- Source: user_feedback
- Related Files: skills/codex2course/SKILL.md
- Tags: gitignore, generated-artifacts, repository-hygiene

---
