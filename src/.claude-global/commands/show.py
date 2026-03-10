#!/usr/bin/env python3
"""
clco-show: Generate a self-contained HTML slideshow from a JSON data file.

Usage:
    python3 show.py <input.json> [--output out.html] [--pdf] [--open]

Input JSON format:
    {
      "title": "My Slides",
      "slides": [
        {
          "title": "Slide Title",
          "content": [
            { "type": "text",  "value": "Some text" },
            { "type": "code",  "language": "python", "value": "print('hi')" },
            { "type": "table", "headers": ["A", "B"], "rows": [["1", "2"]] },
            { "type": "list",  "items": ["Item 1", "Item 2"] },
            { "type": "badge", "label": "Status", "value": "OK", "style": "good" }
          ]
        }
      ]
    }

Badge styles: good (green), mid (yellow), low (red), info (blue)
"""

import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path

# Allow importing clco_show package from the same directory
sys.path.insert(0, str(Path(__file__).parent))
from clco_show.renderer import render_html


# ------------------------------------------------------------------ #
# PDF export (optional Playwright)                                     #
# ------------------------------------------------------------------ #

def export_pdf(html_path: Path, pdf_path: Path) -> bool:
    """Export HTML to PDF using Playwright. Returns True on success."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
            page.pdf(
                path=str(pdf_path),
                format="A4",
                print_background=True,
            )
            browser.close()
        return True
    except Exception as e:
        print(f"[ERROR] PDF export failed: {e}", file=sys.stderr)
        return False


# ------------------------------------------------------------------ #
# Main                                                                  #
# ------------------------------------------------------------------ #

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a self-contained HTML slideshow from JSON."
    )
    parser.add_argument(
        "input",
        help="Path to input JSON file",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output HTML path (default: <input_stem>.html next to input file)",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        default=False,
        help="Also export PDF (requires Playwright: pip install playwright)",
    )
    parser.add_argument(
        "--open",
        dest="open_browser",
        action="store_true",
        default=False,
        help="Open the HTML in the default browser after generating",
    )
    args = parser.parse_args()

    # ---- Load input JSON -----------------------------------------------
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in {input_path}: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, dict):
        print("[ERROR] JSON root must be an object with 'title' and 'slides' keys.", file=sys.stderr)
        sys.exit(1)

    # ---- Determine output paths ----------------------------------------
    if args.output:
        html_path = Path(args.output)
    else:
        html_path = input_path.parent / (input_path.stem + ".html")

    # ---- Render HTML ---------------------------------------------------
    html = render_html(data)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")

    title = data.get("title", "Slideshow")
    slide_count = len(data.get("slides", []))
    print(f"[OK] Generated: {html_path}  ({slide_count} slides, title: {title!r})")

    # ---- PDF export (optional) -----------------------------------------
    if args.pdf:
        pdf_path = html_path.with_suffix(".pdf")
        print(f"-> Exporting PDF: {pdf_path}")
        ok = export_pdf(html_path, pdf_path)
        if ok:
            print(f"[OK] PDF: {pdf_path}")
        else:
            print(
                "[WARN] PDF export skipped - Playwright not installed.\n"
                "       Install with: pip install playwright && playwright install chromium"
            )

    # ---- Open in browser (optional) ------------------------------------
    if args.open_browser:
        webbrowser.open(html_path.resolve().as_uri())


if __name__ == "__main__":
    main()
