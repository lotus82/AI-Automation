"""Публичный URL логотипа сайта: путь на том же origin, что у SPA / Mini App."""

from __future__ import annotations

from urllib.parse import urlparse
from uuid import UUID


def site_uploaded_logo_public_path(site_id: UUID, relative: str) -> str:
    """Относительный путь для загруженного файла (прокси / тот же хост, что у клиента)."""
    rel = relative.lstrip("/").replace("\\", "/")
    return f"/api/public/sites/assets/{site_id}/{rel}"


def normalize_site_logo_url(logo_url: str | None) -> str | None:
    """Убирает чужой host у наших ``/api/public/sites/assets/…`` (старые записи с base_url бэкенда)."""
    s = (logo_url or "").strip()
    if not s:
        return None
    if s.startswith("/"):
        return s
    try:
        p = urlparse(s)
        if p.path.startswith("/api/public/sites/assets/"):
            out = p.path
            if p.query:
                out = f"{out}?{p.query}"
            return out
    except ValueError:
        pass
    return s
