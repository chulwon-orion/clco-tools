#!/usr/bin/env python3
"""
clco-mem setup: Install clco-memstat and clco-mempack commands into ~/.claude/commands/.

Usage:
    python3 setup_clco_mem.py [--force]
"""

import argparse
import shutil
import sys
from pathlib import Path


# ------------------------------------------------------------------ #
# Paths                                                                #
# ------------------------------------------------------------------ #

SCRIPT_DIR = Path(__file__).parent
SRC_COMMANDS_DIR = SCRIPT_DIR.parent / ".claude-global" / "commands"

DEST_DIR = Path.home() / ".claude" / "commands"

FILES_TO_COPY = [
    "clco-memstat.md",
    "clco_memstat.py",
    "clco-mempack.md",
]


# ------------------------------------------------------------------ #
# Helpers                                                              #
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


# ------------------------------------------------------------------ #
# Main                                                                 #
# ------------------------------------------------------------------ #

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install clco-mem commands into ~/.claude/commands/"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files without prompting",
    )
    args = parser.parse_args()

    print("clco-mem setup")
    print("=" * 40)

    print_step("Installing command files to ~/.claude/commands/")
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    missing = False
    for fname in FILES_TO_COPY:
        src = SRC_COMMANDS_DIR / fname
        if not src.exists():
            print_warn(f"Source file not found: {src}")
            missing = True
            continue
        copy_file(src, DEST_DIR / fname, args.force)

    if missing:
        sys.exit(1)

    print("\n" + "=" * 40)
    print("Setup complete!")
    print()
    print("Commands installed:")
    print("  /clco-memstat   -- analyze MEMORY.md health (line count, warnings, refs)")
    print("  /clco-mempack   -- compress MEMORY.md by archiving old sections")
    print()
    print("Tip: Run /clco-memstat periodically, or add it to your session startup.")
    print("     Run /clco-mempack when status shows [WARN] or higher.")


if __name__ == "__main__":
    main()
