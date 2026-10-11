from __future__ import annotations

import json

import streamlit as st

from lib.supabase_client import SchemaClient


def load_interest_groups(client: SchemaClient) -> list[dict]:
    try:
        return (
            client.table("interest_groups")
            .select("id, name")
            .order("name")
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def decode_group_interest_ids(value: str | None) -> list[str]:
    """Parse profiles.group_interests JSON UUID list; ignore legacy free text."""
    text = (value or "").strip()
    if not text:
        return []
    if not text.startswith("["):
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if item]


def encode_group_interest_ids(ids: list[str]) -> str | None:
    cleaned = sorted({str(item).strip() for item in ids if str(item).strip()})
    if not cleaned:
        return None
    return json.dumps(cleaned)


def interest_group_names(groups: list[dict], selected_ids: list[str]) -> str:
    id_to_name = {g["id"]: g["name"] for g in groups}
    names = [id_to_name[i] for i in selected_ids if i in id_to_name]
    return ", ".join(names) if names else "—"


def render_interest_groups_crud(client: SchemaClient) -> None:
    st.markdown("**Interested in groups — options**")
    st.caption(
        "These options appear as checkboxes on Sign Up and Profile. "
        "Members can select one or more."
    )

    with st.form("add_interest_group"):
        name = st.text_input("New group interest option")
        if st.form_submit_button("Add option", type="primary"):
            if not name.strip():
                st.error("Name is required.")
            else:
                try:
                    client.table("interest_groups").insert(
                        {"name": name.strip()}
                    ).execute()
                    st.success("Option added.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not add option (run migration 025): {exc}")

    groups = load_interest_groups(client)
    if not groups:
        st.info("No interest group options yet.")
        return

    for group in groups:
        with st.expander(group["name"]):
            with st.form(f"edit_interest_group_{group['id']}"):
                new_name = st.text_input(
                    "Name",
                    value=group["name"],
                    key=f"interest_group_name_{group['id']}",
                )
                c1, c2 = st.columns(2)
                if c1.form_submit_button("Update"):
                    if not new_name.strip():
                        st.error("Name is required.")
                    else:
                        try:
                            client.table("interest_groups").update(
                                {"name": new_name.strip()}
                            ).eq("id", group["id"]).execute()
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not update: {exc}")
                if c2.form_submit_button("Delete"):
                    try:
                        client.table("interest_groups").delete().eq(
                            "id", group["id"]
                        ).execute()
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not delete: {exc}")
