#!/usr/bin/env python3
"""
Global install helper for clco-tools.

Reads .env.clco from the repo root, then:
  1. Installs clco-notify globally into ~/.claude/
  2. Writes all SLACK_* values into ~/.claude/.env.clconotify
  3. Installs clco-wiki globally into ~/.claude/commands/
     (runs setup from ~/ so .env.clcowiki lands at ~/.env.clcowiki)

Usage:
    python dev/install_global.py
    python dev/install_global.py --env-file /path/to/.env.clco
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


# ---------------------------------------------------------------------------
# .env parser
# ---------------------------------------------------------------------------

def parse_env(path: Path) -> dict:
    """Parse KEY=VALUE env file. Ignores comments and blank lines. Handles = in values."""
    cfg = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key:
                cfg[key] = value
    return cfg


# ---------------------------------------------------------------------------
# Env file writer
# ---------------------------------------------------------------------------

def set_env_value(env_path: Path, key: str, value: str) -> None:
    """Write or update key=value in an env file (appends if key not found)."""
    if not env_path.exists():
        with open(env_path, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
        return

    lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Match active lines (not commented-out)
        if stripped.startswith(f"{key}=") and not stripped.startswith("#"):
            lines[i] = f"{key}={value}\n"
            env_path.write_text("".join(lines), encoding="utf-8")
            return

    with open(env_path, "a", encoding="utf-8") as f:
        f.write(f"{key}={value}\n")


# ---------------------------------------------------------------------------
# Subprocess helper
# ---------------------------------------------------------------------------

def run(cmd: list, **kwargs) -> None:
    display = " ".join(str(c) for c in cmd)
    print(f"\n>>> {display}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"[ERROR] Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# Install steps
# ---------------------------------------------------------------------------

NOTIFY_KEYS = [
    "SLACK_BOT_TOKEN",
    "SLACK_NOTIFY_USER_ID",
    "SLACK_NOTIFY_USER_EMAIL",
    "SLACK_NOTIFY_CHANNEL",
    "SLACK_NOTIFY_PROJECT_NAME",
    "SLACK_NOTIFY_DELAY_SECONDS",
    "SLACK_NOTIFY_LAST_PROMPT_MAXLEN",
    "SLACK_NOTIFY_EVENT_MESSAGE_MAXLEN",
]


def install_notify(cfg: dict, python: str) -> None:
    print("\n" + "=" * 50)
    print("1/2  clco-notify - global install")
    print("=" * 50)

    setup = REPO_ROOT / "src" / "clco_notify" / "setup_clco_notify.py"
    if not setup.exists():
        print(f"[ERROR] Not found: {setup}")
        sys.exit(1)

    cmd = [python, str(setup)]
    if cfg.get("SLACK_NOTIFY_USER_ID"):
        cmd += ["--user-id", cfg["SLACK_NOTIFY_USER_ID"]]
    elif cfg.get("SLACK_NOTIFY_USER_EMAIL"):
        cmd += ["--email", cfg["SLACK_NOTIFY_USER_EMAIL"]]

    run(cmd)

    # Write SLACK_* values into the installed env file
    notify_env = Path.home() / ".claude" / ".env.clconotify"
    print(f"\n-> Writing config values -> {notify_env}")
    for key in NOTIFY_KEYS:
        value = cfg.get(key, "")
        if value:
            set_env_value(notify_env, key, value)
            masked = "***" if "TOKEN" in key or "SECRET" in key else value
            print(f"  [OK] {key} = {masked}")


def install_wiki(cfg: dict, python: str) -> None:
    print("\n" + "=" * 50)
    print("2/2  clco-wiki - global install")
    print("=" * 50)

    setup = REPO_ROOT / "src" / "clco_wiki" / "setup_clco_wiki.py"
    if not setup.exists():
        print(f"[ERROR] Not found: {setup}")
        sys.exit(1)

    cmd = [python, str(setup)]
    if cfg.get("CONFLUENCE_BASE_URL"):
        cmd += ["--base-url", cfg["CONFLUENCE_BASE_URL"]]
    if cfg.get("CONFLUENCE_USERNAME"):
        cmd += ["--username", cfg["CONFLUENCE_USERNAME"]]
    if cfg.get("CONFLUENCE_API_TOKEN"):
        cmd += ["--api-token", cfg["CONFLUENCE_API_TOKEN"]]
    if cfg.get("CONFLUENCE_SPACE_KEY"):
        cmd += ["--space-key", cfg["CONFLUENCE_SPACE_KEY"]]
    if cfg.get("CONFLUENCE_PARENT_PAGE_ID"):
        cmd += ["--parent-id", cfg["CONFLUENCE_PARENT_PAGE_ID"]]

    # Run from home dir so .env.clcowiki is created at ~/.env.clcowiki
    # PYTHONUTF8=1 prevents UnicodeEncodeError from Unicode chars in setup_clco_wiki.py output
    utf8_env = {**os.environ, "PYTHONUTF8": "1"}
    run(cmd, cwd=str(Path.home()), env=utf8_env)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Install clco-notify and clco-wiki globally")
    parser.add_argument(
        "--env-file",
        default=str(REPO_ROOT / ".env.clco"),
        help="Path to env file (default: <repo>/.env.clco)",
    )
    args = parser.parse_args()

    env_path = Path(args.env_file)
    if not env_path.exists():
        print(f"[ERROR] Env file not found: {env_path}")
        sys.exit(1)

    print(f"Reading config from: {env_path}")
    cfg = parse_env(env_path)

    python = sys.executable

    install_notify(cfg, python)
    install_wiki(cfg, python)

    print("\n" + "=" * 50)
    print("All done!")
    print("=" * 50)
    print(f"  clco-notify env : {Path.home() / '.claude' / '.env.clconotify'}")
    print(f"  clco-wiki env   : {Path.home() / '.env.clcowiki'}")
    print()
    print("Reload Claude Code (or start a new session) to activate.")


if __name__ == "__main__":
    main()
