"""Часовой пояс браузера клиента для контекста LLM (IANA, например Europe/Moscow)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header

ClientTimezoneIdDep = Annotated[
    str | None,
    Header(
        alias="X-Client-Timezone",
        description="IANA Time Zone Database, например Europe/Moscow (Intl.DateTimeFormat().resolvedOptions().timeZone)",
    ),
]
