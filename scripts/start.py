#!/usr/bin/env python3
"""Prepare this factor workspace on a new computer.

The default operation is read-only apart from the CLI installation and PandaAI config
bootstrap. Pass --login-if-needed to open the interactive PandaAI login when the local
account is not authenticated. No factor is created and no paid run is started here.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = PROJECT_ROOT / "scripts" / "pandaai.py"


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    printable = " ".join(command)
    print(f"$ {printable}")
    return subprocess.run(command, cwd=PROJECT_ROOT, capture_output=capture, text=True)


def cli_candidates() -> list[Path]:
    """Find tool bin directories that may not yet be present in this process's PATH."""
    candidates: list[Path] = []
    uv = shutil.which("uv")
    if uv:
        try:
            result = subprocess.run(
                [uv, "tool", "dir", "--bin"],
                capture_output=True,
                text=True,
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired):
            result = None
        if result and result.returncode == 0:
            candidates.extend(Path(line.strip()).expanduser() for line in result.stdout.splitlines()
                              if line.strip())

    # These are the conventional user-level locations used by uv/pipx on supported hosts.
    candidates.extend(
        [
            Path.home() / ".local" / "bin",
            Path.home() / "bin",
            Path.home() / "AppData" / "Local" / "pipx" / "bin",
            Path.home() / "AppData" / "Roaming" / "Python" / "Scripts",
        ]
    )
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            unique.append(resolved)
            seen.add(resolved)
    return unique


def expose_cli() -> str | None:
    """Return the CLI path and expose its directory to child processes."""
    found = shutil.which("pandaai-cli")
    if found:
        return found

    names = ("pandaai-cli.exe", "pandaai-cli.cmd", "pandaai-cli") if sys.platform == "win32" else ("pandaai-cli",)
    for directory in cli_candidates():
        for name in names:
            candidate = directory / name
            if candidate.is_file():
                os.environ["PATH"] = str(directory) + os.pathsep + os.environ.get("PATH", "")
                return str(candidate)
    return None


def install_cli() -> bool:
    if expose_cli():
        print("pandaai-cli is already installed")
        return True

    installer = shutil.which("uv") or shutil.which("pipx")
    if installer is None:
        print("pandaai-cli is missing and neither uv nor pipx is installed.", file=sys.stderr)
        print("Install uv first, then rerun this command:", file=sys.stderr)
        if sys.platform == "win32":
            print('powershell -c "irm https://astral.sh/uv/install.ps1 | iex"', file=sys.stderr)
        else:
            print("curl -LsSf https://astral.sh/uv/install.sh | sh", file=sys.stderr)
        print("uv tool install pandaai-cli", file=sys.stderr)
        return False

    if Path(installer).name == "uv":
        command = [installer, "tool", "install", "pandaai-cli"]
    else:
        command = [installer, "install", "pandaai-cli"]
    if run(command).returncode != 0:
        return False
    return bool(expose_cli())


def account_is_ready() -> bool:
    try:
        result = subprocess.run(
            ["pandaai-cli", "--json", "balance"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=90,
        )
        payload = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return False
    return bool(payload.get("success"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--login-if-needed",
        action="store_true",
        help="run interactive `pandaai-cli login` when the account is not authenticated",
    )
    args = parser.parse_args()

    if sys.version_info < (3, 10):
        print("Python 3.10 or newer is required.", file=sys.stderr)
        return 2
    if not install_cli():
        return 2

    bootstrap = run([sys.executable, str(ENTRYPOINT), "bootstrap"])
    if bootstrap.returncode != 0 and not args.login_if_needed:
        return bootstrap.returncode

    if account_is_ready():
        print("PandaAI account is ready. No factor run was started.")
        return 0

    if not args.login_if_needed:
        print("PandaAI is not logged in. Run `pandaai-cli login`, or rerun with --login-if-needed.")
        return 1

    print("Starting interactive PandaAI login. Credentials stay on this computer.")
    login = run(["pandaai-cli", "login"])
    if login.returncode != 0:
        return login.returncode

    final_check = run([sys.executable, str(ENTRYPOINT), "bootstrap"])
    if final_check.returncode == 0 and account_is_ready():
        print("PandaAI account is ready. No factor run was started.")
        return 0
    return final_check.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
