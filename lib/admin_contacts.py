from __future__ import annotations

import streamlit as st

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
                .select("first_name, last_name, title, phone, email")
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
        phone = (admin.get("phone") or "").strip() or "—"
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
        phone = (admin.get("phone") or "").strip()
        email = (admin.get("email") or "").strip()
        with st.container(border=True):
            title = (admin.get("title") or "").strip()
            st.markdown(f"**{title + ' ' if title else ''}{name}**")
            if phone:
                st.markdown(f"Mobile: [{phone}](tel:{phone})")
            else:
                st.write("Mobile: —")
            if email:
                st.markdown(f"Email: [{email}](mailto:{email})")
            else:
                st.write("Email: —")
