# clco-show

A Claude Code skill that generates self-contained, arrow-key navigable HTML
slideshows from structured JSON data.

## Setup

```bash
python3 src/clco_show/setup_clco_show.py
# or via the global installer:
python3 dev/install_global.py
```

## Usage

```
/show                        # Claude builds slides from conversation context
/show notes.md               # Claude reads file and generates slides
/show data.json              # Render existing slide JSON directly
/show data.json --open       # Render and open in browser
/show data.json --pdf        # Also export PDF (requires Playwright)
/show data.json --output report.html
```

## Input JSON Format

```json
{
  "title": "Presentation Title",
  "slides": [
    {
      "title": "Slide Title",
      "content": [
        { "type": "text",  "value": "Plain text (supports newlines)" },
        { "type": "code",  "language": "python", "value": "print('hello')" },
        { "type": "table", "headers": ["Col A", "Col B"], "rows": [["v1", "v2"]] },
        { "type": "list",  "items": ["Item 1", "Item 2"] },
        { "type": "badge", "label": "Status", "value": "OK", "style": "good" }
      ]
    }
  ]
}
```

## Badge Styles

| style  | color  |
|--------|--------|
| `good` | green  |
| `mid`  | yellow |
| `low`  | red    |
| `info` | blue   |

## PDF Export

Requires Playwright (optional):

```bash
pip install playwright
playwright install chromium
```

## Architecture

Three-layer pattern:

| Layer | File | Role |
|---|---|---|
| 1 (Knowledge) | — | (no team config needed) |
| 2 (Skill Prompt) | `show.md` | Instructions for Claude |
| 3 (Execution) | `show.py` + `clco_show/renderer.py` | HTML generation |

- `renderer.py` — pure Python stdlib, no external dependencies; loads `style.css` and inlines it into output HTML
- `style.css` — all visual styling; edit here to change fonts, colors, layout without touching Python
- `show.py` — argparse CLI; Playwright for PDF is optional (try/except)
