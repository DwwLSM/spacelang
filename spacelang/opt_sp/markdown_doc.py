"""Render the documentation page from Markdown without any dependency.

Only the constructs ``documentation.md`` actually uses are supported: ATX
headings, paragraphs, ordered and unordered lists (nested by indentation),
pipe tables, fenced code blocks, blockquotes, thematic breaks, and the inline
forms ``code``, ``**strong**``, ``*emphasis*`` and ``[links](target)``. Raw
HTML in the source is escaped instead of being passed through: the page is
served to a local browser, but document text must never become markup.

The renderer also reports the heading outline so the page can build its table
of contents from the same pass that produces the body. Anchors follow GitHub's
slug rules, which keeps the hand-written links inside ``documentation.md``
working after rendering.
"""

from __future__ import annotations

from dataclasses import dataclass
import html
import re

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
_FENCE = re.compile(r"^(```+|~~~+)\s*([\w.+#-]*)\s*$")
_THEMATIC_BREAK = re.compile(
    r"^[ \t]*(?:-[ \t]*){3,}$|^[ \t]*(?:\*[ \t]*){3,}$|^[ \t]*(?:_[ \t]*){3,}$"
)
_QUOTE = re.compile(r"^[ \t]*>[ \t]?(.*)$")
_LIST_ITEM = re.compile(r"^([ \t]*)([-*+]|\d{1,9}[.)])[ \t]+(.*)$")
_TABLE_DIVIDER = re.compile(
    r"^[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(?:\|[ \t]*:?-{2,}:?[ \t]*)*\|?[ \t]*$"
)
_CODE_SPAN = re.compile(r"(`+)(.+?)\1")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_STRONG = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
_EMPHASIS = re.compile(r"(?<![\w*])\*(?=\S)([^*]+?)(?<=\S)\*(?![\w*])")
_TAG = re.compile(r"<[^>]+>")
_ALLOWED_SCHEMES = ("http://", "https://", "mailto:")
_TOC_LEVELS = (2, 3)
_TOC_SKIP = frozenset({"contents"})


@dataclass(frozen=True)
class TocEntry:
    """One sidebar link: a level-two or level-three heading."""

    level: int
    text: str
    anchor: str


def render_document(source: str) -> tuple[str, list[TocEntry]]:
    """Render Markdown ``source`` to ``(body_html, toc)``."""
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    toc: list[TocEntry] = []
    body = _render_blocks(lines, _Slugger(), toc)
    return body, toc


def render_toc(toc: list[TocEntry], *, title: str = "Contents") -> str:
    """Render the sidebar navigation, or nothing when the document has no sections."""
    if not toc:
        return ""
    parts = [f"<h2>{html.escape(title)}</h2>"]
    for entry in toc:
        css_class = "toc-h3" if entry.level > 2 else "toc-h2"
        parts.append(
            f'<a class="{css_class}" href="#{entry.anchor}">{html.escape(entry.text)}</a>'
        )
    return "".join(parts)


def _render_blocks(lines: list[str], slugger: "_Slugger", toc: list[TocEntry]) -> str:
    blocks: list[str] = []
    index, total = 0, len(lines)
    while index < total:
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        fence = _FENCE.match(line)
        if fence:
            rendered, index = _render_fence(lines, index, fence)
            blocks.append(rendered)
            continue

        heading = _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            text = _inline(heading.group(2).strip())
            plain = _plain_text(text)
            anchor = slugger.unique(plain)
            blocks.append(f'<h{level} id="{anchor}">{text}</h{level}>')
            if level in _TOC_LEVELS and plain.casefold() not in _TOC_SKIP:
                toc.append(TocEntry(level, plain, anchor))
            index += 1
            continue

        if _THEMATIC_BREAK.match(line):
            blocks.append("<hr>")
            index += 1
            continue

        if _is_table_start(lines, index):
            rendered, index = _render_table(lines, index)
            blocks.append(rendered)
            continue

        if _QUOTE.match(line):
            inner: list[str] = []
            while index < total and _QUOTE.match(lines[index]):
                inner.append(_QUOTE.match(lines[index]).group(1))
                index += 1
            blocks.append(
                "<blockquote>" + _render_blocks(inner, slugger, toc) + "</blockquote>"
            )
            continue

        if _LIST_ITEM.match(line):
            rendered, index = _render_list(lines, index)
            blocks.append(rendered)
            continue

        paragraph = [line.strip()]
        index += 1
        while (
            index < total
            and lines[index].strip()
            and not _is_block_start(lines, index)
        ):
            paragraph.append(lines[index].strip())
            index += 1
        blocks.append("<p>" + _inline(" ".join(paragraph)) + "</p>")
    return "\n".join(blocks)


def _is_block_start(lines: list[str], index: int) -> bool:
    line = lines[index]
    return bool(
        _FENCE.match(line)
        or _HEADING.match(line)
        or _THEMATIC_BREAK.match(line)
        or _QUOTE.match(line)
        or _LIST_ITEM.match(line)
        or _is_table_start(lines, index)
    )


def _render_fence(lines: list[str], index: int, match: "re.Match[str]") -> tuple[str, int]:
    marker = match.group(1)
    closer = re.compile(r"^" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}[ \t]*$")
    cursor = index + 1
    body: list[str] = []
    while cursor < len(lines) and not closer.match(lines[cursor]):
        body.append(lines[cursor])
        cursor += 1
    language = re.sub(r"[^\w.+#-]", "", match.group(2))
    attribute = f' class="language-{language}"' if language else ""
    code = html.escape("\n".join(body), quote=False)
    return f"<pre><code{attribute}>{code}</code></pre>", min(cursor + 1, len(lines))


