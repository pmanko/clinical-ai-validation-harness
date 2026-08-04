"""Canonicalize HTML for structural equality checks (roadmap D5).

- Sort element attributes lexicographically by name.
- Normalize only inter-tag whitespace (whitespace between `>` and `<`).
- NEVER normalize text inside <script>, <style>, <pre>, or answer text
  (elements with class containing ``ans``, or id/class ``answer``).
"""

from __future__ import annotations

import re
from html.parser import HTMLParser


_VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

_PRESERVE_TAGS = frozenset({"script", "style", "pre"})


def _is_answer_element(tag: str, attrs: list[tuple[str, str | None]]) -> bool:
    if tag != "div" and tag != "section" and tag != "article" and tag != "span":
        # Still treat any element whose class/id marks answer text as preserved.
        pass
    attr_map = {k.lower(): (v or "") for k, v in attrs}
    classes = attr_map.get("class", "").split()
    eid = attr_map.get("id", "")
    if "ans" in classes or "answer" in classes or eid == "answer":
        return True
    if any(c.startswith("ans") for c in classes):
        return True
    return False


class _CanonParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self._preserve_depth = 0
        self._preserve_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ordered = sorted(attrs, key=lambda kv: kv[0])
        attr_str = "".join(
            f' {name}' if value is None else f' {name}="{value}"' for name, value in ordered
        )
        self.parts.append(f"<{tag}{attr_str}>")
        if tag in _PRESERVE_TAGS or _is_answer_element(tag, attrs):
            self._preserve_depth += 1
            self._preserve_stack.append(tag)
        if tag in _VOID:
            # HTMLParser still emits end tags for some void elements; we don't open preserve.
            pass

    def handle_endtag(self, tag: str) -> None:
        if self._preserve_stack and self._preserve_stack[-1] == tag:
            self._preserve_stack.pop()
            self._preserve_depth = max(0, self._preserve_depth - 1)
        if tag in _VOID:
            return
        self.parts.append(f"</{tag}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ordered = sorted(attrs, key=lambda kv: kv[0])
        attr_str = "".join(
            f' {name}' if value is None else f' {name}="{value}"' for name, value in ordered
        )
        self.parts.append(f"<{tag}{attr_str} />")

    def handle_data(self, data: str) -> None:
        if self._preserve_depth > 0:
            self.parts.append(data)
            return
        # Outside preserved regions: drop data that is only inter-tag whitespace.
        # Non-whitespace text (e.g. titles) is kept as-is.
        if data.strip() == "":
            return
        self.parts.append(data)

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")


def canonicalize_html(html: str) -> str:
    """Return a canonical form suitable for structural HTML equality."""
    # Preserve a leading doctype if present (HTMLParser may normalize it).
    doctype = ""
    m = re.match(r"<!doctype\s+html\s*>", html, flags=re.IGNORECASE)
    if m:
        doctype = "<!doctype html>"
        html = html[m.end() :]

    parser = _CanonParser()
    parser.feed(html)
    parser.close()
    body = "".join(parser.parts)
    # Normalize only inter-tag whitespace that the parser may have kept as empty
    # between tags when mixed with non-preserve text nodes — already dropped in
    # handle_data. Collapse any residual `>\s+<` outside preserve by a second pass
    # that does NOT touch script/style/pre/answer interiors (already serialized).
    return doctype + body
