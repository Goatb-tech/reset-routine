# Reset Routine

Local macOS reset automation for end-of-day cleanup.

It does five things in one run:

- moves exact duplicate top-level files into duplicate review folders
- moves older top-level Desktop and Downloads files into dated review folders
- hides configured apps instead of closing them
- creates a tomorrow plan note with carry-forward tasks
- supports a safe `--dry-run` preview mode before making changes

## Folder Layout

```text
Reset Routine/
├── config.json
├── data/
├── plans/
├── reset_routine/
├── scripts/
└── tests/
```

## Run It

From inside this folder:

```bash
python3 -m reset_routine run --dry-run
python3 -m reset_routine run
```

Or use the launcher:

```bash
scripts/run.command
```

## What It Cleans

- only top-level files in `Desktop` and `Downloads`
- hidden files are skipped
- folders are skipped
- active partial downloads like `.crdownload` are skipped
- exact duplicate files are moved into `review-duplicates/` after one copy is kept in place
- recent files stay where they are
- files older than `old_file_days` move into `review-old/` folders so you can review them manually later

Older files are grouped into dated review folders and then by month and file type under `data/archives/`.
Duplicate candidates are grouped separately under `review-duplicates/` so you can inspect them before removing anything.

## Config

Edit `config.json` to change:

- which Desktop and Downloads folders to manage
- where archives are stored
- which apps get hidden
- how old a file must be before it gets moved to review
- which carry-forward tasks appear in tomorrow's note

Default plan notes are written to `plans/`.

## Test

```bash
python3 -m unittest discover -s tests
```
