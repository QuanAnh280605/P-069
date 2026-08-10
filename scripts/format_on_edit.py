#!/usr/bin/env python3
"""
PostToolUse hook: auto-format edited Python files with ruff.

Reads a Claude Code PostToolUse payload from stdin; when the edited file is a
project ``.py`` file, runs ``ruff format`` then ``ruff check --fix`` on it.
Mirrors the stdin-reading convention of ``log_hook.py`` and exits silently so it
never blocks the tool flow.
"""

import json
import subprocess
import sys
from pathlib import Path

_SKIP_PARTS = {".venv", "node_modules", "site-packages", ".git"}


def _is_project_python(path_str: str) -> bool:
    """True for a ``.py`` file that is not inside a dependency directory."""
    if not path_str.endswith(".py"):
        return False
    parts = Path(path_str).parts
    return not any(part in _SKIP_PARTS for part in parts)


def format_file(path_str: str) -> None:
    """Run ruff format + check --fix on a single file, ignoring failures."""
    for args in (["format", path_str], ["check", "--fix", path_str]):
        try:
            subprocess.run(["ruff", *args], check=False, capture_output=True)  # noqa: S603,S607
        except FileNotFoundError:
            # ruff not on PATH in this hook's environment — skip silently.
            return


def main() -> None:
    """Read the hook payload from stdin and format the edited file if applicable."""
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace").strip()
    if not raw:
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return

    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if _is_project_python(file_path):
        format_file(file_path)


if __name__ == "__main__":
    main()
