from __future__ import annotations

import argparse

from .actions import run_reset
from .config import load_config


MAX_SECTION_ITEMS = 20


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local macOS reset routine")
    parser.add_argument("--config", default="config.json", help="Path to config file")

    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the reset routine")
    run_parser.add_argument("--dry-run", action="store_true", help="Preview changes without moving files, deleting duplicates, or hiding apps")

    preview_parser = subparsers.add_parser("preview", help="Preview the reset routine")
    preview_parser.add_argument("--dry-run", action="store_true", help=argparse.SUPPRESS)
    return parser


def print_result(result) -> None:
    mode = "dry run" if result.dry_run else "live run"
    hidden_count = sum(1 for item in result.cleaned_apps if item["status"] == "hidden")
    print(f"mode: {mode}")
    print(f"desktop old files moved: {result.desktop.moved_count}")
    print(f"desktop duplicates moved: {result.desktop.duplicate_count}")
    print(f"downloads old files moved: {result.downloads.moved_count}")
    print(f"downloads duplicates moved: {result.downloads.duplicate_count}")
    print(f"apps hidden: {hidden_count}")
    print(f"plan path: {result.plan_path}")

    _print_section(
        "desktop review moves",
        [f"{item['from']} -> {item['to']}" for item in result.desktop.moved_old],
    )
    _print_section(
        "desktop duplicate review moves",
        [f"{item['from']} -> {item['to']} (kept {item['kept']})" for item in result.desktop.moved_duplicates],
    )
    _print_section(
        "downloads review moves",
        [f"{item['from']} -> {item['to']}" for item in result.downloads.moved_old],
    )
    _print_section(
        "downloads duplicate review moves",
        [f"{item['from']} -> {item['to']} (kept {item['kept']})" for item in result.downloads.moved_duplicates],
    )

    _print_section("desktop skipped", result.desktop.skipped)
    _print_section("downloads skipped", result.downloads.skipped)
    _print_section(
        "cleaned apps",
        [f"{item['app_name']}: {item['status']}" for item in result.cleaned_apps],
    )


def _print_section(title: str, items: list[str]) -> None:
    if not items:
        return

    print(f"{title}:")
    for item in items[:MAX_SECTION_ITEMS]:
        print(f"- {item}")
    remaining = len(items) - MAX_SECTION_ITEMS
    if remaining > 0:
        print(f"- ... and {remaining} more")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config)
    dry_run = True if args.command == "preview" else args.dry_run
    result = run_reset(config, dry_run=dry_run)
    print_result(result)
    return 0 if result.ok else 1
