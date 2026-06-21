from __future__ import annotations

from datetime import date, datetime


def parse_profile_date(value: str | date | datetime | None) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def format_profile_date(value: str | date | datetime | None) -> str:
    parsed = parse_profile_date(value)
    return parsed.isoformat() if parsed else "—"
