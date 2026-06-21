from __future__ import annotations

import streamlit as st


def format_name(profile: dict | None, fallback: str = "User") -> str:
    if not profile:
        return fallback
    first = (profile.get("first_name") or "").strip()
    last = (profile.get("last_name") or "").strip()
    name = f"{first} {last}".strip()
    return name or fallback


def render_recommended_by_readonly(name: str) -> None:
    """Show Recommended By as non-editable text (regular users)."""
    st.markdown(f"**Recommended By:** {name}")
    st.caption("Automatically set from your profile. Only admins can change this.")


def render_recommended_by_field(
    *,
    admin: bool,
    default_name: str,
    current_value: str = "",
) -> str:
    """Editable Recommended By for admins; read-only display for everyone else."""
    if admin:
        return st.text_input(
            "Recommended By",
            value=current_value or default_name,
        )
    render_recommended_by_readonly(current_value or default_name)
    return current_value or default_name
