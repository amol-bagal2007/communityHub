from __future__ import annotations

import streamlit as st

from lib.supabase_client import SchemaClient


def load_vendor_categories(client: SchemaClient) -> list[dict]:
    return (
        client.table("vendor_categories")
        .select("id, name")
        .order("name")
        .execute()
        .data
        or []
    )


def category_display_name(vendor: dict) -> str:
    linked = vendor.get("vendor_categories") or {}
    if isinstance(linked, dict) and linked.get("name"):
        return linked["name"]
    return "Uncategorized"


def render_category_select(
    categories: list[dict],
    *,
    key: str,
    current_category_id: str | None = None,
) -> str | None:
    if not categories:
        st.warning("No vendor categories yet. An admin must add categories first.")
        return None

    options = {cat["name"]: cat["id"] for cat in categories}
    names = list(options.keys())
    default_index = 0
    if current_category_id:
        for index, cat in enumerate(categories):
            if cat["id"] == current_category_id:
                default_index = index
                break

    selected_name = st.selectbox("Category *", names, index=default_index, key=key)
    return options[selected_name]
