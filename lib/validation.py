from __future__ import annotations

import re


def validate_password(password: str) -> str | None:
    """Return an error message if password is invalid, else None."""
    if len(password) < 7:
        return "Password must be at least 7 characters."
    if not re.fullmatch(r"[a-zA-Z0-9]+", password):
        return "Password must be alphanumeric (letters and numbers only)."
    return None
