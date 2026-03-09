"""
Bidirectional converter between Markdown and Confluence Wiki Markup.

Markdown → Wiki Markup  (used by wiki_push.py)
Wiki Markup → Markdown  (used by wiki_pull.py)

Coverage: headings, bold, italic, inline code, fenced code blocks,
blockquotes, unordered/ordered lists, links, images, horizontal rules,
tables (basic). Complex Confluence macros are passed through as-is on pull.
"""

import re


# ======================================================================
# Markdown  →  Confluence Wiki Markup
# ======================================================================

def md_to_wiki(text: str) -> str:
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # ---- Fenced code block ----------------------------------------
        fence_match = re.match(r"^```(\w*)$", line)
        if fence_match:
            lang = fence_match.group(1)
            code_lines = []
            i += 1
            while i < len(lines) and lines[i] != "```":
                code_lines.append(lines[i])
                i += 1
            code_body = "\n".join(code_lines)
            if lang:
                out.append(f"{{code:language={lang}}}\n{code_body}\n{{code}}")
            else:
                out.append(f"{{code}}\n{code_body}\n{{code}}")
            i += 1
            continue

        # ---- Blockquote (single-line; collapse adjacent lines) ----------
        if line.startswith("> "):
            quote_lines = []
            while i < len(lines) and lines[i].startswith("> "):
                quote_lines.append(lines[i][2:])
                i += 1
            inner = "\n".join(quote_lines)
            out.append(f"{{quote}}\n{inner}\n{{quote}}")
            continue

        # ---- Horizontal rule -------------------------------------------
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", line.strip()):
            out.append("----")
            i += 1
            continue

        # ---- Table row --------------------------------------------------
        if "|" in line and line.strip().startswith("|"):
            # Skip separator rows like |---|---|
            if re.match(r"^\|[\s\-:|]+\|$", line.strip()):
                i += 1
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            # Detect header row: next line is a separator
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            is_header = bool(re.match(r"^\|[\s\-:|]+\|$", next_line.strip()))
            if is_header:
                out.append("|| " + " || ".join(cells) + " ||")
                i += 2  # skip separator
            else:
                out.append("| " + " | ".join(cells) + " |")
                i += 1
            continue

        # ---- Headings ---------------------------------------------------
        heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading_match:
            level = len(heading_match.group(1))
            content = heading_match.group(2)
            out.append(f"h{level}. {_inline_md_to_wiki(content)}")
            i += 1
            continue

        # ---- Unordered list --------------------------------------------
        ul_match = re.match(r"^(\s*)[-*+]\s+(.*)", line)
        if ul_match:
            indent = len(ul_match.group(1)) // 2 + 1
            content = ul_match.group(2)
            out.append("*" * indent + " " + _inline_md_to_wiki(content))
            i += 1
            continue

        # ---- Ordered list ----------------------------------------------
        ol_match = re.match(r"^(\s*)\d+\.\s+(.*)", line)
        if ol_match:
            indent = len(ol_match.group(1)) // 2 + 1
            content = ol_match.group(2)
            out.append("#" * indent + " " + _inline_md_to_wiki(content))
            i += 1
            continue

        # ---- Normal line (apply inline transforms) ---------------------
        out.append(_inline_md_to_wiki(line))
        i += 1

    return "\n".join(out)


def _inline_md_to_wiki(text: str) -> str:
    """Apply inline Markdown → Wiki Markup transformations."""
    # Inline code (must come before bold/italic to avoid mangling backticks)
    text = re.sub(r"`([^`]+)`", r"{{\1}}", text)

    # Bold+italic: ***text*** → *_text_*
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"*_\1_*", text)
    # Bold: **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    text = re.sub(r"__(.+?)__", r"*\1*", text)
    # Italic: *text* or _text_
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"_\1_", text)
    text = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"_\1_", text)

    # Strikethrough: ~~text~~ → -text-
    text = re.sub(r"~~(.+?)~~", r"-\1-", text)

    # Images: ![alt](url) → !url|alt!
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"!\2|\1!", text)

    # Links: [text](url) → [text|url]
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"[\1|\2]", text)

    return text


# ======================================================================
# Confluence Wiki Markup  →  Markdown
# ======================================================================

