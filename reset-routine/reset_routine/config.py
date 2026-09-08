from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent.parent


def _resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = APP_ROOT / path
    return path


@dataclass
class Config:
    desktop_dir: Path = field(default_factory=lambda: Path.home() / "Desktop")
    downloads_dir: Path = field(default_factory=lambda: Path.home() / "Downloads")
    archive_dir: Path = APP_ROOT / "data" / "archives"
    plans_dir: Path = APP_ROOT / "plans"
    clean_apps: list[str] = field(default_factory=lambda: ["Safari", "Google Chrome", "Mail", "Slack"])
    old_file_days: int = 30
    task_templates: list[str] = field(
        default_factory=lambda: [
            "Review tomorrow's calendar",
            "Pick the top 3 priorities",
            "Clear urgent replies",
            "Set the first task for the morning",
        ]
    )

    def ensure_directories(self) -> None:
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.plans_dir.mkdir(parents=True, exist_ok=True)


def load_config(config_path: str | Path | None = None) -> Config:
    path = _resolve_path(config_path) if config_path else APP_ROOT / "config.json"
    config = Config()

    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        config.desktop_dir = _resolve_path(data.get("desktop_dir", config.desktop_dir))
        config.downloads_dir = _resolve_path(data.get("downloads_dir", config.downloads_dir))
        config.archive_dir = _resolve_path(data.get("archive_dir", config.archive_dir))
        config.plans_dir = _resolve_path(data.get("plans_dir", config.plans_dir))
        config.clean_apps = [str(item) for item in data.get("clean_apps", config.clean_apps)]
        config.old_file_days = int(data.get("old_file_days", config.old_file_days))
        config.task_templates = [str(item) for item in data.get("task_templates", config.task_templates)]

    config.ensure_directories()
    return config
