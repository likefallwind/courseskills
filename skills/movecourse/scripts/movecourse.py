#!/usr/bin/env python3
"""Register generated course lesson videos for aistudy101 local publishing."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_WEBSITE_ROOT = Path("/home/likefallwind/code/aistudy101-website")
DEFAULT_DEST_ROOT = DEFAULT_WEBSITE_ROOT / "static/course-assets"
DEFAULT_SOURCES_YAML = DEFAULT_WEBSITE_ROOT / "course-sources.yaml"
DEFAULT_COURSE_ID_REGISTRY = Path(
    "/home/likefallwind/code/aistudy101-website/docs/course-id-registry.md"
)
DEFAULT_LOCAL_ASSETS_YAML = DEFAULT_WEBSITE_ROOT / "course-assets.local.yaml"
DEFAULT_VIDEO_GLOBS = ["lesson*/*.mp4"]
DEFAULT_VIDEO_PUBLISH_NAME = "{lesson_id}-intro{suffix}"
DEFAULT_VIDEO_BASE_URL = "/course-assets"

COURSE_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SAFE_FILENAME_RE = re.compile(r"[A-Za-z0-9._-]+")


@dataclass(frozen=True)
class VideoPlan:
    lesson_id: str
    source: Path
    publish_name: str
    url: str


@dataclass(frozen=True)
class CourseIdEntry:
    title: str
    standard_title: str
    course_id: str
    status: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Register lesson*/.mp4 files in course-assets.local.yaml for aistudy101. "
            "Static copying is available only with --publish-static."
        )
    )
    parser.add_argument("--course", help="Course id, e.g. ai-enlightenment")
    parser.add_argument("--source", default=".", help="Source course directory; default: cwd")
    parser.add_argument(
        "--website-root",
        default=str(DEFAULT_WEBSITE_ROOT),
        help="aistudy101 website checkout root",
    )
    parser.add_argument(
        "--local-assets-yaml",
        default=str(DEFAULT_LOCAL_ASSETS_YAML),
        help="course-assets.local.yaml to add or update",
    )
    parser.add_argument(
        "--dest-root",
        default=str(DEFAULT_DEST_ROOT),
        help="Website static/course-assets root used only with --publish-static",
    )
    parser.add_argument(
        "--sources-yaml",
        default=str(DEFAULT_SOURCES_YAML),
        help="course-sources.yaml used to validate course ids",
    )
    parser.add_argument(
        "--course-id-registry",
        default=str(DEFAULT_COURSE_ID_REGISTRY),
        help="Markdown course ID registry used to resolve planned curriculum course ids",
    )
    parser.add_argument(
        "--course-title",
        help="Curriculum or standard Chinese course title; resolves to --course via the ID registry",
    )
    parser.add_argument(
        "--video-publish-name",
        default=DEFAULT_VIDEO_PUBLISH_NAME,
        help=(
            "Filename template stored in course-assets.local.yaml. Supports "
            "{course_id}, {lesson_id}, {lesson_number}, {source_name}, "
            "{source_stem}, and {suffix}."
        ),
    )
    parser.add_argument(
        "--filename-template",
        help=(
            "Deprecated alias for --video-publish-name. Also supports the legacy "
            "{lesson} placeholder."
        ),
    )
    parser.add_argument(
        "--video-glob",
        action="append",
        dest="video_globs",
        help='Video glob to store in course-assets.local.yaml; default: "lesson*/*.mp4"',
    )
    parser.add_argument(
        "--video-base-url",
        default=DEFAULT_VIDEO_BASE_URL,
        help="Base URL expected after npm run sync; default: /course-assets",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show operations without writing")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing destination mp4")
    parser.add_argument(
        "--publish-static",
        action="store_true",
        help="Also copy videos into static/course-assets for local preview only.",
    )
    parser.add_argument(
        "--move",
        action="store_true",
        help=(
            "Delete source mp4 after verified static copy. Requires --publish-static "
            "and should be used only when explicitly requested."
        ),
    )
    parser.add_argument(
        "--allow-unknown-course",
        action="store_true",
        help="Proceed even when --course is absent from course-sources.yaml and the ID registry",
    )
    parser.add_argument("--list-courses", action="store_true", help="Print known course ids and exit")
    return parser.parse_args()


def load_course_ids(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Course registry not found: {path}")

    ids: list[str] = []
    id_line = re.compile(r"^\s*-\s+id:\s*['\"]?([^'\"\s#]+)")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = id_line.match(line)
        if match:
            ids.append(match.group(1))
    return ids


def validate_course_id(course_id: str) -> str:
    if not COURSE_ID_RE.fullmatch(course_id):
        raise ValueError(
            f"Invalid course id {course_id!r}; use lowercase kebab-case letters, "
            "digits, and single hyphens only"
        )
    if len(course_id) > 64:
        raise ValueError(f"Invalid course id {course_id!r}; maximum length is 64")
    return course_id


def load_course_id_registry(path: Path) -> list[CourseIdEntry]:
    if not path.exists():
        return []

    entries: list[CourseIdEntry] = []
    row_re = re.compile(
        r"^\|\s*(?P<columns>.+?)\s*\|\s*$",
    )
    for line in path.read_text(encoding="utf-8").splitlines():
        match = row_re.match(line)
        if not match:
            continue
        cells = [cell.strip() for cell in match.group("columns").split("|")]
        if len(cells) == 6:
            title, standard_title, course_id, status = cells[2], cells[3], cells[4], cells[5]
        elif len(cells) == 5:
            title, standard_title, course_id, status = cells[1], cells[2], cells[3], cells[4]
        else:
            continue
        if title in {"全景图名称", "---"} or "`" not in course_id:
            continue
        id_match = re.fullmatch(r"`([^`]+)`", course_id)
        if id_match is None:
            continue
        entries.append(
            CourseIdEntry(
                title=title,
                standard_title=standard_title,
                course_id=validate_course_id(id_match.group(1)),
                status=status,
            )
        )
    return entries


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", "", title).lower()


def resolve_course_id_from_title(
    title: str, registry_entries: list[CourseIdEntry]
) -> CourseIdEntry | None:
    normalized = normalize_title(title)
    matches = [
        entry
        for entry in registry_entries
        if normalize_title(entry.title) == normalized
        or normalize_title(entry.standard_title) == normalized
    ]
    if not matches:
        return None
    if len(matches) > 1:
        ids = ", ".join(entry.course_id for entry in matches)
        raise ValueError(f"Course title {title!r} matches multiple course ids: {ids}")
    return matches[0]


def lesson_sort_key(path: Path) -> tuple[int, str]:
    match = re.fullmatch(r"lesson0*(\d+)", path.name, flags=re.IGNORECASE)
    if not match:
        return (sys.maxsize, path.name)
    return (int(match.group(1)), path.name)


def normalized_lesson_name(path: Path) -> str:
    match = re.fullmatch(r"lesson0*(\d+)", path.name, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"Unsupported lesson directory name: {path.name}")
    return f"lesson{int(match.group(1))}"


def render_video_name(template: str, *, source: Path, course_id: str, lesson_id: str) -> str:
    lesson_number = lesson_id.removeprefix("lesson")
    return template.format(
        course_id=course_id,
        lesson_id=lesson_id,
        lesson=lesson_id,
        lesson_number=lesson_number,
        source_name=source.name,
        source_stem=source.stem,
        suffix=source.suffix.lower(),
    )


def video_url(base_url: str, course_id: str, lesson_id: str, filename: str) -> str:
    return f"{base_url.rstrip('/')}/{course_id}/{lesson_id}/video/{filename}"


def collect_video_plan(
    source_root: Path,
    course: str,
    publish_template: str,
    video_base_url: str,
) -> list[VideoPlan]:
    if not source_root.is_dir():
        raise NotADirectoryError(f"Source directory not found: {source_root}")

    lesson_dirs = sorted(
        [
            path
            for path in source_root.iterdir()
            if path.is_dir() and re.fullmatch(r"lesson0*\d+", path.name, flags=re.IGNORECASE)
        ],
        key=lesson_sort_key,
    )
    if not lesson_dirs:
        raise ValueError(f"No lessonN directories found under {source_root}")

    errors: list[str] = []
    plans: list[VideoPlan] = []
    for lesson_dir in lesson_dirs:
        lesson = normalized_lesson_name(lesson_dir)
        mp4s = sorted(path for path in lesson_dir.glob("*.mp4") if path.is_file())
        if len(mp4s) != 1:
            errors.append(f"{lesson_dir}: expected exactly one .mp4, found {len(mp4s)}")
            continue
        if mp4s[0].stat().st_size == 0:
            errors.append(f"{mp4s[0]}: source mp4 is empty")
            continue

        filename = render_video_name(
            publish_template,
            source=mp4s[0],
            course_id=course,
            lesson_id=lesson,
        )
        if not filename.lower().endswith(".mp4"):
            errors.append(f"{lesson}: video publish template must produce an .mp4 name, got {filename!r}")
            continue
        if not SAFE_FILENAME_RE.fullmatch(filename):
            errors.append(f"{lesson}: output filename must be English/ASCII-safe, got {filename!r}")
            continue

        plans.append(
            VideoPlan(
                lesson_id=lesson,
                source=mp4s[0],
                publish_name=filename,
                url=video_url(video_base_url, course, lesson, filename),
            )
        )

    if errors:
        raise ValueError("Preflight failed:\n" + "\n".join(f"- {error}" for error in errors))
    return plans


def verified_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(destination.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    shutil.copy2(source, tmp)
    if tmp.stat().st_size == 0 or source.stat().st_size != tmp.stat().st_size:
        tmp.unlink(missing_ok=True)
        raise IOError(f"Copy verification failed for {source}")
    tmp.replace(destination)


def check_static_targets(
    plans: list[VideoPlan],
    *,
    dest_root: Path,
    course: str,
    overwrite: bool,
) -> None:
    errors = []
    for plan in plans:
        destination = static_destination(dest_root, course, plan)
        if destination.exists() and not overwrite:
            errors.append(f"{destination}: already exists; pass --overwrite to replace")
    if errors:
        raise ValueError("Static publish preflight failed:\n" + "\n".join(f"- {error}" for error in errors))


def static_destination(dest_root: Path, course: str, plan: VideoPlan) -> Path:
    return dest_root / course / plan.lesson_id / "video" / plan.publish_name


def local_assets_entry(source_root: Path, video_globs: list[str], publish_template: str) -> dict[str, object]:
    return {
        "source_dir": source_root.as_posix(),
        "video_globs": video_globs,
        "video_publish_name": publish_template,
    }


def load_local_assets(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"courses": {}}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    courses = data.setdefault("courses", {})
    if not isinstance(courses, dict):
        raise ValueError(f"{path}: courses must be a YAML mapping")
    return data


def write_local_assets(
    path: Path,
    *,
    course: str,
    entry: dict[str, object],
) -> None:
    data = load_local_assets(path)
    courses = data.setdefault("courses", {})
    assert isinstance(courses, dict)
    courses[course] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def yaml_preview(course: str, entry: dict[str, object]) -> str:
    return yaml.safe_dump({"courses": {course: entry}}, allow_unicode=True, sort_keys=False).rstrip()


def print_plan(
    plans: list[VideoPlan],
    *,
    local_assets_path: Path,
    course: str,
    entry: dict[str, object],
    dry_run: bool,
) -> None:
    action = "Would update" if dry_run else "Update"
    print(f"{action}: {local_assets_path}")
    print(yaml_preview(course, entry))
    print()
    print("Expected video URL metadata after npm run sync:")
    for plan in plans:
        print(f"- {plan.lesson_id}: {plan.source} -> {plan.url}")


def print_static_manifest(
    plans: list[VideoPlan],
    *,
    dest_root: Path,
    course: str,
    action: str,
) -> None:
    for plan in plans:
        print(f"{action}: {plan.source} -> {static_destination(dest_root, course, plan)}")


def main() -> int:
    args = parse_args()
    source_root = Path(args.source).expanduser().resolve()
    website_root = Path(args.website_root).expanduser().resolve()
    dest_root = (
        website_root / "static/course-assets"
        if args.dest_root == str(DEFAULT_DEST_ROOT)
        else Path(args.dest_root).expanduser()
    ).resolve()
    sources_yaml = (
        website_root / "course-sources.yaml"
        if args.sources_yaml == str(DEFAULT_SOURCES_YAML)
        else Path(args.sources_yaml).expanduser()
    ).resolve()
    course_id_registry = (
        website_root / "docs/course-id-registry.md"
        if args.course_id_registry == str(DEFAULT_COURSE_ID_REGISTRY)
        else Path(args.course_id_registry).expanduser()
    ).resolve()
    local_assets_path = (
        website_root / "course-assets.local.yaml"
        if args.local_assets_yaml == str(DEFAULT_LOCAL_ASSETS_YAML)
        else Path(args.local_assets_yaml).expanduser()
    ).resolve()
    publish_template = args.filename_template or args.video_publish_name
    video_globs = args.video_globs or list(DEFAULT_VIDEO_GLOBS)

    try:
        if args.move and not args.publish_static:
            print("movecourse: --move requires --publish-static", file=sys.stderr)
            return 2

        course_ids = load_course_ids(sources_yaml)
        registry_entries = load_course_id_registry(course_id_registry)
        registry_ids = [entry.course_id for entry in registry_entries]
        if args.list_courses:
            known = set(course_ids)
            for course_id in course_ids:
                print(course_id)
            for entry in registry_entries:
                if entry.course_id not in known:
                    print(f"{entry.course_id}\t{entry.status}\t{entry.standard_title}")
            return 0

        course = args.course
        if args.course_title:
            entry = resolve_course_id_from_title(args.course_title, registry_entries)
            if entry is None:
                print(
                    f"movecourse: course title {args.course_title!r} is not listed in "
                    f"{course_id_registry}",
                    file=sys.stderr,
                )
                return 2
            if course and course != entry.course_id:
                print(
                    f"movecourse: --course {course!r} conflicts with --course-title "
                    f"{args.course_title!r}, which maps to {entry.course_id!r}",
                    file=sys.stderr,
                )
                return 2
            course = entry.course_id
            print(
                f"Resolved course title {args.course_title!r} to {course!r} "
                f"({entry.status})."
            )

        if not course:
            print(
                "movecourse: --course or --course-title is required unless --list-courses is used",
                file=sys.stderr,
            )
            return 2
        course = validate_course_id(course)

        if course not in course_ids and course not in registry_ids and not args.allow_unknown_course:
            print(
                f"Course id {course!r} is not listed in {sources_yaml} or "
                f"{course_id_registry}. "
                "Check the course ID registry before inventing a new id. "
                "Pass --allow-unknown-course only after confirmation.",
                file=sys.stderr,
            )
            if course_ids:
                print("Known course ids: " + ", ".join(course_ids), file=sys.stderr)
            return 2
        if course not in course_ids and course in registry_ids:
            print(
                f"Course id {course!r} is reserved in the ID registry but not yet "
                f"registered in {sources_yaml}. Local video metadata can be prepared now, "
                "but npm run sync will not publish a clickable course until course-sources.yaml is updated."
            )

        plans = collect_video_plan(
            source_root=source_root,
            course=course,
            publish_template=publish_template,
            video_base_url=args.video_base_url,
        )
        if args.publish_static:
            check_static_targets(plans, dest_root=dest_root, course=course, overwrite=args.overwrite)

        entry = local_assets_entry(source_root, video_globs, publish_template)
        print_plan(
            plans,
            local_assets_path=local_assets_path,
            course=course,
            entry=entry,
            dry_run=args.dry_run,
        )

        if args.publish_static:
            print()
            print("Static preview publish is enabled.")
            print_static_manifest(
                plans,
                dest_root=dest_root,
                course=course,
                action="Would move" if args.dry_run and args.move else "Would copy" if args.dry_run else "Move" if args.move else "Copy",
            )
        else:
            print()
            print("No files will be copied into static/course-assets.")

        if args.dry_run:
            return 0

        write_local_assets(local_assets_path, course=course, entry=entry)

        if args.publish_static:
            for plan in plans:
                verified_copy(plan.source, static_destination(dest_root, course, plan))
                if args.move:
                    plan.source.unlink()
            print(f"Completed local config update and static preview copy for {len(plans)} video file(s).")
        else:
            print(f"Completed local config update for {len(plans)} video file(s).")
            print(
                f"Next: cd {website_root} && npm run sync, then start dev with "
                "./scripts/dev.sh or npm run start so local video symlinks are exposed."
            )
        return 0
    except Exception as exc:
        print(f"movecourse: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
