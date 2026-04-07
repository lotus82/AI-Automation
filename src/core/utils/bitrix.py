"""Утилиты для URL портала Bitrix24 (общие для API-схем и репозитория)."""


def normalize_bitrix_portal_url(domain_or_url: str) -> str:
    """Приводит домен/URL портала к виду ``https://subdomain.bitrix24.xx`` без завершающего ``/``."""
    s = (domain_or_url or "").strip()
    if not s:
        return ""
    low = s.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return s.rstrip("/")
    return f"https://{s}".rstrip("/")
