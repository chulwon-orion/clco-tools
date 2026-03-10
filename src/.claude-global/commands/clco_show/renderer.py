"""
clco-show renderer: generate a self-contained HTML slideshow from structured data.

Input schema (dict):
    {
      "title": "Presentation Title",
      "slides": [
        {
          "title": "Slide Title",
          "content": [
            { "type": "text",  "value": "Plain text" },
            { "type": "code",  "language": "python", "value": "print('hi')" },
            { "type": "table", "headers": ["A", "B"], "rows": [["1", "2"]] },
            { "type": "list",  "items": ["Item 1", "Item 2"] },
            { "type": "badge", "label": "Status", "value": "OK", "style": "good" }
          ]
        }
      ]
    }

Badge styles: "good" (green), "mid" (yellow), "low" (red), "info" (blue)

Style is loaded from style.css in the same directory and inlined into the HTML.
"""

from html import escape
from pathlib import Path


# ── HTML template ─────────────────────────────────────────────────────────
# CSS is injected via __CLCO_STYLE__ placeholder (loaded from style.css).
# Using a named placeholder avoids {{ }} escaping conflicts with .format().

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
__CLCO_STYLE__
</style>
</head>
<body>

<header>
  <h1>{title}</h1>
  <div class="slide-counter" id="counter">1 / {total}</div>
</header>

<nav id="nav">
{nav_buttons}
</nav>

<main>
{slides}
</main>

<footer>&#8592; &#8594; arrow keys to navigate</footer>

<script>
  const slides = document.querySelectorAll('.slide');
  const navBtns = document.querySelectorAll('#nav button');
  const counter = document.getElementById('counter');
  let current = 0;

  function goTo(idx) {{
    if (idx < 0 || idx >= slides.length) return;
    slides[current].classList.remove('active');
    navBtns[current].classList.remove('active');
    current = idx;
    slides[current].classList.add('active');
    navBtns[current].classList.add('active');
    counter.textContent = (current + 1) + ' / ' + slides.length;
    navBtns[current].scrollIntoView({{ behavior: 'smooth', block: 'nearest', inline: 'nearest' }});
  }}

  document.addEventListener('keydown', e => {{
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') goTo(current + 1);
    if (e.key === 'ArrowLeft'  || e.key === 'ArrowUp')   goTo(current - 1);
  }});

  navBtns.forEach((btn, i) => btn.addEventListener('click', () => goTo(i)));

  slides[0].classList.add('active');
  navBtns[0].classList.add('active');
</script>
</body>
</html>
"""

_CSS_FILE = Path(__file__).parent / "style.css"


def _load_css() -> str:
    """Load style.css from the package directory. Falls back to empty string if missing."""
    if _CSS_FILE.exists():
        return _CSS_FILE.read_text(encoding="utf-8")
    return ""


# ── Block renderers ────────────────────────────────────────────────────────

def _block_text(block: dict) -> str:
    value = escape(block.get("value", ""))
    return f'<div class="block-text">{value}</div>'


def _block_code(block: dict) -> str:
    lang = escape(block.get("language", ""))
    value = escape(block.get("value", ""))
    lang_label = f'<div class="code-lang">{lang}</div>' if lang else ""
    return f'<div class="block-code">{lang_label}<pre>{value}</pre></div>'


def _block_table(block: dict) -> str:
    headers = block.get("headers", [])
    rows = block.get("rows", [])
    th_cells = "".join(f"<th>{escape(str(h))}</th>" for h in headers)
    thead = f"<thead><tr>{th_cells}</tr></thead>" if th_cells else ""
    tr_rows = []
    for row in rows:
        td_cells = "".join(f"<td>{escape(str(c))}</td>" for c in row)
        tr_rows.append(f"<tr>{td_cells}</tr>")
    tbody = f"<tbody>{''.join(tr_rows)}</tbody>"
    return f'<div class="block-table"><table>{thead}{tbody}</table></div>'


def _block_list(block: dict) -> str:
    items = block.get("items", [])
    li_items = "".join(f"<li>{escape(str(item))}</li>" for item in items)
    return f'<ul class="block-list">{li_items}</ul>'


def _block_badge(block: dict) -> str:
    label = escape(block.get("label", ""))
    value = escape(block.get("value", ""))
    style = block.get("style", "info")
    if style not in ("good", "mid", "low", "info"):
        style = "info"
    label_html = f'<span class="badge-label">{label}:</span> ' if label else ""
    return (
        f'<div class="block-badges">'
        f'<span class="badge {style}">{label_html}{value}</span>'
        f'</div>'
    )


_BLOCK_RENDERERS = {
    "text":  _block_text,
    "code":  _block_code,
    "table": _block_table,
    "list":  _block_list,
    "badge": _block_badge,
}


def _render_block(block: dict) -> str:
    t = block.get("type", "text")
    renderer = _BLOCK_RENDERERS.get(t)
    if renderer:
        return renderer(block)
    return f'<div class="block-text" style="color:#ef4444">(unknown block type: {escape(t)})</div>'


# ── Slide renderer ─────────────────────────────────────────────────────────

def _render_slide(slide: dict, idx: int, total: int) -> str:
    title = escape(slide.get("title", f"Slide {idx + 1}"))
    content = slide.get("content", [])
    blocks_html = "\n    ".join(_render_block(b) for b in content)
    return (
        f'<div class="slide" id="slide-{idx}">\n'
        f'  <div class="slide-header">\n'
        f'    <span class="slide-num">{idx + 1} / {total}</span>\n'
        f'    <h2 class="slide-title">{title}</h2>\n'
        f'  </div>\n'
        f'  <div class="slide-body">\n'
        f'    {blocks_html}\n'
        f'  </div>\n'
        f'</div>'
    )


def _render_nav_button(slide: dict, idx: int) -> str:
    title = slide.get("title", f"Slide {idx + 1}")
    display = title if len(title) <= 30 else title[:28] + "..."
    return f'  <button data-idx="{idx}">{escape(display)}</button>'


# ── Public API ─────────────────────────────────────────────────────────────

def render_html(data: dict) -> str:
    """Render a slideshow data dict to a self-contained HTML string."""
    title = data.get("title", "Slideshow")
    slides = data.get("slides", [])
    total = len(slides)

    if total == 0:
        slides = [{"title": "Empty", "content": [{"type": "text", "value": "No slides provided."}]}]
        total = 1

    nav_buttons = "\n".join(_render_nav_button(s, i) for i, s in enumerate(slides))
    slides_html = "\n\n".join(_render_slide(s, i, total) for i, s in enumerate(slides))

    css = _load_css()
    html = _HTML_TEMPLATE.format(
        title=escape(title),
        total=total,
        nav_buttons=nav_buttons,
        slides=slides_html,
    )
    return html.replace("__CLCO_STYLE__", css)
