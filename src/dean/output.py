"""Output rendering: the JSON envelope and human-readable formatters.

The JSON envelope matches the convention pku-captain already consumes for the
``plib`` / ``pku3b`` CLIs:

* success → ``{"ok": true, "data": <payload>}``
* failure → ``{"ok": false, "error": {"code": ..., "message": ...}}``

The envelope is always written to **stdout**, even on failure, so a subprocess
caller parses one stream.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from typing import Any

from .errors import DeanError
from .models import FileItem, Page, RuleDoc, RuleItem, SidebarLink


def jsonable(obj: Any) -> Any:
    """Recursively convert dataclasses / Page into plain JSON-friendly values."""
    if isinstance(obj, Page):
        return {
            "page": obj.page,
            "last_page": obj.last_page,
            "count": len(obj.items),
            "items": [jsonable(i) for i in obj.items],
        }
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(i) for i in obj]
    return obj


def emit_json_ok(data: Any) -> None:
    json.dump({"ok": True, "data": jsonable(data)}, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def emit_json_error(err: DeanError) -> None:
    json.dump({"ok": False, "error": err.to_dict()}, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


# -- human renderers --------------------------------------------------------


def render_sidebar(links: list[SidebarLink]) -> str:
    out: list[str] = []
    current = object()
    for link in links:
        if link.category != current:
            current = link.category
            out.append(f"\n# {link.category}")
        out.append(f"  {link.title}\n    {link.url}")
    return "\n".join(out).lstrip("\n")


def render_rules(page: Page) -> str:
    header = _page_header(page, "rules")
    rows = [f"  [{it.id:>4}] {it.title}" for it in page.items]
    return "\n".join([header, *rows]) if rows else header + "\n  (no rules found)"


def render_rule_doc(doc: RuleDoc) -> str:
    return f"{doc.title}\n{'=' * len(doc.title)}\n{doc.url}\n\n{doc.text}"


def render_files(page: Page) -> str:
    header = _page_header(page, "files")
    rows = []
    for it in page.items:
        meta = []
        if it.date:
            meta.append(it.date)
        if it.downloads is not None:
            meta.append(f"{it.downloads} downloads")
        suffix = f"  ({', '.join(meta)})" if meta else ""
        rows.append(f"  [{it.id:>4}] {it.title}{suffix}")
    return "\n".join([header, *rows]) if rows else header + "\n  (no files found)"


def render_rule_list(items: list[RuleItem]) -> str:
    rows = [f"  [{it.id:>4}] {it.title}" for it in items]
    head = f"rules — {len(items)} item(s), all pages"
    return "\n".join([head, *rows])


def render_file_list(items: list[FileItem]) -> str:
    rows = []
    for it in items:
        meta = []
        if it.date:
            meta.append(it.date)
        if it.downloads is not None:
            meta.append(f"{it.downloads} downloads")
        suffix = f"  ({', '.join(meta)})" if meta else ""
        rows.append(f"  [{it.id:>4}] {it.title}{suffix}")
    head = f"files — {len(items)} item(s), all pages"
    return "\n".join([head, *rows])


def _page_header(page: Page, label: str) -> str:
    return f"{label} — page {page.page}/{page.last_page}, {len(page.items)} item(s)"