def _is_table_start(lines: list[str], index: int) -> bool:
    return (
        lines[index].lstrip().startswith("|")
        and index + 1 < len(lines)
        and bool(_TABLE_DIVIDER.match(lines[index + 1]))
    )


def _render_table(lines: list[str], index: int) -> tuple[str, int]:
    headers = _split_row(lines[index])
    alignments = _alignments(_split_row(lines[index + 1]))
    cursor = index + 2
    rows: list[list[str]] = []
    while (
        cursor < len(lines)
        and lines[cursor].strip()
        and lines[cursor].lstrip().startswith("|")
    ):
        rows.append(_split_row(lines[cursor]))
        cursor += 1

    def cell(tag: str, text: str, column: int) -> str:
        alignment = alignments[column] if column < len(alignments) else "left"
        style = f' style="text-align:{alignment}"' if alignment != "left" else ""
        return f"<{tag}{style}>{_inline(text)}</{tag}>"

    parts = ["<table><thead><tr>"]
    parts.extend(cell("th", text, column) for column, text in enumerate(headers))
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        parts.extend(cell("td", text, column) for column, text in enumerate(row))
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts), cursor


def _split_row(line: str) -> list[str]:
    """Split a pipe row on unescaped pipes and drop the outer empty cells."""
    cells: list[str] = []
    buffer: list[str] = []
    index = 0
    while index < len(line):
        character = line[index]
        if character == "\\" and index + 1 < len(line) and line[index + 1] in "|\\":
            buffer.append(line[index + 1])
            index += 2
            continue
        if character == "|":
            cells.append("".join(buffer))
            buffer = []
        else:
            buffer.append(character)
        index += 1
    cells.append("".join(buffer))
    if cells and not cells[0].strip():
        cells.pop(0)
    if cells and not cells[-1].strip():
        cells.pop()
    return [cell.strip() for cell in cells]


def _alignments(cells: list[str]) -> list[str]:
    alignments: list[str] = []
    for cell in cells:
        cell = cell.strip()
        if cell.startswith(":") and cell.endswith(":"):
            alignments.append("center")
        elif cell.endswith(":"):
            alignments.append("right")
        else:
            alignments.append("left")
    return alignments


def _render_list(lines: list[str], index: int) -> tuple[str, int]:
    """Parse one list block into a node tree, honouring indentation."""
    roots: list[dict] = []
    stack: list[dict] = []
    cursor = index
    while cursor < len(lines):
        line = lines[cursor]
        if not line.strip():
            break
        item = _LIST_ITEM.match(line)
        if item:
            indent = len(item.group(1).expandtabs(4))
            node = {
                "indent": indent,
                "marker": item.group(2),
                "text": [item.group(3).strip()],
                "children": [],
            }
            while stack and stack[-1]["indent"] >= indent:
                stack.pop()
            (stack[-1]["children"] if stack else roots).append(node)
            stack.append(node)
        elif line[:1] in (" ", "\t") and stack:
            stack[-1]["text"].append(line.strip())
        else:
            break
        cursor += 1
    return _emit_list(roots), cursor


def _emit_list(nodes: list[dict]) -> str:
    if not nodes:
        return ""
    tag = "ol" if nodes[0]["marker"][0].isdigit() else "ul"
    parts = [f"<{tag}>"]
    for node in nodes:
        text = _inline(" ".join(part for part in node["text"] if part))
        parts.append(f"<li>{text}{_emit_list(node['children'])}</li>")
    parts.append(f"</{tag}>")
    return "".join(parts)


def _inline(text: str) -> str:
    pieces: list[str] = []
    position = 0
    for match in _CODE_SPAN.finditer(text):
        pieces.append(_inline_markup(text[position:match.start()]))
        code = html.escape(match.group(2).strip(), quote=False)
        pieces.append(f"<code>{code}</code>")
        position = match.end()
    pieces.append(_inline_markup(text[position:]))
    return "".join(pieces)


def _inline_markup(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = _LINK.sub(_link, escaped)
    escaped = _STRONG.sub(r"<strong>\1</strong>", escaped)
    return _EMPHASIS.sub(r"<em>\1</em>", escaped)


def _link(match: "re.Match[str]") -> str:
    label, target = match.group(1), match.group(2)
    if not _is_safe_target(target):
        return match.group(0)
    return f'<a href="{html.escape(target, quote=True)}">{label}</a>'


def _is_safe_target(target: str) -> bool:
    lowered = target.strip().casefold()
    if lowered.startswith(("#", "/", "./", "../")):
        return True
    head = lowered.split("/", 1)[0].split("#", 1)[0]
    if ":" not in head:
        return True
    return lowered.startswith(_ALLOWED_SCHEMES)


def _plain_text(rendered: str) -> str:
    return html.unescape(_TAG.sub("", rendered)).strip()


class _Slugger:
    """Make heading anchors unique the way GitHub does (``x``, ``x-1``, ...)."""

    def __init__(self) -> None:
        self._seen: dict[str, int] = {}

    def unique(self, text: str) -> str:
        base = _slugify(text)
        count = self._seen.get(base, 0)
        self._seen[base] = count + 1
        return base if count == 0 else f"{base}-{count}"


def _slugify(text: str) -> str:
    kept = [
        character
        for character in text.strip().casefold()
        if character.isalnum() or character in "-_ "
    ]
    return "".join(kept).strip().replace(" ", "-") or "section"


__all__ = ["TocEntry", "render_document", "render_toc"]
