from __future__ import annotations

import streamlit as st

from lib.supabase_client import SchemaClient

FLAG_VENDORS_TAB = "vendors_tab"
FLAG_EVENTS_TAB = "events_tab"
FLAG_LOCAL_BUSINESS_TAB = "local_business_tab"


def is_feature_enabled(client: SchemaClient, key: str, *, default: bool = False) -> bool:
    try:
        row = (
            client.table("app_feature_flags")
            .select("enabled")
            .eq("key", key)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not row:
            return default
        return bool(row[0].get("enabled"))
    except Exception:
        # Migration not applied yet — keep current tabs visible.
        return True


def set_feature_enabled(client: SchemaClient, key: str, enabled: bool) -> str | None:
    try:
        existing = (
            client.table("app_feature_flags")
            .select("key")
            .eq("key", key)
            .limit(1)
            .execute()
            .data
            or []
        )
        if existing:
            client.table("app_feature_flags").update(
                {"enabled": enabled}
            ).eq("key", key).execute()
        else:
            client.table("app_feature_flags").insert(
                {"key": key, "enabled": enabled}
            ).execute()
        return None
    except Exception as exc:
        return str(exc)


def render_feature_toggle(
    client: SchemaClient,
    *,
    key: str,
    label: str,
    help_text: str,
    widget_key: str,
) -> None:
    current = is_feature_enabled(client, key, default=False)
    if widget_key not in st.session_state:
        st.session_state[widget_key] = current
    enabled = st.checkbox(label, key=widget_key, help=help_text)
    if enabled != current:
        err = set_feature_enabled(client, key, enabled)
        if err:
            st.session_state[widget_key] = current
            st.error(
                f"Could not update visibility (run migration 024): {err}"
            )
        else:
            st.success(
                f"{'Enabled' if enabled else 'Disabled'} for members."
            )
            st.rerun()


def load_societies(
    client: SchemaClient,
    *,
    enabled_only: bool = False,
    include_id: str | None = None,
) -> list[dict]:
    try:
        rows = (
            client.table("societies")
            .select("id, name, is_enabled")
            .order("name")
            .execute()
            .data
            or []
        )
    except Exception:
        rows = (
            client.table("societies")
            .select("id, name")
            .order("name")
            .execute()
            .data
            or []
        )
        for row in rows:
            row.setdefault("is_enabled", True)

    if not enabled_only:
        return rows
    return [
        row
        for row in rows
        if row.get("is_enabled") or (include_id and row.get("id") == include_id)
    ]


def load_towers(
    client: SchemaClient,
    society_id: str | None,
    *,
    enabled_only: bool = False,
    include_id: str | None = None,
) -> list[dict]:
    if not society_id:
        return []
    try:
        rows = (
            client.table("towers")
            .select("id, name, society_id, is_enabled")
            .eq("society_id", society_id)
            .order("name")
            .execute()
            .data
            or []
        )
    except Exception:
        rows = (
            client.table("towers")
            .select("id, name, society_id")
            .eq("society_id", society_id)
            .order("name")
            .execute()
            .data
            or []
        )
        for row in rows:
            row.setdefault("is_enabled", True)

    if not enabled_only:
        return rows
    return [
        row
        for row in rows
        if row.get("is_enabled") or (include_id and row.get("id") == include_id)
    ]


def set_society_enabled(client: SchemaClient, society_id: str, enabled: bool) -> str | None:
    try:
        client.table("societies").update({"is_enabled": enabled}).eq(
            "id", society_id
        ).execute()
        return None
    except Exception as exc:
        return str(exc)


def set_tower_enabled(client: SchemaClient, tower_id: str, enabled: bool) -> str | None:
    try:
        client.table("towers").update({"is_enabled": enabled}).eq(
            "id", tower_id
        ).execute()
        return None
    except Exception as exc:
        return str(exc)
