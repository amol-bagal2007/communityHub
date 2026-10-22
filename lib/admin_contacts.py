from __future__ import annotations

import streamlit as st

from lib.auth import is_admin
from lib.contact_privacy import HIDDEN_CONTACT, format_visible_contact
from lib.profile_utils import format_name
from lib.supabase_client import SchemaClient


def load_admin_contacts(client: SchemaClient) -> tuple[list[dict], str | None]:
    """
    Load approved admin name/phone/email (works for anon via RPC).
    Returns (rows, error_message).
    """
    try:
        rows = client.raw.rpc("get_admin_contacts").execute().data or []
        contacts = [row for row in rows if isinstance(row, dict)]
        return contacts, None
    except Exception as exc:
        message = str(exc)
        if (
            "get_admin_contacts" in message
            or "PGRST202" in message
            or "schema cache" in message.lower()
        ):
            return [], (
                "Admin contacts RPC is missing. "
                "Run Supabase migration `027_admin_contacts.sql`, then refresh."
            )
        # Fallback for sessions that can read admin profiles via RLS.
        try:
            rows = (
                client.table("profiles")
                .select("first_name, last_name, title, phone, email, mask_phone")
                .eq("role", "admin")
                .eq("status", "approved")
                .order("first_name")
                .execute()
                .data
                or []
            )
            if rows:
                return rows, None
        except Exception:
            pass
        return [], f"Could not load admin contacts: {exc}"


def format_admin_contact_offline(admins: list[dict]) -> str:
    """Compact offline contact line for disclaimer point 6."""
    if not admins:
        return "your society administrator (details shown under **Contact** after login)"

    parts: list[str] = []
    for admin in admins:
        name = format_name(admin, "Administrator")
        phone = format_visible_contact(
            admin.get("phone"),
            masked=bool(admin.get("mask_phone")),
        )
        email = (admin.get("email") or "").strip() or "—"
        parts.append(f"**{name}** — {phone} — {email}")
    return "; ".join(parts)


def render_admin_contacts(client: SchemaClient, *, heading: str = "Contact Administrator") -> None:
    st.subheader(heading)
    st.caption(
        "If you have any issue with CommunityHub, contact the administrator below."
    )
    admins, error = load_admin_contacts(client)
    if error:
        st.warning(error)
        return
    if not admins:
        st.info(
            "No approved admin profile found with contact details. "
            "Sign in as admin and save **name**, **phone**, and **email** on Profile "
            "(role must be admin, status approved)."
        )
        return

    for admin in admins:
        name = format_name(admin, "Administrator")
        phone = format_visible_contact(
            admin.get("phone"),
            masked=bool(admin.get("mask_phone")),
            viewer_is_admin=is_admin(),
        )
        email = (admin.get("email") or "").strip()
        with st.container(border=True):
            title = (admin.get("title") or "").strip()
            st.markdown(f"**{title + ' ' if title else ''}{name}**")
            raw_phone = (admin.get("phone") or "").strip()
            if phone == HIDDEN_CONTACT or not raw_phone:
                st.write(f"Mobile: {phone or '—'}")
            else:
                st.markdown(f"Mobile: [{phone}](tel:{raw_phone})")
            if email:
                st.markdown(f"Email: [{email}](mailto:{email})")
            else:
                st.write("Email: —")
