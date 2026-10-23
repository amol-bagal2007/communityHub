from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_component = components.declare_component(
    "communityhub_remember_login",
    path=str(Path(__file__).resolve().parent / "remember_login_frontend"),
)


def load_remembered_login() -> dict | None:
    """Read email, password, and the Remember me choice saved in this browser."""
    value = _component(action="load", key="communityhub_remember_load", default=None)
    if not isinstance(value, dict):
        return None
    return {
        "email": str(value.get("email") or ""),
        "password": str(value.get("password") or ""),
        "remember": bool(value.get("remember", True)),
    }


def save_remembered_login(email: str, password: str, remember: bool, token: str) -> bool:
    """Store or clear the login in this browser. Returns True once this save has finished."""
    value = _component(
        action="save",
        email=email,
        password=password if remember else "",
        remember=bool(remember),
        token=token,
        key="communityhub_remember_save",
        default=None,
    )
    return isinstance(value, dict) and value.get("token") == token
