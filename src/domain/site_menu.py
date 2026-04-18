"""Построение нижнего меню Mini App из JSONB ``sites.menu_items``.

Если ``menu_items`` пустой или после фильтрации не осталось пунктов — используется
запасной порядок: все опубликованные страницы по ``order_index``, затем ``created_at``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class SiteNavItemDTO:
    """Один пункт Tabbar: подпись (может отличаться от title страницы) и slug."""

    label: str
    slug: str


def _page_sort_key(p: Any) -> tuple:
    oi = int(getattr(p, "order_index", 0) or 0)
    ca = getattr(p, "created_at", None)
    ca_val = ca.isoformat() if ca is not None else ""
    return oi, ca_val


def nav_items_for_miniapp(
    menu_items_json: list[dict[str, Any]] | None,
    published_pages: list[Any],
) -> list[SiteNavItemDTO]:
    """Возвращает упорядоченные пункты меню для клиента (только опубликованные страницы)."""
    pages_sorted = sorted(published_pages, key=_page_sort_key)
    by_id: dict[UUID, Any] = {p.id: p for p in pages_sorted}

    raw = menu_items_json
    if not raw or not isinstance(raw, list):
        return [
            SiteNavItemDTO(label=str(getattr(p, "title", "") or ""), slug=str(getattr(p, "slug", "") or ""))
            for p in pages_sorted
            if str(getattr(p, "slug", "") or "")
        ]

    decorated: list[tuple[int, str, dict[str, Any]]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        oid = str(row.get("id") or "")
        decorated.append((int(row.get("order_index", 0) or 0), oid, row))
    decorated.sort(key=lambda t: (t[0], t[1]))

    out: list[SiteNavItemDTO] = []
    for _, _, row in decorated:
        if row.get("is_visible") is False:
            continue
        pid_raw = row.get("page_id")
        if not pid_raw:
            continue
        try:
            pid = UUID(str(pid_raw))
        except ValueError:
            continue
        page = by_id.get(pid)
        if page is None:
            continue
        if not bool(getattr(page, "is_published", True)):
            continue
        title = str(getattr(page, "title", "") or "")
        slug = str(getattr(page, "slug", "") or "")
        if not slug:
            continue
        label_raw = (str(row.get("label") or "")).strip()
        out.append(SiteNavItemDTO(label=label_raw or title, slug=slug))

    if not out:
        return [
            SiteNavItemDTO(label=str(getattr(p, "title", "") or ""), slug=str(getattr(p, "slug", "") or ""))
            for p in pages_sorted
            if str(getattr(p, "slug", "") or "")
        ]
    return out
