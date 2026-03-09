#!/usr/bin/env python3
"""
clco-wiki pull: Download an Atlassian Confluence page as a local Markdown file.

Usage:
    python3 wiki_pull.py <page-id-or-url> [--output file.md]

If --output is not given, the file is saved as <page-title>.md in the current directory.
"""

import argparse
import re
import sys
from pathlib import Path

# Allow importing clco_wiki package from the same directory
sys.path.insert(0, str(Path(__file__).parent))
from clco_wiki.confluence_api import ConfluenceClient, ConfluenceError, extract_page_id_from_url
from clco_wiki.md_converter import wiki_to_md


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
# Frontmatter                                                           #
# ------------------------------------------------------------------ #

def build_frontmatter(meta: dict) -> str:
    lines = []
    for key in ("confluence-page-id", "confluence-space", "confluence-title", "confluence-url"):
        val = meta.get(key, "")
        if val:
            lines.append(f"<!-- {key}: {val} -->")
    return "\n".join(lines) + "\n\n" if lines else ""


def safe_filename(title: str) -> str:
    """Convert a page title to a safe filename."""
    safe = re.sub(r'[<>:"/\\|?*]', "-", title)
    safe = re.sub(r"\s+", "_", safe.strip())
    return safe + ".md"


# ------------------------------------------------------------------ #
# Main                                                                  #
# ------------------------------------------------------------------ #

def main() -> None:
    parser = argparse.ArgumentParser(description="Pull a Confluence page to a local Markdown file.")
    parser.add_argument("page", help="Confluence page ID or URL")
    parser.add_argument("--output", "-o", help="Output .md file path (default: <title>.md)")
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

    # ---- Resolve page ID ---------------------------------------------
    try:
        page_id = extract_page_id_from_url(args.page)
    except ConfluenceError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # ---- Fetch page --------------------------------------------------
    client = ConfluenceClient(base_url, username, api_token)
    try:
        page = client.get_page_wiki(page_id)
    except ConfluenceError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # ---- Convert Wiki Markup → MD ------------------------------------
    md_body = wiki_to_md(page["wiki_content"])

    # ---- Build output ------------------------------------------------
    meta = {
        "confluence-page-id": page["page_id"],
        "confluence-space": page["space_key"],
        "confluence-title": page["title"],
        "confluence-url": page["page_url"],
    }
    frontmatter = build_frontmatter(meta)
    output_text = frontmatter + md_body

    # ---- Determine output path ---------------------------------------
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = Path.cwd() / safe_filename(page["title"])

    out_path.write_text(output_text, encoding="utf-8")
    print(f"Saved: {out_path}")
    print(f"Page: {page['page_url']}")


if __name__ == "__main__":
    main()
