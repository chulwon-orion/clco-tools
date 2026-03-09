#!/usr/bin/env python3
"""
clco-wiki push: Upload a local Markdown file to Atlassian Confluence.

Usage:
    python3 wiki_push.py <file.md> [--space SPACE] [--parent-id ID] [--title "Title"]

The script reads Confluence metadata from HTML-comment frontmatter in the MD file:
    <!-- confluence-page-id: 12345 -->
    <!-- confluence-space: MYSPACE -->
    <!-- confluence-title: My Page Title -->

- If confluence-page-id is present  → update existing page
- If not                             → create new page, write frontmatter back
"""

import argparse
import os
import re
import sys
from pathlib import Path

# Allow importing clco_wiki package from the same directory
sys.path.insert(0, str(Path(__file__).parent))
from clco_wiki.confluence_api import ConfluenceClient, ConfluenceError
from clco_wiki.md_converter import md_to_wiki


# ------------------------------------------------------------------ #
# Frontmatter helpers                                                   #
# ------------------------------------------------------------------ #

_FRONTMATTER_KEYS = ("confluence-page-id", "confluence-space", "confluence-title", "confluence-url")
_FM_PATTERN = re.compile(r"<!--\s*(confluence-[\w-]+):\s*(.*?)\s*-->")


def parse_frontmatter(text: str) -> dict:
    """Extract confluence-* HTML comment metadata from the top of the file."""
    meta = {}
    for line in text.splitlines():
        m = _FM_PATTERN.match(line.strip())
        if m:
            meta[m.group(1)] = m.group(2)
        elif line.strip() and not line.strip().startswith("<!--"):
            break  # stop at first non-comment, non-empty line
    return meta


def strip_frontmatter(text: str) -> str:
    """Remove confluence-* HTML comment lines from the beginning of the file."""
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if _FM_PATTERN.match(stripped) or stripped == "":
            i += 1
        else:
            break
    return "".join(lines[i:])


def write_frontmatter(file_path: Path, meta: dict, body: str) -> None:
    """Write frontmatter + body back to the file."""
    fm_lines = [f"<!-- {k}: {v} -->" for k, v in meta.items() if v]
    content = "\n".join(fm_lines) + "\n\n" + body.lstrip("\n")
    file_path.write_text(content, encoding="utf-8")


# ------------------------------------------------------------------ #
# Config                                                                #
# ------------------------------------------------------------------ #

def load_env() -> dict:
    """Load .env.clcowiki from cwd or home directory."""
    env = {}
    for candidate in (Path.cwd() / ".env.clcowiki", Path.home() / ".env.clcowiki"):
        if candidate.exists():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
            break
    return env


# ------------------------------------------------------------------ #
# Main                                                                  #
# ------------------------------------------------------------------ #

def main() -> None:
    parser = argparse.ArgumentParser(description="Push a Markdown file to Confluence.")
    parser.add_argument("file", help="Path to the .md file to push")
    parser.add_argument("--space", help="Confluence space key (overrides env/frontmatter)")
    parser.add_argument("--parent-id", dest="parent_id", help="Parent page ID")
    parser.add_argument("--title", help="Page title (overrides frontmatter)")
    args = parser.parse_args()

    # ---- Load config --------------------------------------------------
    env = load_env()

    base_url = env.get("CONFLUENCE_BASE_URL", "")
    username = env.get("CONFLUENCE_USERNAME", "")
    api_token = env.get("CONFLUENCE_API_TOKEN", "")

    if not base_url or not username or not api_token:
        missing = [k for k, v in [
            ("CONFLUENCE_BASE_URL", base_url),
            ("CONFLUENCE_USERNAME", username),
            ("CONFLUENCE_API_TOKEN", api_token),
        ] if not v]
        print(f"ERROR: Missing required config: {', '.join(missing)}", file=sys.stderr)
        print("Set them in .env.clcowiki in the current directory or ~/.env.clcowiki", file=sys.stderr)
        sys.exit(1)

    # ---- Read MD file -------------------------------------------------
    md_path = Path(args.file)
    if not md_path.exists():
        print(f"ERROR: File not found: {md_path}", file=sys.stderr)
        sys.exit(1)

    text = md_path.read_text(encoding="utf-8")
    meta = parse_frontmatter(text)
    body = strip_frontmatter(text)

    # ---- Resolve page title ------------------------------------------
    title = (
        args.title
        or meta.get("confluence-title")
        or _infer_title(body)
        or md_path.stem
    )

    # ---- Resolve space key -------------------------------------------
    space_key = (
        args.space
        or meta.get("confluence-space")
        or env.get("CONFLUENCE_SPACE_KEY", "")
    )
    if not space_key:
        print("ERROR: Confluence space key required. Use --space or set CONFLUENCE_SPACE_KEY.", file=sys.stderr)
        sys.exit(1)

    # ---- Resolve parent page -----------------------------------------
    # Default prevents pages from being created at the space root.
    DEFAULT_PARENT_PAGE_ID = "922814104"
    parent_id = args.parent_id or env.get("CONFLUENCE_PARENT_PAGE_ID", "") or DEFAULT_PARENT_PAGE_ID

    # ---- Convert MD → Wiki Markup ------------------------------------
    wiki_content = md_to_wiki(body)

    # ---- Push to Confluence ------------------------------------------
    client = ConfluenceClient(base_url, username, api_token)
    page_id = meta.get("confluence-page-id", "")

    try:
        if page_id:
            print(f"Updating Confluence page {page_id} …")
            result = client.update_page(page_id, title, wiki_content)
            action = "Updated"
        else:
            print(f"Creating new Confluence page in space {space_key} …")
            result = client.create_page(space_key, title, wiki_content, parent_id)
            action = "Created"
    except ConfluenceError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # ---- Write frontmatter back to file ------------------------------
    new_meta = {
        "confluence-page-id": result["page_id"],
        "confluence-space": result["space_key"],
        "confluence-title": result["title"],
        "confluence-url": result["page_url"],
    }
    write_frontmatter(md_path, new_meta, body)

    print(f"{action}: {result['page_url']}")


def _infer_title(body: str) -> str:
    """Extract the first H1 heading from the body, if present."""
    for line in body.splitlines():
        m = re.match(r"^#\s+(.+)", line)
        if m:
            return m.group(1).strip()
    return ""


if __name__ == "__main__":
    main()