def wiki_to_md(text: str) -> str:
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # ---- {code...} block -------------------------------------------
        code_start = re.match(r"^\{code(?::language=(\w+))?\}", line, re.IGNORECASE)
        if code_start:
            lang = code_start.group(1) or ""
            code_lines = []
            i += 1
            while i < len(lines) and not re.match(r"^\{code\}", lines[i], re.IGNORECASE):
                code_lines.append(lines[i])
                i += 1
            fence = f"```{lang}"
            out.append(fence)
            out.extend(code_lines)
            out.append("```")
            i += 1
            continue

        # ---- {quote} block ---------------------------------------------
        if re.match(r"^\{quote\}", line, re.IGNORECASE):
            quote_lines = []
            i += 1
            while i < len(lines) and not re.match(r"^\{quote\}", lines[i], re.IGNORECASE):
                quote_lines.append("> " + lines[i])
                i += 1
            out.extend(quote_lines)
            i += 1
            continue

        # ---- Other block macros: pass through as code block comment ----
        macro_match = re.match(r"^\{(\w+).*?\}", line)
        if macro_match and not line.startswith("{{"):
            # pass through Confluence macros as HTML comment
            out.append(f"<!-- confluence: {line} -->")
            i += 1
            continue

        # ---- Horizontal rule -------------------------------------------
        if line.strip() == "----":
            out.append("---")
            i += 1
            continue

        # ---- Table row -------------------------------------------------
        if line.strip().startswith("||"):
            cells = [c.strip() for c in line.strip().strip("|").split("||")]
            cells = [c for c in cells if c]
            out.append("| " + " | ".join(cells) + " |")
            out.append("| " + " | ".join(["---"] * len(cells)) + " |")
            i += 1
            continue
        if line.strip().startswith("|") and not line.strip().startswith("||"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            cells = [c for c in cells if c]
            out.append("| " + " | ".join(cells) + " |")
            i += 1
            continue

        # ---- Headings --------------------------------------------------
        heading_match = re.match(r"^h([1-6])\.\s+(.*)", line)
        if heading_match:
            level = int(heading_match.group(1))
            content = heading_match.group(2)
            out.append("#" * level + " " + _inline_wiki_to_md(content))
            i += 1
            continue

        # ---- Unordered list (*) ----------------------------------------
        ul_match = re.match(r"^(\*+)\s+(.*)", line)
        if ul_match:
            depth = len(ul_match.group(1))
            content = ul_match.group(2)
            indent = "  " * (depth - 1)
            out.append(f"{indent}- {_inline_wiki_to_md(content)}")
            i += 1
            continue

        # ---- Ordered list (#) ------------------------------------------
        ol_match = re.match(r"^(#+)\s+(.*)", line)
        if ol_match:
            depth = len(ol_match.group(1))
            content = ol_match.group(2)
            indent = "  " * (depth - 1)
            out.append(f"{indent}1. {_inline_wiki_to_md(content)}")
            i += 1
            continue

        # ---- Normal line -----------------------------------------------
        out.append(_inline_wiki_to_md(line))
        i += 1

    return "\n".join(out)


def _inline_wiki_to_md(text: str) -> str:
    """Apply inline Wiki Markup → Markdown transformations."""
    # {{inline code}} → `code`
    text = re.sub(r"\{\{(.+?)\}\}", r"`\1`", text)

    # Bold+italic: *_text_* → ***text***
    text = re.sub(r"\*_(.+?)_\*", r"***\1***", text)
    # Bold: *text* → **text**
    text = re.sub(r"(?<!\w)\*(?!\*|\s)(.+?)(?<!\s)\*(?!\w)", r"**\1**", text)
    # Italic: _text_ → *text*
    text = re.sub(r"(?<!\w)_(?!_)(.+?)(?<!_)_(?!\w)", r"*\1*", text)

    # Strikethrough: -text- → ~~text~~
    text = re.sub(r"(?<!\w)-(?!-)(.+?)(?<!-)-(?!\w)", r"~~\1~~", text)

    # Images: !url|alt! → ![alt](url)
    text = re.sub(r"!([^|!\s]+)\|([^!]*)!", r"![\2](\1)", text)
    # Images without alt: !url! → ![](url)
    text = re.sub(r"!([^!\s]+)!", r"![](\1)", text)

    # Links: [text|url] → [text](url)
    text = re.sub(r"\[([^\]|]+)\|([^\]]+)\]", r"[\1](\2)", text)

    return text
