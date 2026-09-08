from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .config import Config


ACTIVE_DOWNLOAD_SUFFIXES = {".crdownload", ".download", ".part"}

FILE_CATEGORY_SUFFIXES = {
    "documents": {".doc", ".docx", ".md", ".pages", ".pdf", ".rtf", ".txt"},
    "images": {".gif", ".heic", ".jpeg", ".jpg", ".png", ".svg", ".webp"},
    "audio": {".aac", ".m4a", ".mp3", ".wav"},
    "video": {".m4v", ".mkv", ".mov", ".mp4"},
    "archives": {".7z", ".gz", ".rar", ".tar", ".zip"},
    "installers": {".dmg", ".pkg"},
    "code": {".css", ".html", ".js", ".json", ".py", ".ts", ".tsx"},
    "spreadsheets": {".csv", ".numbers", ".xlsx"},
}


@dataclass
class FolderSummary:
    source_dir: Path
    target_dir: Path
    moved_old: list[dict[str, str]]
    moved_duplicates: list[dict[str, str]]
    left_in_place: list[str]
    skipped: list[str]
    ok: bool = True

    @property
    def moved_count(self) -> int:
        return len(self.moved_old)

    @property
    def duplicate_count(self) -> int:
        return len(self.moved_duplicates)


@dataclass
class ResetResult:
    stamp: str
    desktop: FolderSummary
    downloads: FolderSummary
    cleaned_apps: list[dict[str, str | bool]]
    plan_path: Path
    dry_run: bool

    @property
    def ok(self) -> bool:
        return self.desktop.ok and self.downloads.ok and all(bool(item["ok"]) for item in self.cleaned_apps)


def run_reset(config: Config, dry_run: bool = False) -> ResetResult:
    stamp = datetime.now().strftime("%Y-%m-%d")
    desktop = clean_top_level_files(
        config.desktop_dir,
        config.archive_dir / stamp / "desktop",
        old_file_days=config.old_file_days,
        dry_run=dry_run,
    )
    downloads = clean_top_level_files(
        config.downloads_dir,
        config.archive_dir / stamp / "downloads",
        old_file_days=config.old_file_days,
        dry_run=dry_run,
    )
    cleaned_apps = [clean_app(app_name, dry_run=dry_run) for app_name in config.clean_apps if app_name.strip()]
    plan_path = write_tomorrow_plan(config, desktop, downloads, cleaned_apps, dry_run=dry_run)
    return ResetResult(
        stamp=stamp,
        desktop=desktop,
        downloads=downloads,
        cleaned_apps=cleaned_apps,
        plan_path=plan_path,
        dry_run=dry_run,
    )


def clean_top_level_files(
    source_dir: Path,
    target_dir: Path,
    old_file_days: int,
    dry_run: bool = False,
) -> FolderSummary:
    if not source_dir.exists():
        return FolderSummary(
            source_dir=source_dir,
            target_dir=target_dir,
            moved_old=[],
            moved_duplicates=[],
            left_in_place=[],
            skipped=[f"Missing folder: {source_dir}"],
            ok=False,
        )

    moved_old: list[dict[str, str]] = []
    moved_duplicates: list[dict[str, str]] = []
    left_in_place: list[str] = []
    skipped: list[str] = []
    seen_hashes: dict[str, Path] = {}
    now = datetime.now()

    entries = sorted(
        source_dir.iterdir(),
        key=lambda item: (-item.stat().st_mtime, item.name.lower()),
    )

    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            skipped.append(f"Skipped folder: {entry.name}")
            continue
        if entry.suffix.lower() in ACTIVE_DOWNLOAD_SUFFIXES:
            skipped.append(f"Skipped active download: {entry.name}")
            continue

        file_hash = hash_file(entry)
        if file_hash in seen_hashes:
            kept_path = seen_hashes[file_hash]
            category = categorize_file(entry)
            month_bucket = datetime.fromtimestamp(entry.stat().st_mtime).strftime("%Y-%m")
            destination = unique_destination(target_dir / "review-duplicates" / month_bucket / category / entry.name)
            moved_duplicates.append({"from": str(entry), "to": str(destination), "kept": str(kept_path)})
            if not dry_run:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(entry), str(destination))
            continue
        seen_hashes[file_hash] = entry

        age_days = int((now - datetime.fromtimestamp(entry.stat().st_mtime)).days)
        if age_days < old_file_days:
            left_in_place.append(str(entry))
            continue

        category = categorize_file(entry)
        month_bucket = datetime.fromtimestamp(entry.stat().st_mtime).strftime("%Y-%m")
        destination = unique_destination(target_dir / "review-old" / month_bucket / category / entry.name)
        moved_old.append({"from": str(entry), "to": str(destination), "category": category})
        if dry_run:
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(entry), str(destination))

    return FolderSummary(
        source_dir=source_dir,
        target_dir=target_dir,
        moved_old=moved_old,
        moved_duplicates=moved_duplicates,
        left_in_place=left_in_place,
        skipped=skipped,
    )


