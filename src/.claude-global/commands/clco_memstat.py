#!/usr/bin/env python3
"""
clco-memstat: Analyze a project's MEMORY.md health.

Usage:
    python3 clco_memstat.py [project_dir]

If project_dir is omitted, uses the current working directory.
"""

import os
import re
import sys
from pathlib import Path


# ------------------------------------------------------------------ #
# Memory path encoding                                                 #
# ------------------------------------------------------------------ #

def cwd_to_project_key(cwd: str) -> str:
    """Convert a filesystem path to Claude's project key encoding.

    Algorithm (verified against actual Claude paths):
      - Replace ':' with '-'
      - Replace '\\' or '/' with '-'

    Example: c:\\works\\AI\\clco-tools -> c--works-AI-clco-tools
    """
    key = cwd.replace(":", "-").replace("\\", "-").replace("/", "-")
    # Strip leading/trailing dashes that may arise from drive root
    key = key.strip("-")
    # Claude lowercases the drive letter on Windows (C -> c)
    if len(key) >= 1 and key[0].isupper() and (len(key) == 1 or key[1] == "-"):
        key = key[0].lower() + key[1:]
    return key


def find_memory_file(project_dir: str) -> Path | None:
    """Locate MEMORY.md for the given project directory."""
    claude_projects = Path.home() / ".claude" / "projects"
    if not claude_projects.exists():
        return None

    key = cwd_to_project_key(project_dir)
    candidate = claude_projects / key / "memory" / "MEMORY.md"
    if candidate.exists():
        return candidate

    # Fallback: search for a key that ends with the encoded basename
    encoded_base = cwd_to_project_key(os.path.basename(project_dir))
    for d in claude_projects.iterdir():
        if d.is_dir() and d.name.endswith(encoded_base):
            mem = d / "memory" / "MEMORY.md"
            if mem.exists():
                return mem

    return None


# ------------------------------------------------------------------ #
# Line count status                                                    #
# ------------------------------------------------------------------ #

def line_status(n: int) -> str:
    if n >= 200:
        return f"{n} [CRITICAL] - at or over truncation limit! Run /clco-mempack now."
    if n >= 180:
        return f"{n} [ALERT] - compression recommended (/clco-mempack)"
    if n >= 150:
        return f"{n} [WARN] - approaching limit (200)"
    return f"{n} [OK]"


# ------------------------------------------------------------------ #
# Referenced .md files                                                 #
# ------------------------------------------------------------------ #

def find_referenced_mds(content: str, memory_dir: Path) -> list[tuple[str, Path]]:
    """Return list of (link_target, resolved_path) for .md references."""
    pattern = re.compile(r'\[.*?\]\(([^)]+\.md)\)')
    seen: dict[str, Path] = {}
    for match in pattern.finditer(content):
        target = match.group(1)
        if target not in seen:
            resolved = (memory_dir / target).resolve()
            seen[target] = resolved
    return list(seen.items())


# ------------------------------------------------------------------ #
# Main                                                                 #
# ------------------------------------------------------------------ #

def main() -> None:
    project_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    project_dir = str(Path(project_dir).resolve())

    memory_file = find_memory_file(project_dir)

    if memory_file is None:
        key = cwd_to_project_key(project_dir)
        expected = Path.home() / ".claude" / "projects" / key / "memory" / "MEMORY.md"
        print(f"MEMORY.md not found for: {project_dir}")
        print(f"  Expected path: {expected}")
        print("  (No memory has been saved for this project yet, or the project key does not match.)")
        sys.exit(0)

    content = memory_file.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    n = len(lines)
    size_kb = memory_file.stat().st_size / 1024

    # Shorten home path for display
    try:
        display_path = "~/.claude/projects" + str(memory_file).split(".claude" + os.sep + "projects")[1]
        display_path = display_path.replace("\\", "/")
    except Exception:
        display_path = str(memory_file)

    print(f"MEMORY.md status: {display_path}")
    print(f"  Lines  : {line_status(n)}")
    print(f"  Size   : {size_kb:.1f} KB")

    # Referenced .md files
    refs = find_referenced_mds(content, memory_file.parent)
    if refs:
        print()
        print("Referenced .md files:")
        for target, path in refs:
            if path.exists():
                ref_lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
                print(f"  [EXISTS]  {target} ({ref_lines} lines)")
            else:
                print(f"  [MISSING] {target}")
    else:
        print()
        print("Referenced .md files: (none)")


if __name__ == "__main__":
    main()
