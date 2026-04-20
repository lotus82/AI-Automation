"""Генерация свободных слотов записи по рабочим часам, блокировкам и существующим записям."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src.core.config import Settings

_UTC = ZoneInfo("UTC")

_WEEKDAY_KEYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def _day_key_for_date(d: date) -> str:
    return _WEEKDAY_KEYS[d.weekday()]


def _parse_hh_mm(raw: str) -> time | None:
    s = (raw or "").strip()
    if not s or len(s) < 4:
        return None
    parts = s.split(":")
    if len(parts) < 2:
        return None
    try:
        h = int(parts[0], 10)
        m = int(parts[1], 10)
    except ValueError:
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return time(h, m)


def _window_for_day(
    working_hours: dict[str, Any],
    day_key: str,
    day_local: date,
    tz: ZoneInfo,
) -> tuple[datetime, datetime] | None:
    raw = working_hours.get(day_key)
    if not isinstance(raw, list) or len(raw) < 2:
        return None
    t0 = _parse_hh_mm(str(raw[0]))
    t1 = _parse_hh_mm(str(raw[1]))
    if t0 is None or t1 is None:
        return None
    start_dt = datetime.combine(day_local, t0, tzinfo=tz)
    end_dt = datetime.combine(day_local, t1, tzinfo=tz)
    if end_dt <= start_dt:
        return None
    return (start_dt, end_dt)


def intervals_overlap(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> bool:
    """Полуинтервалы [a0, a1) и [b0, b1)."""
    return a0 < b1 and b0 < a1


def compute_available_slots(
    *,
    target_date: date,
    duration_minutes: int,
    working_hours: dict[str, Any],
    busy_intervals: list[tuple[datetime, datetime]],
    appointment_intervals: list[tuple[datetime, datetime]],
    settings: Settings,
) -> list[tuple[datetime, datetime]]:
    """Возвращает список (start, end) в timezone-aware UTC (как в БД)."""
    tz = settings.app_zoneinfo
    day_key = _day_key_for_date(target_date)
    window = _window_for_day(working_hours, day_key, target_date, tz)
    if window is None:
        return []
    win_start, win_end = window
    if duration_minutes <= 0:
        return []

    blocked = list(busy_intervals) + list(appointment_intervals)
    out: list[tuple[datetime, datetime]] = []
    cur = win_start
    step = timedelta(minutes=duration_minutes)
    while cur + step <= win_end:
        slot_start = cur
        slot_end = cur + step
        conflict = False
        for b0, b1 in blocked:
            if intervals_overlap(slot_start, slot_end, b0, b1):
                conflict = True
                break
        if not conflict:
            out.append((slot_start.astimezone(_UTC), slot_end.astimezone(_UTC)))
        cur = slot_end
    return out
