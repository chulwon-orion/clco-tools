Generate a self-contained HTML slideshow and open it for the user.

Run the following command:
```
python3 ~/.claude/commands/show.py $ARGUMENTS
```

**Behavior by input type:**

- **`.json` file path given** — run the script directly on that file.
- **Other file path given** (`.md`, `.txt`, etc.) — read the file, convert its
  content into a slide JSON structure (see format below), write it as a temp
  `.json` file beside the original, then run the script on that temp file.
- **No arguments** — create a slide JSON structure summarizing the current
  conversation or task context, write it as `show_output.json` in the current
  directory, then run the script on it.

**Flags (append after the file path if needed):**
- `--pdf` — also export a PDF (requires Playwright)
- `--open` — open HTML in browser immediately
- `--output <path>` — set custom output path

**Examples:**
```
/show
/show notes.md
/show data.json
/show data.json --open
/show data.json --pdf --output report.html
```

**JSON format for slide data:**
```json
{
  "title": "Presentation Title",
  "slides": [
    {
      "title": "Slide Title",
      "content": [
        { "type": "text",  "value": "Plain text content (supports newlines)" },
        { "type": "code",  "language": "python", "value": "print('hello')" },
        { "type": "table", "headers": ["Column A", "Column B"], "rows": [["val1", "val2"]] },
        { "type": "list",  "items": ["Item 1", "Item 2", "Item 3"] },
        { "type": "badge", "label": "Status", "value": "Complete", "style": "good" }
      ]
    }
  ]
}
```

Badge `style` values: `"good"` (green), `"mid"` (yellow), `"low"` (red), `"info"` (blue)

After the command completes, report the output HTML file path to the user.
If `--pdf` was requested but Playwright is not installed, report the HTML path
and show the install instructions from the script output.
