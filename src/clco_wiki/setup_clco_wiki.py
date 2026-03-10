#!/usr/bin/env python3
"""
clco-wiki setup: Install clco-wiki commands into ~/.claude/commands/.

Usage:
    python3 setup_clco_wiki.py [options]

Options:
    --base-url URL      Confluence base URL (e.g. https://yourcompany.atlassian.net/wiki)
    --username EMAIL    Atlassian account email
    --api-token TOKEN   Atlassian API token
    --space-key KEY     Default Confluence space key (e.g. MYSPACE)
    --parent-id ID      Default parent page ID (optional)
    --force             Overwrite existing files without prompting
"""

import argparse
import os
import shutil
import sys
from pathlib import Path


# ------------------------------------------------------------------ #
# Paths                                                                 #
# ------------------------------------------------------------------ #

SCRIPT_DIR = Path(__file__).parent
SRC_COMMANDS_DIR = SCRIPT_DIR.parent / ".claude-global" / "commands"

DEST_DIR = Path.home() / ".claude" / "commands"

FILES_TO_COPY = [
    "wiki-push.md",
    "wiki-pull.md",
    "wiki_push.py",
    "wiki_pull.py",
]
PACKAGE_DIR = "clco_wiki"

ENV_EXAMPLE = SCRIPT_DIR.parent / ".env.clco-example"
ENV_DEST_NAME = ".env.clco"


# ------------------------------------------------------------------ #
# Helpers                                                               #
# ------------------------------------------------------------------ #

def print_step(msg: str) -> None:
    print(f"\n-> {msg}")


def print_ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def print_warn(msg: str) -> None:
    print(f"  ! {msg}")


def copy_file(src: Path, dst: Path, force: bool) -> None:
    if dst.exists() and not force:
        print_warn(f"Already exists (skipped): {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print_ok(f"Copied: {dst}")


def copy_package(src_pkg: Path, dst_pkg: Path, force: bool) -> None:
    """Copy an entire package directory, preserving structure."""
    for src_file in src_pkg.rglob("*"):
        if src_file.is_file():
            rel = src_file.relative_to(src_pkg.parent)
            dst_file = dst_pkg.parent / rel
            copy_file(src_file, dst_file, force)


def set_env_value(env_path: Path, key: str, value: str) -> None:
    """Set a key=value in an env file (update if exists, append if not)."""
    if not env_path.exists():
        return
    lines = env_path.read_text(encoding="utf-8").splitlines()
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}=") or line.strip().startswith(f"# {key}="):
            lines[i] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def step_gitignore(project_dir: Path) -> None:
    """Add .env.clco to .gitignore if in a git project."""
    gitignore = project_dir / ".gitignore"
    entry = ".env.clco"
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        if entry in content:
            print_ok(f".gitignore already has {entry}")
            return
        gitignore.write_text(content.rstrip() + f"\n{entry}\n", encoding="utf-8")
        print_ok(f"Added {entry} to .gitignore")
    else:
        print_warn(".gitignore not found - skipped")


# ------------------------------------------------------------------ #
# Main                                                                  #
# ------------------------------------------------------------------ #

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install clco-wiki commands into ~/.claude/commands/"
    )
    parser.add_argument("--base-url", help="Confluence base URL")
    parser.add_argument("--username", help="Atlassian account email")
    parser.add_argument("--api-token", help="Atlassian API token")
    parser.add_argument("--space-key", help="Default Confluence space key")
    parser.add_argument("--parent-id", help="Default parent page ID")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    print("clco-wiki setup")
    print("=" * 40)

    # ---- Step 1: Copy command files to ~/.claude/commands/ ----------
    print_step("Installing command files to ~/.claude/commands/")
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    for fname in FILES_TO_COPY:
        src = SRC_COMMANDS_DIR / fname
        if not src.exists():
            print_warn(f"Source file not found: {src}")
            continue
        copy_file(src, DEST_DIR / fname, args.force)

    # ---- Step 2: Copy clco_wiki package ----------------------------
    print_step("Installing clco_wiki package to ~/.claude/commands/clco_wiki/")
    src_pkg = SRC_COMMANDS_DIR / PACKAGE_DIR
    if src_pkg.exists():
        copy_package(src_pkg, DEST_DIR / PACKAGE_DIR, args.force)
    else:
        print_warn(f"Package directory not found: {src_pkg}")

    # ---- Step 3: Create .env.clco in project directory ----------
    print_step("Creating .env.clco config file")
    project_dir = Path.cwd()
    env_dest = project_dir / ENV_DEST_NAME

    if not env_dest.exists():
        if ENV_EXAMPLE.exists():
            shutil.copy2(ENV_EXAMPLE, env_dest)
            print_ok(f"Created: {env_dest}")
        else:
            # Create minimal config file
            env_dest.write_text(
                "# clco-wiki configuration\n"
                "# Required\n"
                "CONFLUENCE_BASE_URL=\n"
                "CONFLUENCE_USERNAME=\n"
                "CONFLUENCE_API_TOKEN=\n"
                "# Optional\n"
                "CONFLUENCE_SPACE_KEY=\n"
                "CONFLUENCE_PARENT_PAGE_ID=\n"
                "CONFLUENCE_PROJECT_NAME=\n"
                "# See .env.clco-example for clco-notify (Slack) keys\n",
                encoding="utf-8",
            )
            print_ok(f"Created (minimal): {env_dest}")
    else:
        print_ok(f"Already exists: {env_dest}")

    # Apply CLI-provided config values
    if args.base_url:
        set_env_value(env_dest, "CONFLUENCE_BASE_URL", args.base_url)
        print_ok(f"Set CONFLUENCE_BASE_URL = {args.base_url}")
    if args.username:
        set_env_value(env_dest, "CONFLUENCE_USERNAME", args.username)
        print_ok(f"Set CONFLUENCE_USERNAME = {args.username}")
    if args.api_token:
        set_env_value(env_dest, "CONFLUENCE_API_TOKEN", args.api_token)
        print_ok("Set CONFLUENCE_API_TOKEN = ***")
    if args.space_key:
        set_env_value(env_dest, "CONFLUENCE_SPACE_KEY", args.space_key)
        print_ok(f"Set CONFLUENCE_SPACE_KEY = {args.space_key}")
    if args.parent_id:
        set_env_value(env_dest, "CONFLUENCE_PARENT_PAGE_ID", args.parent_id)
        print_ok(f"Set CONFLUENCE_PARENT_PAGE_ID = {args.parent_id}")

    # ---- Step 4: Update .gitignore ----------------------------------
    print_step("Updating .gitignore")
    step_gitignore(project_dir)

    # ---- Done -------------------------------------------------------
    print("\n" + "=" * 40)
    print("Setup complete!")
    print()
    print("Next steps:")
    print(f"  1. Edit {env_dest} and fill in your Confluence (and Slack) credentials")
    print("  2. Reload Claude Code (or start a new session)")
    print("  3. Use /wiki-push <file.md> to push a markdown file to Confluence")
    print("     Use /wiki-pull <page-id> to pull a Confluence page to markdown")
    print()
    print("Atlassian API token: https://id.atlassian.com/manage-profile/security/api-tokens")


if __name__ == "__main__":
    main()
