#!/bin/zsh
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR" || exit 1
/usr/bin/python3 -m reset_routine run
