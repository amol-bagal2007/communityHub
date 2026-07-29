from __future__ import annotations

from datetime import date, datetime, time
from typing import Any


def combine_event_start(event_date: date, from_time: time) -> datetime:
    return datetime.combine(event_date, from_time)


def validate_event_schedule(
    *,
    from_time: time,
    to_time: time,
    include_break: bool,
    break_from: time | None,
    break_to: time | None,
) -> list[str]:
    errors: list[str] = []
    if to_time <= from_time:
        errors.append("To Time must be after From Time.")
    if include_break:
        if break_from is None or break_to is None:
            errors.append("Break From and Break To are required when break is enabled.")
        elif break_to <= break_from:
            errors.append("Break To must be after Break From.")
        elif break_from < from_time or break_to > to_time:
            errors.append("Break must fall within the event From–To time range.")
    return errors


def format_clock(value: time | str | None) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, str):
        # Postgres time often comes as "HH:MM:SS"
        parts = value.split(":")
        try:
            parsed = time(int(parts[0]), int(parts[1]))
            return parsed.strftime("%I:%M %p").lstrip("0")
        except (ValueError, IndexError):
            return value
    return value.strftime("%I:%M %p").lstrip("0")


def parse_time_value(value: Any) -> time | None:
    if value is None or value == "":
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        parts = value.split(":")
        try:
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            second = int(float(parts[2])) if len(parts) > 2 else 0
            return time(hour, minute, second)
        except (ValueError, IndexError):
            return None
    return None


def format_event_schedule(event: dict) -> str:
    start_dt = datetime.fromisoformat(
        str(event["event_date"]).replace("Z", "+00:00")
    )
    from_label = start_dt.strftime("%I:%M %p").lstrip("0")
    to_label = format_clock(event.get("end_time"))
    schedule = f"{from_label} – {to_label}"
    break_from = event.get("break_start_time")
    break_to = event.get("break_end_time")
    if break_from and break_to:
        schedule += (
            f" · Break {format_clock(break_from)} – {format_clock(break_to)}"
        )
    return schedule


def build_event_schedule_payload(
    *,
    event_date: date,
    from_time: time,
    to_time: time,
    include_break: bool,
    break_from: time | None,
    break_to: time | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event_date": combine_event_start(event_date, from_time).isoformat(),
        "end_time": to_time.isoformat(),
        "break_start_time": None,
        "break_end_time": None,
    }
    if include_break and break_from and break_to:
        payload["break_start_time"] = break_from.isoformat()
        payload["break_end_time"] = break_to.isoformat()
    return payload
