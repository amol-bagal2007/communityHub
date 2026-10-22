from __future__ import annotations

import math
from datetime import datetime

import streamlit as st

from lib.supabase_client import SchemaClient

PAGE_SIZE = 10


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _format_time(value: str | None) -> str:
    parsed = _parse_time(value)
    if not parsed:
        return ""
    return parsed.strftime("%d %b %Y, %I:%M %p")


def _was_edited(row: dict) -> bool:
    created = _parse_time(row.get("created_at"))
    updated = _parse_time(row.get("updated_at"))
    if not created or not updated:
        return False
    return abs((updated - created).total_seconds()) > 2


def _load_feedback(client: SchemaClient) -> tuple[list[dict], str | None]:
    try:
        rows = client.raw.rpc("list_feedback_suggestions").execute().data or []
        return [row for row in rows if isinstance(row, dict)], None
    except Exception as exc:
        message = str(exc)
        if "list_feedback_suggestions" in message or "PGRST202" in message:
            return [], "Feedback is unavailable. Run Supabase migration 034, then refresh."
        return [], f"Could not load feedback: {exc}"


def _rpc_error(exc: Exception) -> str:
    message = str(exc)
    if "Feedback comments are required" in message:
        return "Feedback comments are required."
    if "cannot exceed 5000" in message:
        return "Feedback comments cannot exceed 5000 characters."
    if "only edit your own" in message or "only delete your own" in message:
        return "You can only change feedback you posted."
    if "list_feedback_suggestions" in message or "PGRST202" in message or "post_feedback" in message:
        return "Feedback is unavailable. Run Supabase migration 034, then refresh."
    return message


def _delete_feedback(client: SchemaClient, row_id: str) -> None:
    try:
        client.raw.rpc(
            "soft_delete_feedback_suggestion",
            {"p_id": row_id},
        ).execute()
        st.success("Feedback deleted.")
        st.rerun()
    except Exception as exc:
        st.error(_rpc_error(exc))


def _page_rows(rows: list[dict], *, key_prefix: str) -> list[dict]:
    total = len(rows)
    if total == 0:
        st.info(
            "You have not posted any feedback yet."
            if key_prefix == "user_feedback"
            else "No feedback or suggestions yet."
        )
        return []

    page_key = f"{key_prefix}_page"
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    current_page = int(st.session_state.get(page_key, 1) or 1)
    current_page = max(1, min(current_page, total_pages))
    st.session_state[page_key] = current_page

    start = (current_page - 1) * PAGE_SIZE
    page_items = rows[start : start + PAGE_SIZE]

    st.caption(
        f"Showing {start + 1}–{min(start + PAGE_SIZE, total)} of {total} "
        f"(page {current_page} of {total_pages}, {PAGE_SIZE} per page)"
    )
    if total_pages > 1:
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
    return page_items


def render_feedback(client: SchemaClient, *, admin: bool = False) -> None:
    st.subheader("Feedback/Suggestion")
    st.caption(
        "You can see and delete only the feedback you posted."
        if not admin
        else "You can see every comment, who posted it, and delete any of them."
    )

    if st.session_state.pop("_feedback_clear_draft", False):
        st.session_state["feedback_new_comment"] = ""

    comment = st.text_area(
        "Feedback comments",
        key="feedback_new_comment",
        placeholder="Write your feedback or suggestion",
    )
    if st.button("Post", type="primary", key="feedback_post"):
        if not (comment or "").strip():
            st.error("Feedback comments are required.")
        else:
            try:
                client.raw.rpc(
                    "post_feedback_suggestion",
                    {"p_comment": comment.strip()},
                ).execute()
                st.session_state["_feedback_clear_draft"] = True
                st.session_state["user_feedback_page"] = 1
                st.session_state["admin_feedback_page"] = 1
                st.success("Feedback posted.")
                st.rerun()
            except Exception as exc:
                st.error(_rpc_error(exc))

    rows, error = _load_feedback(client)
    if error:
        st.warning(error)
        return

    key_prefix = "admin_feedback" if admin else "user_feedback"
    for row in _page_rows(rows, key_prefix=key_prefix):
        row_id = row.get("id")
        deleted = bool(row.get("deleted_at"))
        is_mine = bool(row.get("is_mine"))
        edit_key = f"{key_prefix}_edit_{row_id}"

        with st.container(border=True):
            posted = _format_time(row.get("created_at"))
            meta = posted
            if _was_edited(row) and not deleted:
                meta = f"{meta} · Edited" if meta else "Edited"
            if deleted:
                meta = f"{meta} · Deleted" if meta else "Deleted"
            if is_mine and not admin:
                meta = f"Your feedback · {meta}" if meta else "Your feedback"
            if meta:
                st.caption(meta)

            editing = bool(st.session_state.get(edit_key)) and is_mine and not deleted
            if editing:
                text_key = f"{key_prefix}_text_{row_id}"
                if text_key not in st.session_state:
                    st.session_state[text_key] = row.get("comment") or ""
                edited = st.text_area("Feedback comments", key=text_key)
                save_col, cancel_col = st.columns(2)
                if save_col.button("Save", key=f"{key_prefix}_save_{row_id}", type="primary"):
                    if not (edited or "").strip():
                        st.error("Feedback comments are required.")
                    else:
                        try:
                            client.raw.rpc(
                                "update_feedback_suggestion",
                                {"p_id": row_id, "p_comment": edited.strip()},
                            ).execute()
                            st.session_state[edit_key] = False
                            st.success("Feedback updated.")
                            st.rerun()
                        except Exception as exc:
                            st.error(_rpc_error(exc))
                if cancel_col.button("Cancel", key=f"{key_prefix}_cancel_{row_id}"):
                    st.session_state[edit_key] = False
                    st.rerun()
            else:
                st.write(row.get("comment") or "")

            if admin:
                st.markdown(
                    f"**Name:** {row.get('author_name') or '—'}  \n"
                    f"**Phone:** {row.get('phone') or '—'}  \n"
                    f"**Email:** {row.get('email') or '—'}  \n"
                    f"**Society:** {row.get('society_name') or '—'} · "
                    f"**Tower:** {row.get('tower_name') or '—'} · "
                    f"**Flat:** {row.get('flat_number') or '—'}"
                )

            can_edit = is_mine and not deleted and not editing
            can_delete = (admin or is_mine) and not deleted and not editing
            if can_edit and can_delete:
                edit_col, delete_col = st.columns(2)
                if edit_col.button("Edit", key=f"{key_prefix}_edit_btn_{row_id}"):
                    st.session_state[edit_key] = True
                    st.session_state[f"{key_prefix}_text_{row_id}"] = row.get("comment") or ""
                    st.rerun()
                if delete_col.button("Delete", key=f"{key_prefix}_delete_{row_id}"):
                    _delete_feedback(client, row_id)
            elif can_delete:
                if st.button("Delete", key=f"{key_prefix}_delete_{row_id}"):
                    _delete_feedback(client, row_id)
