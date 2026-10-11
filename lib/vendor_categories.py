from __future__ import annotations

import math

import streamlit as st

from lib.supabase_client import SchemaClient

VENDOR_PAGE_SIZE = 5
_ALL_CATEGORIES = "__all__"


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


def vendor_name_sort_key(vendor: dict) -> tuple[str, str]:
    return (
        (vendor.get("first_name") or "").strip().lower(),
        (vendor.get("last_name") or "").strip().lower(),
    )


def sort_vendors_by_name(vendors: list[dict]) -> list[dict]:
    return sorted(vendors, key=vendor_name_sort_key)


def filter_vendors_by_category(
    vendors: list[dict], category_id: str | None
) -> list[dict]:
    if not category_id:
        return vendors
    return [v for v in vendors if v.get("category_id") == category_id]


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


def render_vendor_filter_and_page(
    categories: list[dict],
    vendors: list[dict],
    *,
    key_prefix: str,
    page_size: int = VENDOR_PAGE_SIZE,
) -> list[dict]:
    """Category filter + name sort + paging (page_size). Returns current page slice."""
    filter_key = f"{key_prefix}_category_filter"
    page_key = f"{key_prefix}_page"
    last_filter_key = f"{key_prefix}_last_category_filter"

    category_options = {_ALL_CATEGORIES: "All categories"}
    category_options.update({cat["id"]: cat["name"] for cat in categories})
    selected_category = st.selectbox(
        "Filter by category",
        options=list(category_options.keys()),
        format_func=lambda value: category_options[value],
        key=filter_key,
    )
    if st.session_state.get(last_filter_key) != selected_category:
        st.session_state[last_filter_key] = selected_category
        st.session_state[page_key] = 1

    category_id = None if selected_category == _ALL_CATEGORIES else selected_category
    filtered = sort_vendors_by_name(
        filter_vendors_by_category(vendors, category_id)
    )
    total = len(filtered)
    if total == 0:
        st.info(
            "No vendors match this category." if vendors else "No vendors listed yet."
        )
        return []

    total_pages = max(1, math.ceil(total / page_size))
    current_page = int(st.session_state.get(page_key, 1) or 1)
    current_page = max(1, min(current_page, total_pages))
    st.session_state[page_key] = current_page

    start = (current_page - 1) * page_size
    end = start + page_size
    page_vendors = filtered[start:end]

    if total > page_size:
        st.caption(
            f"Showing {start + 1}–{min(end, total)} of {total} "
            f"(page {current_page} of {total_pages})"
        )
        prev_col, mid_col, next_col = st.columns([1, 2, 1])
        if prev_col.button(
            "← Previous",
            key=f"{key_prefix}_prev",
            disabled=current_page <= 1,
            use_container_width=True,
        ):
            st.session_state[page_key] = current_page - 1
            st.rerun()
        mid_col.caption(f"Page {current_page} / {total_pages}")
        if next_col.button(
            "Next →",
            key=f"{key_prefix}_next",
            disabled=current_page >= total_pages,
            use_container_width=True,
        ):
            st.session_state[page_key] = current_page + 1
            st.rerun()
    else:
        st.caption(f"{total} vendor{'s' if total != 1 else ''}")

    return page_vendors
