#!/usr/bin/env python3
"""
clco-show setup: Install clco-show commands into ~/.claude/commands/.

Usage:
    python3 setup_clco_show.py [--force]
"""

import argparse
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
    "show.md",
    "show.py",
]
PACKAGE_FILES = [
    "__init__.py",
    "renderer.py",
    "style.css",
]
PACKAGE_DIR = "clco_show"


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


# ------------------------------------------------------------------ #
# Main                                                                  #
# ------------------------------------------------------------------ #

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install clco-show commands into ~/.claude/commands/"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files without prompting",
    )
    args = parser.parse_args()

    print("clco-show setup")
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

    # ---- Step 2: Copy clco_show package ----------------------------
    print_step("Installing clco_show package to ~/.claude/commands/clco_show/")
    src_pkg = SRC_COMMANDS_DIR / PACKAGE_DIR
    if src_pkg.exists():
        copy_package(src_pkg, DEST_DIR / PACKAGE_DIR, args.force)
    else:
        print_warn(f"Package directory not found: {src_pkg}")
        sys.exit(1)

    # ---- Done -------------------------------------------------------
    print("\n" + "=" * 40)
    print("Setup complete!")
    print()
    print("Usage:")
    print("  /show                  -- generate slides from conversation context")
    print("  /show notes.md         -- generate slides from a markdown file")
    print("  /show data.json        -- render an existing slide JSON file")
    print("  /show data.json --open -- render and open in browser")
    print()
    print("Optional PDF export (requires Playwright):")
    print("  pip install playwright && playwright install chromium")
    print("  /show data.json --pdf")


if __name__ == "__main__":
    main()
