#!/usr/bin/env python3
"""
Global install helper for clco-tools.

Reads .env.clco from the repo root, then:
  1. Installs clco-notify globally into ~/.claude/
  2. Writes all SLACK_* values into ~/.claude/.env.clco
  3. Installs clco-wiki globally into ~/.claude/commands/
     (runs setup from ~/.claude/ so .env.clco lands at ~/.claude/.env.clco)
  4. Installs clco-show globally into ~/.claude/commands/
  5. Installs clco-mem globally into ~/.claude/commands/

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
    print("1/3  clco-notify - global install")
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
    notify_env = Path.home() / ".claude" / ".env.clco"
    print(f"\n-> Writing config values -> {notify_env}")
    for key in NOTIFY_KEYS:
        value = cfg.get(key, "")
        if value:
            set_env_value(notify_env, key, value)
            masked = "***" if "TOKEN" in key or "SECRET" in key else value
            print(f"  [OK] {key} = {masked}")


def install_wiki(cfg: dict, python: str) -> None:
    print("\n" + "=" * 50)
    print("2/3  clco-wiki - global install")
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

    # Run from ~/.claude/ so .env.clco is created at ~/.claude/.env.clco
    # PYTHONUTF8=1 prevents UnicodeEncodeError from Unicode chars in setup_clco_wiki.py output
    claude_dir = Path.home() / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    utf8_env = {**os.environ, "PYTHONUTF8": "1"}
    run(cmd, cwd=str(claude_dir), env=utf8_env)


def install_show(cfg: dict, python: str) -> None:
    print("\n" + "=" * 50)
    print("3/5  clco-show - global install")
    print("=" * 50)

    setup = REPO_ROOT / "src" / "clco_show" / "setup_clco_show.py"
    if not setup.exists():
        print(f"[ERROR] Not found: {setup}")
        sys.exit(1)

    utf8_env = {**os.environ, "PYTHONUTF8": "1"}
    run([python, str(setup)], env=utf8_env)


def install_mem(cfg: dict, python: str) -> None:
    print("\n" + "=" * 50)
    print("4/5  clco-mem - global install")
    print("=" * 50)

    setup = REPO_ROOT / "src" / "clco_mem" / "setup_clco_mem.py"
    if not setup.exists():
        print(f"[ERROR] Not found: {setup}")
        sys.exit(1)

    utf8_env = {**os.environ, "PYTHONUTF8": "1"}
    run([python, str(setup)], env=utf8_env)


def install_knowledge() -> None:
    import shutil

    print("\n" + "=" * 50)
    print("5/5  knowledge - global install")
    print("=" * 50)

    dest = Path.home() / ".claude" / "knowledge"
    dest.mkdir(parents=True, exist_ok=True)

    # Source: workspace-meta/conventions/ (preferred - single source of truth)
    workspace_conventions = REPO_ROOT.parent / "workspace-meta" / "conventions"
    # Fallback: src/.claude-global/knowledge/ (local copies for standalone install)
    local_knowledge = REPO_ROOT / "src" / ".claude-global" / "knowledge"

    if workspace_conventions.exists():
        src_dir = workspace_conventions
        print(f"Source: {src_dir} (workspace-meta)")
    elif local_knowledge.exists():
        src_dir = local_knowledge
        print(f"Source: {src_dir} (local fallback)")
    else:
        print("[SKIP] No knowledge source found. Skipping.")
        print(f"  Expected: {workspace_conventions}")
        return

    count = 0
    for md_file in sorted(src_dir.glob("*.md")):
        if md_file.name == "README.md":
            continue
        shutil.copy2(md_file, dest / md_file.name)
        print(f"  [OK] {md_file.name} -> {dest / md_file.name}")
        count += 1

    if count == 0:
        print("[WARN] No .md files found in source directory.")
    else:
        print(f"\n-> {count} knowledge file(s) installed to {dest}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Install clco-notify, clco-wiki, clco-show, clco-mem, and knowledge globally")
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
    install_show(cfg, python)
    install_mem(cfg, python)
    install_knowledge()

    print("\n" + "=" * 50)
    print("All done!")
    print("=" * 50)
    print(f"  shared env file : {Path.home() / '.claude' / '.env.clco'}")
    print(f"  knowledge dir   : {Path.home() / '.claude' / 'knowledge'}")
    print()
    print("Reload Claude Code (or start a new session) to activate.")


if __name__ == "__main__":
    main()
