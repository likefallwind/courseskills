#!/usr/bin/env python3
"""Prepare an existing course repository for aistudy101 website sync."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


DEFAULT_WEBSITE_ROOT = Path("/home/likefallwind/code/aistudy101-website")
DEFAULT_VIDEO_GLOBS = ["lesson*/deck/*.mp4", "lesson*/video/*.mp4", "lesson*/*.mp4"]
STAGE_BY_PATH = {
    "stage1": "小学",
    "stage2": "初中",
    "stage3": "高中",
    "college": "大学",
}
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class CoursePlan:
    source_root: Path
    website_root: Path
    course_id: str
    title: str
    repo_url: str
    branch: str
    fallback: dict[str, Any]
    video_globs: list[str]
    write_course_yaml: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wire an existing course repository into the aistudy101 website."
    )
    parser.add_argument("--source", default=".", help="Course repository root; default: cwd")
    parser.add_argument("--website-root", default=str(DEFAULT_WEBSITE_ROOT))
    parser.add_argument("--course-id", help="Website course id, e.g. ai-concept")
    parser.add_argument("--repo-url", help="Public repository URL; inferred from git origin")
    parser.add_argument("--branch", help="Source branch; inferred from git")
    parser.add_argument("--title", help="Course title; inferred from course files")
    parser.add_argument("--stage", help="Course stage, e.g. 小学 / 初中 / 高中")
    parser.add_argument("--education-phase", default="基础教育")
    parser.add_argument("--track", default="AI 通识")
    parser.add_argument("--status", default="待审核")
    parser.add_argument("--version", default="0.1")
    parser.add_argument("--hours", type=float, help="Course hours / lesson count")
    parser.add_argument(
        "--theme-line",
        action="append",
        dest="theme_lines",
        help="Theme line. Can be passed multiple times.",
    )
    parser.add_argument(
        "--video-glob",
        action="append",
        dest="video_globs",
        help="Local video glob relative to course root. Can be passed multiple times.",
    )
    parser.add_argument(
        "--write-course-yaml",
        action="store_true",
        help="Create course.yaml in the course repo when missing.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes only")
    return parser.parse_args()


def run_git(source_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=source_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return None
    return result.stdout.strip()


def normalize_repo_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    scp = re.fullmatch(r"git@(gitee\.com|github\.com):(.+?)(?:\.git)?", url)
    if scp:
        return f"https://{scp.group(1)}/{scp.group(2)}"
    https = re.fullmatch(r"(https?://.+?)(?:\.git)?/?", url)
    if https:
        return https.group(1)
    return url.removesuffix(".git")


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def first_heading(path: Path) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = re.match(r"^\s*#\s+(.+?)\s*$", line)
        if match:
            return strip_course_prefix(match.group(1))
    return None


def strip_course_prefix(title: str) -> str:
    title = re.sub(r"^课程介绍[:：]\s*", "", title.strip())
    return re.sub(r"[*_`]+", "", title).strip()


def infer_title(source_root: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    course_yaml = read_yaml(source_root / "course.yaml")
    if course_yaml.get("title"):
        return str(course_yaml["title"])
    for name in ("README.md", "introduction.md", "syllabus.md"):
        title = first_heading(source_root / name)
        if title:
            return title
    return source_root.name


def infer_course_id(source_root: Path, explicit: str | None) -> str:
    if explicit:
        course_id = explicit
    else:
        course_yaml = read_yaml(source_root / "course.yaml")
        if course_yaml.get("id"):
            course_id = str(course_yaml["id"])
        else:
            name = source_root.name.lower()
            course_id = re.sub(r"^\d+[-_]", "", name)
            course_id = re.sub(r"[^a-z0-9._-]+", "-", course_id).strip("-")
    if not course_id or not SAFE_ID_RE.fullmatch(course_id):
        raise ValueError("Unable to infer a safe course id; pass --course-id")
    return course_id


def infer_stage(source_root: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    for part in reversed(source_root.parts):
        if part in STAGE_BY_PATH:
            return STAGE_BY_PATH[part]
    text = joined_summary_text(source_root)
    if re.search(r"小学|6-10|6\s*-\s*10", text):
        return "小学"
    if re.search(r"初中|12-15|12\s*-\s*15", text):
        return "初中"
    if "高中" in text:
        return "高中"
    return "待确认"


def joined_summary_text(source_root: Path) -> str:
    chunks: list[str] = []
    for name in ("README.md", "introduction.md", "syllabus.md"):
        path = source_root / name
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8", errors="ignore")[:5000])
    return "\n".join(chunks)


def infer_hours(source_root: Path, explicit: float | None) -> int | float:
    if explicit is not None:
        return int(explicit) if explicit.is_integer() else explicit
    text = joined_summary_text(source_root)
    match = re.search(r"总课时[^0-9一二三四五六七八九十]*(\d+)\s*节", text)
    if match:
        return int(match.group(1))
    lessons = lesson_dirs(source_root)
    return len(lessons) if lessons else 1


def infer_theme_lines(source_root: Path, title: str, explicit: list[str] | None) -> list[str]:
    if explicit:
        return explicit
    text = title + "\n" + joined_summary_text(source_root)
    themes = ["AI 素养"]
    if re.search(r"机器学习|模型|过拟合|分类|回归", text):
        themes.append("机器学习")
    if re.search(r"Python|编程|代码", title, flags=re.IGNORECASE):
        themes.append("编程与工程")
    return themes


def infer_goals(source_root: Path, title: str) -> list[str]:
    bullets = bullets_after_keywords(joined_summary_text(source_root), ["学习目标", "课程目标"])
    if bullets:
        return bullets[:5]
    return [f"掌握 {title} 的核心概念与实践方法"]


def infer_outputs(source_root: Path, title: str) -> list[str]:
    text = joined_summary_text(source_root)
    outputs: list[str] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 3 or _is_table_separator(cells):
            continue
        project = strip_markdown(cells[-1])
        if project and project not in {"项目", "项目任务"}:
            outputs.append(f"完成项目：{project}")
    return dedupe(outputs)[:5] or [f"完成 {title} 的课程项目"]


def bullets_after_keywords(text: str, keywords: list[str]) -> list[str]:
    results: list[str] = []
    collecting = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and any(keyword in stripped for keyword in keywords):
            collecting = True
            continue
        if collecting and stripped.startswith("#") and results:
            break
        if collecting and stripped.startswith("- "):
            results.append(strip_markdown(stripped[2:]))
    return dedupe(results)


def strip_markdown(text: str) -> str:
    return re.sub(r"[*_`]+", "", text).strip()


def _is_table_separator(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-+:?", cell) is not None for cell in cells)


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def lesson_dirs(source_root: Path) -> list[Path]:
    dirs = [
        path
        for path in source_root.iterdir()
        if path.is_dir() and re.fullmatch(r"lesson0*\d+", path.name, flags=re.IGNORECASE)
    ]
    return sorted(dirs, key=lambda path: int(re.search(r"\d+", path.name).group(0)))


def existing_course_entry(sources: list[dict[str, Any]], course_id: str) -> dict[str, Any] | None:
    for source in sources:
        if str(source.get("id")) == course_id:
            return source
    return None


def build_plan(args: argparse.Namespace) -> CoursePlan:
    source_root = Path(args.source).expanduser().resolve()
    website_root = Path(args.website_root).expanduser().resolve()
    if not source_root.is_dir():
        raise NotADirectoryError(f"Course source does not exist: {source_root}")
    if not website_root.is_dir():
        raise NotADirectoryError(f"Website root does not exist: {website_root}")
    if not lesson_dirs(source_root):
        raise ValueError(f"No lessonN directories found under {source_root}")

    title = infer_title(source_root, args.title)
    course_id = infer_course_id(source_root, args.course_id)
    repo_url = normalize_repo_url(args.repo_url or run_git(source_root, "remote", "get-url", "origin"))
    if not repo_url:
        raise ValueError("Unable to infer repo URL; pass --repo-url")
    branch = args.branch or run_git(source_root, "branch", "--show-current") or "master"
    hours = infer_hours(source_root, args.hours)
    fallback = {
        "title": title,
        "stage": infer_stage(source_root, args.stage),
        "education_phase": args.education_phase,
        "track": args.track,
        "status": args.status,
        "version": str(args.version),
        "hours": hours,
        "theme_lines": infer_theme_lines(source_root, title, args.theme_lines),
    }
    return CoursePlan(
        source_root=source_root,
        website_root=website_root,
        course_id=course_id,
        title=title,
        repo_url=repo_url,
        branch=branch,
        fallback=fallback,
        video_globs=args.video_globs or DEFAULT_VIDEO_GLOBS,
        write_course_yaml=args.write_course_yaml,
    )


def planned_source_entry(plan: CoursePlan) -> dict[str, Any]:
    return {
        "id": plan.course_id,
        "type": "gitee",
        "repo": plan.repo_url,
        "branch": plan.branch,
        "fallback": plan.fallback,
    }


def planned_course_yaml(plan: CoursePlan) -> dict[str, Any]:
    fallback = plan.fallback
    return {
        "id": plan.course_id,
        "title": plan.title,
        "stage": fallback["stage"],
        "education_phase": fallback["education_phase"],
        "track": fallback["track"],
        "status": fallback["status"],
        "version": fallback["version"],
        "hours": fallback["hours"],
        "target_learners": [fallback["stage"]],
        "prerequisites": {
            "coding": "按课程说明准备",
            "math": "按对应学段要求准备",
            "ai": "按课程说明准备",
        },
        "goals": infer_goals(plan.source_root, plan.title),
        "outputs": infer_outputs(plan.source_root, plan.title),
        "links": {"repo": plan.repo_url, "website": f"/courses/{plan.course_id}"},
        "review": {
            "pedagogy": "pending",
            "technical": "pending",
            "ethics": "pending",
            "runnable": "pending",
            "piloted": False,
        },
        "maintainers": ["AI Study 101"],
        "contributors": [],
        "license": {"content": "CC BY-SA 4.0", "code": "MIT"},
        "theme_lines": fallback["theme_lines"],
    }


def apply_plan(plan: CoursePlan, dry_run: bool) -> None:
    sources_path = plan.website_root / "course-sources.yaml"
    local_assets_path = plan.website_root / "course-assets.local.yaml"
    course_yaml_path = plan.source_root / "course.yaml"

    sources_data = read_yaml(sources_path) or {"sources": []}
    sources = list(sources_data.get("sources") or [])
    source_entry = planned_source_entry(plan)
    existing = existing_course_entry(sources, plan.course_id)
    if existing is None:
        sources.append(source_entry)
        source_action = "add"
    else:
        existing.clear()
        existing.update(source_entry)
        source_action = "update"
    sources_data["sources"] = sources

    local_assets_data = read_yaml(local_assets_path) or {"courses": {}}
    local_assets_data.setdefault("courses", {})[plan.course_id] = {
        "source_dir": str(plan.source_root),
        "video_globs": plan.video_globs,
        "video_publish_name": "{lesson_id}-intro{suffix}",
    }

    should_write_course_yaml = plan.write_course_yaml and not course_yaml_path.exists()

    print(f"Course root: {plan.source_root}")
    print(f"Website root: {plan.website_root}")
    print(f"Course id: {plan.course_id}")
    print(f"Title: {plan.title}")
    print(f"Repo: {plan.repo_url} ({plan.branch})")
    print(f"Lessons: {', '.join(path.name for path in lesson_dirs(plan.source_root))}")
    print(f"Fallback: {plan.fallback}")
    print(f"course-sources.yaml: {source_action} {plan.course_id}")
    print("course-assets.local.yaml: set local video source and globs")
    if should_write_course_yaml:
        print("course.yaml: create")
    elif plan.write_course_yaml and course_yaml_path.exists():
        print("course.yaml: exists, leave unchanged")

    dirty = run_git(plan.source_root, "status", "--porcelain")
    if dirty:
        print("Warning: source repo has uncommitted changes; website sync reads the remote repo.")

    ahead = run_git(plan.source_root, "rev-list", "--count", "@{u}..HEAD")
    if ahead and ahead != "0":
        print(f"Warning: source branch is {ahead} commit(s) ahead of upstream; push before syncing.")

    if dry_run:
        print("\nDry run only. Re-run without --dry-run to write these changes.")
        return

    write_yaml(sources_path, sources_data)
    write_yaml(local_assets_path, local_assets_data)
    if should_write_course_yaml:
        write_yaml(course_yaml_path, planned_course_yaml(plan))
    print("\nWrote website course configuration.")


def main() -> int:
    args = parse_args()
    try:
        plan = build_plan(args)
        apply_plan(plan, dry_run=args.dry_run)
        return 0
    except Exception as exc:
        print(f"publish_course: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
