from __future__ import annotations

import streamlit as st

from lib.member_groups import render_group_select
from lib.supabase_client import SchemaClient

# Set True to show Group / Sub-Group selectors on signup, profile, and admin user forms.
SHOW_MEMBER_GROUP_FIELDS = False


def load_member_sub_groups(
    client: SchemaClient,
    member_group_id: str | None,
) -> list[dict]:
    if not member_group_id:
        return []
    return (
        client.table("member_sub_groups")
        .select("id, name, member_group_id")
        .eq("member_group_id", member_group_id)
        .order("name")
        .execute()
        .data
        or []
    )


def load_all_member_sub_groups(client: SchemaClient) -> list[dict]:
    return (
        client.table("member_sub_groups")
        .select("id, name, member_group_id, member_groups(name)")
        .order("name")
        .execute()
        .data
        or []
    )


def sub_group_display_name(profile: dict) -> str:
    linked = profile.get("member_sub_groups") or {}
    if isinstance(linked, dict) and linked.get("name"):
        return linked["name"]
    return "—"


def render_sub_group_select(
    sub_groups: list[dict],
    *,
    key: str,
    current_sub_group_id: str | None = None,
) -> str | None:
    """Optional Sub-Group dropdown for the selected group."""
    options = [""] + [sg["id"] for sg in sub_groups]
    id_to_name = {sg["id"]: sg["name"] for sg in sub_groups}
    default_index = 0
    if current_sub_group_id and current_sub_group_id in id_to_name:
        default_index = options.index(current_sub_group_id)

    selected_id = st.selectbox(
        "Sub-Group (optional)",
        options,
        index=default_index,
        format_func=lambda value: (
            "Select sub-group (optional)..."
            if value == ""
            else id_to_name.get(value, value)
        ),
        key=key,
    )
    return selected_id or None


def render_group_sub_group_fields(
    client: SchemaClient,
    groups: list[dict],
    *,
    group_key: str,
    sub_group_key: str,
    current_group_id: str | None = None,
    current_sub_group_id: str | None = None,
) -> tuple[str | None, str | None]:
    """Group + dependent Sub-Group selectors (optional; hidden when flag is off)."""
    if not SHOW_MEMBER_GROUP_FIELDS:
        # Preserve existing assignments while fields are hidden.
        return current_group_id, current_sub_group_id

    def _reset_sub_group() -> None:
        st.session_state[sub_group_key] = ""

    member_group_id = render_group_select(
        groups,
        key=group_key,
        current_group_id=current_group_id,
        on_change=_reset_sub_group,
    )

    member_sub_group_id = None
    if member_group_id:
        sub_groups = load_member_sub_groups(client, member_group_id)
        if sub_groups:
            valid_current = (
                current_sub_group_id
                if current_group_id == member_group_id
                else None
            )
            member_sub_group_id = render_sub_group_select(
                sub_groups,
                key=sub_group_key,
                current_sub_group_id=valid_current,
            )
        else:
            st.caption("No sub-groups configured for this group yet.")

    return member_group_id, member_sub_group_id
