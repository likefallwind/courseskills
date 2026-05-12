#!/usr/bin/env python3
"""Register an AI-generated course in the aistudy101 website.

This script edits website-side config only:
- course-sources.yaml
- course-assets.local.yaml

It never moves or deletes source course videos. Website sync later copies videos
to static/course-assets using safe public filenames.
"""

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish an AI-generated course directory into aistudy101 website config."
    )
    parser.add_argument("--source", default=".", help="Generated course root; default: cwd")
    parser.add_argument("--website-root", default=str(DEFAULT_WEBSITE_ROOT))
    parser.add_argument("--course-id", help="Website course id, e.g. ai-concept")
    parser.add_argument(
        "--repo-url",
        help="Source repository URL. Prefer SSH, e.g. git@gitee.com:owner/repo.git",
    )
    parser.add_argument("--branch", help="Source branch; inferred from git")
    parser.add_argument("--title", help="Curriculum course title")
    parser.add_argument("--stage", help="小学 / 初中 / 高中 / 大学")
    parser.add_argument("--education-phase", default="基础教育")
    parser.add_argument("--track", help="Course track, e.g. AI 通识")
    parser.add_argument("--status", default="待审核", help="已发布 / 待审核 / AI初稿")
    parser.add_argument("--version", default="0.1")
    parser.add_argument("--hours", type=float, help="Course hours or lesson count")
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
        help="Local video glob relative to source root. Can be passed multiple times.",
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
        return f"git@{scp.group(1)}:{scp.group(2)}.git"
    https = re.fullmatch(r"(https?://.+?)(?:\.git)?/?", url)
    if https:
        return https.group(1)
    return url


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
    intro_title = extract_course_info_value(source_root / "introduction.md", "课程名称")
    if intro_title:
        return intro_title
    for name in ("README.md", "introduction.md", "syllabus.md"):
        title = first_heading(source_root / name)
        if title:
            return title
    return source_root.name


def extract_course_info_value(path: Path, label: str) -> str | None:
    if not path.exists():
        return None
    pattern = re.compile(rf"^\s*-\s*\*\*{re.escape(label)}\*\*[：:]\s*(.+?)\s*$")
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = pattern.match(line)
        if match:
            return strip_markdown(match.group(1))
    return None


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


def infer_track(source_root: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    text = joined_summary_text(source_root)
    if "通识" in text:
        return "AI 通识"
    if re.search(r"拔尖|竞赛|创新", text):
        return "拔尖创新培养"
    return "AI 通识"


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
    if re.search(r"大模型|LLM|Agent", text, flags=re.IGNORECASE):
        themes.append("大模型 / LLM")
    return dedupe(themes)


def lesson_dirs(source_root: Path) -> list[Path]:
    dirs = [
        path
        for path in source_root.iterdir()
        if path.is_dir() and re.fullmatch(r"lesson0*\d+", path.name, flags=re.IGNORECASE)
    ]
    return sorted(dirs, key=lambda path: int(re.search(r"\d+", path.name).group(0)))


def strip_markdown(text: str) -> str:
    return re.sub(r"[*_`]+", "", text).strip()


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


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
    fallback = {
        "title": title,
        "stage": infer_stage(source_root, args.stage),
        "education_phase": args.education_phase,
        "track": infer_track(source_root, args.track),
        "status": args.status,
        "version": str(args.version),
        "hours": infer_hours(source_root, args.hours),
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
    )


def planned_source_entry(plan: CoursePlan) -> dict[str, Any]:
    return {
        "id": plan.course_id,
        "type": "gitee",
        "repo": plan.repo_url,
        "branch": plan.branch,
        "fallback": plan.fallback,
    }


def apply_plan(plan: CoursePlan, dry_run: bool) -> None:
    sources_path = plan.website_root / "course-sources.yaml"
    local_assets_path = plan.website_root / "course-assets.local.yaml"

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

    video_candidates = video_files(plan.source_root, plan.video_globs)
    lesson_names = [path.name for path in lesson_dirs(plan.source_root)]

    print(f"Course root: {plan.source_root}")
    print(f"Website root: {plan.website_root}")
    print(f"Course id: {plan.course_id}")
    print(f"Title: {plan.title}")
    print(f"Repo: {plan.repo_url} ({plan.branch})")
    print(f"Lessons: {', '.join(lesson_names)}")
    print(f"Local videos: {len(video_candidates)}")
    print(f"Fallback: {plan.fallback}")
    print(f"course-sources.yaml: {source_action} {plan.course_id}")
    print("course-assets.local.yaml: set local video source and copy globs")
    print("Source course repo: leave unchanged")

    dirty = run_git(plan.source_root, "status", "--porcelain")
    if dirty:
        print("Warning: source repo has uncommitted changes; website sync reads committed remote text.")

    if dry_run:
        print("\nDry run only. Re-run without --dry-run to write website config.")
        return

    write_yaml(sources_path, sources_data)
    write_yaml(local_assets_path, local_assets_data)
    print("\nWrote website course configuration.")


def video_files(source_root: Path, patterns: list[str]) -> list[Path]:
    result: dict[Path, None] = {}
    for pattern in patterns:
        for path in source_root.glob(pattern):
            if path.is_file() and path.suffix.lower() in {".mp4", ".webm", ".ogg"}:
                result[path.resolve()] = None
    return sorted(result)


def main() -> int:
    args = parse_args()
    try:
        plan = build_plan(args)
        apply_plan(plan, dry_run=args.dry_run)
        return 0
    except Exception as exc:
        print(f"publish_ai_course: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
