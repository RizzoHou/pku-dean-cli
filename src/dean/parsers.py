"""HTML parsers for each dean.pku.edu.cn page type.

Selectors target stable CSS classes observed on the live site:

* sidebar      — ``.student_nav li`` with ``p.tosubnav`` category headers
* rules list   — ``#sub_content`` anchors to ``rules_info.php?id=``
* rule detail  — ``.newsinfo_box`` body text
* file listing — ``.load_item`` rows (download.php / openinfo.php)
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .client import INDEX_URL, WEB_URL
from .errors import DeanError
from .models import FileItem, Page, RuleDoc, RuleItem, SidebarLink
from .pagination import parse_last_page

_ID_RE = re.compile(r"[?&]id=(\d+)")
_DIGITS_RE = re.compile(r"(\d+)")


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _extract_id(href: str) -> int | None:
    m = _ID_RE.search(href or "")
    return int(m.group(1)) if m else None


# -- sidebar ----------------------------------------------------------------


def parse_sidebar(html: str) -> list[SidebarLink]:
    """Parse the 学生 sidebar from index.php into categorized links."""
    soup = _soup(html)
    nav = soup.select_one(".student_nav")
    if nav is None:
        raise DeanError("student sidebar not found on index page", code="parse_error")

    links: list[SidebarLink] = []
    for li in nav.find_all("li", recursive=True):
        header = li.find("p", class_="tosubnav")
        category = header.get_text(strip=True) if header else ""
        sub = li.find("div", class_="sub_stunav")
        if sub is not None:
            anchors = sub.find_all("a")
        else:
            # Top-level entry (e.g. 学生服务中心): the <li>'s own anchor.
            anchors = li.find_all("a", recursive=False)
        for a in anchors:
            href = a.get("href")
            title = a.get_text(strip=True)
            if not href or not title:
                continue
            links.append(
                SidebarLink(
                    category=category or title,
                    title=title,
                    url=urljoin(INDEX_URL, href),
                )
            )
    if not links:
        raise DeanError("no links found in student sidebar", code="parse_error")
    return links


# -- rules listings ---------------------------------------------------------


def parse_rules(html: str, scope: str) -> Page:
    """Parse rules.php / rules_school.php into a page of :class:`RuleItem`."""
    soup = _soup(html)
    content = soup.select_one("#sub_content") or soup
    seen: set[int] = set()
    items: list[RuleItem] = []
    for a in content.select('a[href*="rules_info.php"]'):
        rid = _extract_id(a.get("href", ""))
        title = a.get_text(strip=True)
        if rid is None or not title or rid in seen:
            continue
        seen.add(rid)
        items.append(
            RuleItem(
                id=rid,
                title=title,
                scope=scope,
                url=urljoin(WEB_URL, a["href"]),
            )
        )
    return Page(page=_current_page(soup), last_page=parse_last_page(soup), items=items)


def parse_rule_doc(html: str, rule_id: int, url: str) -> RuleDoc:
    """Parse a single rule detail page (rules_info.php?id=...)."""
    soup = _soup(html)
    box = soup.select_one(".newsinfo_box") or soup.select_one(".news_con")
    if box is None:
        raise DeanError(f"rule body not found for id={rule_id}", code="parse_error")
    title_el = soup.select_one("#sub_content .active") or box.find(["h1", "h2", "h3"])
    title = title_el.get_text(strip=True) if title_el else ""
    text = box.get_text("\n", strip=True)
    # A missing rule still serves the template with an empty breadcrumb and a
    # body holding only the share widget — treat that as not found.
    if not title and len(text) < 10:
        raise DeanError(f"no rule found with id={rule_id}", code="not_found")
    return RuleDoc(id=rule_id, title=title, text=text, url=url)


# -- file listings ----------------------------------------------------------


def parse_files(html: str, kind: str) -> Page:
    """Parse download.php / openinfo.php into a page of :class:`FileItem`."""
    soup = _soup(html)
    items: list[FileItem] = []
    for item in soup.select(".load_item"):
        title_el = item.select_one(".load_top")
        link = item.select_one("a.xz") or item.select_one('a[href*="download_down.php"]')
        if title_el is None or link is None:
            continue
        href = link.get("href", "")
        fid = _extract_id(href)
        if fid is None:
            continue
        num_el = item.select_one("a.num")
        date_el = item.select_one("a.update")
        items.append(
            FileItem(
                id=fid,
                title=title_el.get_text(strip=True),
                kind=kind,
                download_url=urljoin(WEB_URL, href),
                downloads=_first_int(num_el.get_text()) if num_el else None,
                date=_after_colon(date_el.get_text()) if date_el else None,
            )
        )
    return Page(page=_current_page(soup), last_page=parse_last_page(soup), items=items)


# -- helpers ----------------------------------------------------------------


def _current_page(soup: BeautifulSoup) -> int:
    active = soup.select_one("#page_bar a.active")
    if active:
        m = re.search(r"[?&]page=(\d+)", active.get("href", ""))
        if m:
            return int(m.group(1))
    return 1


def _first_int(text: str) -> int | None:
    m = _DIGITS_RE.search(text or "")
    return int(m.group(1)) if m else None


def _after_colon(text: str) -> str | None:
    if not text:
        return None
    return text.split("：", 1)[-1].split(":", 1)[-1].strip() or None
