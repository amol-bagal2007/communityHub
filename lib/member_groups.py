from __future__ import annotations

import streamlit as st

from lib.supabase_client import SchemaClient


def load_member_groups(client: SchemaClient) -> list[dict]:
    return (
        client.table("member_groups")
        .select("id, name")
        .order("name")
        .execute()
        .data
        or []
    )


def group_display_name(profile: dict) -> str:
    linked = profile.get("member_groups") or {}
    if isinstance(linked, dict) and linked.get("name"):
        return linked["name"]
    return "—"


def render_group_select(
    groups: list[dict],
    *,
    key: str,
    current_group_id: str | None = None,
    on_change=None,
) -> str | None:
    """Optional Group dropdown; returns selected group id or None."""
    options = [""] + [g["id"] for g in groups]
    id_to_name = {g["id"]: g["name"] for g in groups}
    default_index = 0
    if current_group_id and current_group_id in id_to_name:
        default_index = options.index(current_group_id)

    selectbox_kwargs = {
        "label": "Group (optional)",
        "options": options,
        "index": default_index,
        "format_func": lambda value: (
            "Select group (optional)..."
            if value == ""
            else id_to_name.get(value, value)
        ),
        "key": key,
    }
    if on_change is not None:
        selectbox_kwargs["on_change"] = on_change

    selected_id = st.selectbox(**selectbox_kwargs)
    return selected_id or None
