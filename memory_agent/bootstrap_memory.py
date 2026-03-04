#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MEMORY_DIR = BASE_DIR / "memory"
PROMPTS_DIR = BASE_DIR / "prompts"
ENTITIES_DIR = MEMORY_DIR / "entities"
TIMELINE_DIR = MEMORY_DIR / "timeline"
PREFERENCES_DIR = MEMORY_DIR / "preferences"
ARCHIVE_SPECS_DIR = MEMORY_DIR / "archive" / "specs"
PROJECT_FILE = MEMORY_DIR / "project.md"
STATUS_FILE = TIMELINE_DIR / "current_status.md"
PREFERENCES_FILE = PREFERENCES_DIR / "current.md"
PROMPT_FILE = PROMPTS_DIR / "memory_agent_system_prompt.md"

DEFAULT_PROJECT_MD = "# Autofinisher Factory — Project Memory\n\nBootstrap created this file because it was missing. Update it with current project state.\n"
DEFAULT_STATUS_MD = "# Current Status\n\nBootstrap created this file because it was missing.\n"
DEFAULT_PREFERENCES_MD = "# Project Preferences\n\nBootstrap created this file because it was missing.\n"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_file(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def main() -> None:
    for directory in [MEMORY_DIR, ENTITIES_DIR, TIMELINE_DIR, PREFERENCES_DIR, ARCHIVE_SPECS_DIR, PROMPTS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

    created = []
    if ensure_file(PROJECT_FILE, DEFAULT_PROJECT_MD):
        created.append(str(PROJECT_FILE.relative_to(BASE_DIR.parent)))
    if ensure_file(STATUS_FILE, DEFAULT_STATUS_MD):
        created.append(str(STATUS_FILE.relative_to(BASE_DIR.parent)))
    if ensure_file(PREFERENCES_FILE, DEFAULT_PREFERENCES_MD):
        created.append(str(PREFERENCES_FILE.relative_to(BASE_DIR.parent)))

    payload = {
        "initialized_at": now_iso(),
        "memory_dir": str(MEMORY_DIR),
        "prompt_exists": PROMPT_FILE.exists(),
        "created_files": created,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