def categorize_file(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    for category, suffixes in FILE_CATEGORY_SUFFIXES.items():
        if suffix in suffixes:
            return category
    return "other"


def unique_destination(target: Path) -> Path:
    if not target.exists():
        return target

    for index in range(2, 1000):
        candidate = target.with_name(f"{target.stem}-{index}{target.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find a unique destination for {target}")


def hash_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def clean_app(app_name: str, dry_run: bool = False) -> dict[str, str | bool]:
    if dry_run:
        return {"app_name": app_name, "status": "dry-run", "ok": True}

    script = """
on run argv
    set appName to item 1 of argv
    tell application "System Events"
        if (name of processes) contains appName then
            set visible of process appName to false
            return "hidden"
        end if
    end tell
    return "not-running"
end run
""".strip()

    try:
        completed = subprocess.run(
            ["osascript", "-e", script, app_name],
            check=True,
            capture_output=True,
            text=True,
        )
        status = (completed.stdout or "not-running").strip() or "not-running"
        return {"app_name": app_name, "status": status, "ok": True}
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip() or f"Could not clean {app_name}."
        return {"app_name": app_name, "status": message, "ok": False}


def write_tomorrow_plan(
    config: Config,
    desktop: FolderSummary,
    downloads: FolderSummary,
    cleaned_apps: list[dict[str, str | bool]],
    dry_run: bool = False,
) -> Path:
    tomorrow = datetime.now() + timedelta(days=1)
    plan_path = unique_destination(config.plans_dir / f"{tomorrow.strftime('%Y-%m-%d')}-plan.md")
    lines = build_tomorrow_plan_lines(config, tomorrow, desktop, downloads, cleaned_apps)
    if not dry_run:
        config.plans_dir.mkdir(parents=True, exist_ok=True)
        plan_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return plan_path


def build_tomorrow_plan_lines(
    config: Config,
    tomorrow: datetime,
    desktop: FolderSummary,
    downloads: FolderSummary,
    cleaned_apps: list[dict[str, str | bool]],
) -> list[str]:
    hidden_apps = [str(item["app_name"]) for item in cleaned_apps if item["status"] == "hidden"]
    task_templates = config.task_templates or ["Pick the top 3 priorities"]

    lines = [
        f"# Tomorrow Plan - {tomorrow.strftime('%A, %B %d')}",
        "",
        "## Carry Forward",
    ]
    lines.extend(f"- [ ] {task}" for task in task_templates)
    lines.extend(
        [
            "",
            "## Top 3",
            "- [ ]",
            "- [ ]",
            "- [ ]",
            "",
            "## Quick Reset Summary",
            f"- Desktop old files moved to review: {desktop.moved_count}",
            f"- Desktop duplicates moved to review: {desktop.duplicate_count}",
            f"- Downloads old files moved to review: {downloads.moved_count}",
            f"- Downloads duplicates moved to review: {downloads.duplicate_count}",
            f"- Apps hidden: {', '.join(hidden_apps) if hidden_apps else 'None'}",
            "",
            "## Notes",
            "- ",
        ]
    )
    return lines
