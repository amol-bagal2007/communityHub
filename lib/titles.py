from __future__ import annotations

TITLE_OPTIONS = ["Mr.", "Ms.", "Mrs.", "Miss.", "Mx."]


def is_valid_title(title: str | None) -> bool:
    return bool(title and title in TITLE_OPTIONS)
