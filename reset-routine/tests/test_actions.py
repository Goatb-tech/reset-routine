from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from reset_routine.actions import run_reset
from reset_routine.config import Config


class ResetRoutineTests(unittest.TestCase):
    def test_dry_run_marks_old_files_and_duplicate_review_moves_without_touching_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            desktop_dir = root / "Desktop"
            downloads_dir = root / "Downloads"
            desktop_dir.mkdir()
            downloads_dir.mkdir()
            old_desktop_file = desktop_dir / "notes.txt"
            old_download_file = downloads_dir / "image.png"
            duplicate_download_file = downloads_dir / "image-copy.png"
            old_desktop_file.write_text("old desktop", encoding="utf-8")
            old_download_file.write_text("same", encoding="utf-8")
            duplicate_download_file.write_text("same", encoding="utf-8")

            old_timestamp = time.time() - (40 * 24 * 60 * 60)
            os.utime(old_desktop_file, (old_timestamp, old_timestamp))
            os.utime(old_download_file, (old_timestamp, old_timestamp))
            os.utime(duplicate_download_file, (old_timestamp, old_timestamp))

            config = Config(
                desktop_dir=desktop_dir,
                downloads_dir=downloads_dir,
                archive_dir=root / "archives",
                plans_dir=root / "plans",
                clean_apps=["Safari"],
                old_file_days=30,
                task_templates=["Pick top priorities"],
            )
            config.ensure_directories()

            result = run_reset(config, dry_run=True)

            self.assertTrue(old_desktop_file.exists())
            self.assertTrue(old_download_file.exists())
            self.assertTrue(duplicate_download_file.exists())
            self.assertEqual(result.desktop.moved_count, 1)
            self.assertEqual(result.downloads.moved_count, 1)
            self.assertEqual(result.downloads.duplicate_count, 1)
            self.assertFalse(result.plan_path.exists())
            self.assertEqual(result.cleaned_apps[0]["status"], "dry-run")

    def test_live_run_moves_old_files_and_duplicates_to_review_and_writes_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            desktop_dir = root / "Desktop"
            downloads_dir = root / "Downloads"
            desktop_dir.mkdir()
            downloads_dir.mkdir()
            desktop_file = desktop_dir / "notes.txt"
            download_file = downloads_dir / "report.pdf"
            duplicate_file = downloads_dir / "report-copy.pdf"
            desktop_file.write_text("desktop", encoding="utf-8")
            download_file.write_text("duplicate", encoding="utf-8")
            duplicate_file.write_text("duplicate", encoding="utf-8")

            old_timestamp = time.time() - (40 * 24 * 60 * 60)
            os.utime(desktop_file, (old_timestamp, old_timestamp))
            os.utime(download_file, (old_timestamp, old_timestamp))
            os.utime(duplicate_file, (old_timestamp, old_timestamp))

            config = Config(
                desktop_dir=desktop_dir,
                downloads_dir=downloads_dir,
                archive_dir=root / "archives",
                plans_dir=root / "plans",
                clean_apps=["Safari", "Mail"],
                old_file_days=30,
                task_templates=["Review calendar"],
            )
            config.ensure_directories()

            with patch(
                "reset_routine.actions.subprocess.run",
                return_value=CompletedProcess(args=["osascript"], returncode=0, stdout="hidden\n", stderr=""),
            ) as mocked_run:
                result = run_reset(config, dry_run=False)

            self.assertFalse(desktop_file.exists())
            self.assertFalse(duplicate_file.exists())
            self.assertFalse(download_file.exists())
            self.assertTrue(result.plan_path.exists())
            self.assertIn("Review calendar", result.plan_path.read_text(encoding="utf-8"))
            self.assertIn("Apps hidden: Safari, Mail", result.plan_path.read_text(encoding="utf-8"))
            self.assertIn("Downloads duplicates moved to review: 1", result.plan_path.read_text(encoding="utf-8"))
            self.assertEqual(result.downloads.duplicate_count, 1)
            self.assertTrue(any("review-duplicates" in item["to"] for item in result.downloads.moved_duplicates))
            self.assertEqual(mocked_run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
