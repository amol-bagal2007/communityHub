from __future__ import annotations

import re


def validate_password(password: str) -> str | None:
    """Return an error message if password is invalid, else None."""
    if len(password) < 7:
        return "Password must be at least 7 characters."
    if not re.search(r"[a-zA-Z]", password):
        return "Password must contain at least one letter."
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one number."
    return None
