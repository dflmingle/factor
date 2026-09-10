#!/usr/bin/env python3
"""Portable entry point for the bundled PandaAI research skill.

Examples:
    python scripts/pandaai.py bootstrap
    python scripts/pandaai.py batch candidates.txt --start 20210907 --end 20260907
    python scripts/pandaai.py analyze corr factor-a.csv factor-b.csv

The account token is never read from this repository. The PandaAI CLI keeps it in the
user's local configuration directory after an interactive login.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_RELATIVE = Path("vendor") / "skill-pandaai-factor-online"
SCRIPT_NAMES = {
    "bootstrap": "bootstrap.py",
    "batch": "batch.py",
    "analyze": "analyze.py",
    "collect": "collect_results.py",
    "selftest": "selftest.py",
    "composites": "build_composites.py",
    "competition-proxy": "competition_proxy.py",
}


def skill_candidates() -> list[Path]:
    paths: list[Path] = []
    configured = os.environ.get("PANDAAI_FACTOR_SKILL_DIR")
    if configured:
        paths.append(Path(configured).expanduser())

    paths.append(PROJECT_ROOT / SKILL_RELATIVE)
    home = Path.home()
    for parent in (".codex/skills", ".claude/skills", ".cursor/skills", ".openclaw/skills"):
        paths.append(home / parent / "skill-pandaai-factor-online")
        paths.append(home / parent / "pandaai-factor-online")

    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            unique.append(resolved)
            seen.add(resolved)
    return unique


def find_skill() -> Path | None:
    for root in skill_candidates():
        if (root / "SKILL.md").is_file() and (root / "scripts").is_dir():
            return root
    return None


def usage() -> None:
    print("Usage: python scripts/pandaai.py <command> [arguments...]")
    print("Commands:")
    for command in SCRIPT_NAMES:
        print(f"  {command:<18} run the bundled Skill script")
    print("  skill-path          print the Skill directory in use")
    print()
    print("Set PANDAAI_FACTOR_SKILL_DIR to override the bundled Skill directory.")


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help", "help"}:
        usage()
        return 0

    command = sys.argv[1]
    skill = find_skill()
    if skill is None:
        print(
            "PandaAI Skill not found. Clone this repository with its tracked files, "
            "or set PANDAAI_FACTOR_SKILL_DIR to an installed skill directory.",
            file=sys.stderr,
        )
        return 2

    if command == "skill-path":
        print(skill)
        return 0

    script_name = SCRIPT_NAMES.get(command)
    if script_name is None:
        print(f"Unknown command: {command}", file=sys.stderr)
        usage()
        return 2

    script = skill / "scripts" / script_name
    if not script.is_file():
        print(f"Skill script is missing: {script}", file=sys.stderr)
        return 2

    completed = subprocess.run([sys.executable, str(script), *sys.argv[2:]], cwd=PROJECT_ROOT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
