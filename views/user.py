from __future__ import annotations

from datetime import datetime

import streamlit as st
from lib.supabase_client import SchemaClient

from lib.auth import get_profile


def render_user_dashboard(client: SchemaClient) -> None:
    profile = get_profile()
    st.title("CommunityHub")
    st.caption(f"Welcome, {profile.get('full_name', 'Resident')}")

    tab_events, tab_vendors, tab_society, tab_profile = st.tabs(
        ["Events", "Vendors", "My Society", "Profile"]
    )

    with tab_events:
        _render_events(client, profile)

    with tab_vendors:
        _render_vendors(client, profile)

    with tab_society:
        _render_society_info(client, profile)

    with tab_profile:
        _render_profile(client, profile)


def _render_events(client: SchemaClient, profile: dict) -> None:
    st.subheader("Upcoming Events")
    society_id = profile.get("society_id")
    if not society_id:
        st.info("No society linked to your profile.")
        return

    events = (
        client.table("events")
        .select("*")
        .eq("society_id", society_id)
        .eq("is_published", True)
        .order("event_date")
        .execute()
        .data
        or []
    )

    if not events:
        st.info("No published events yet. Check back later!")
        return

    now = datetime.now().astimezone()
    for event in events:
        event_dt = datetime.fromisoformat(event["event_date"].replace("Z", "+00:00"))
        is_past = event_dt < now
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"### {event['title']}")
                if event.get("description"):
                    st.write(event["description"])
                st.caption(
                    f"📅 {event_dt.strftime('%a, %d %b %Y · %I:%M %p')}  "
                    f"| 📍 {event.get('location') or 'TBA'}"
                )
            with col2:
                if is_past:
                    st.markdown("Past")
                else:
                    st.success("Upcoming")


def _render_vendors(client: SchemaClient, profile: dict) -> None:
    st.subheader("Community Vendors")
    society_id = profile.get("society_id")
    if not society_id:
        st.info("No society linked to your profile.")
        return

    with st.expander("Add a Vendor"):
        with st.form("user_add_vendor"):
            name = st.text_input("Vendor Name *")
            category = st.text_input("Category")
            phone = st.text_input("Phone")
            email = st.text_input("Email")
            description = st.text_area("Description")
            if st.form_submit_button("Submit Vendor", type="primary"):
                if name.strip():
                    client.table("vendors").insert(
                        {
                            "name": name.strip(),
                            "category": category.strip() or None,
                            "contact_phone": phone.strip() or None,
                            "contact_email": email.strip() or None,
                            "description": description.strip() or None,
                            "society_id": society_id,
                            "added_by": profile["id"],
                        }
                    ).execute()
                    st.success("Vendor added!")
                    st.rerun()
                else:
                    st.error("Vendor name is required.")

    vendors = (
        client.table("vendors")
        .select("*, profiles(full_name)")
        .eq("society_id", society_id)
        .order("name")
        .execute()
        .data
        or []
    )

    if not vendors:
        st.info("No vendors listed yet.")
        return

    for vendor in vendors:
        added_by = (vendor.get("profiles") or {}).get("full_name", "Community")
        can_edit = vendor.get("added_by") == profile["id"]

        with st.container(border=True):
            st.markdown(f"**{vendor['name']}** — {vendor.get('category') or 'General'}")
            st.caption(f"Added by {added_by}")
            if vendor.get("contact_phone") or vendor.get("contact_email"):
                st.write(
                    f"📞 {vendor.get('contact_phone') or '—'}  "
                    f"| ✉️ {vendor.get('contact_email') or '—'}"
                )
            if vendor.get("description"):
                st.write(vendor["description"])

            if can_edit:
                with st.form(f"user_edit_vendor_{vendor['id']}"):
                    en = st.text_input("Name", value=vendor["name"])
                    ec = st.text_input("Category", value=vendor.get("category") or "")
                    ep = st.text_input("Phone", value=vendor.get("contact_phone") or "")
                    ee = st.text_input("Email", value=vendor.get("contact_email") or "")
                    ed = st.text_area("Description", value=vendor.get("description") or "")
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("Update"):
                        client.table("vendors").update(
                            {
                                "name": en,
                                "category": ec,
                                "contact_phone": ep,
                                "contact_email": ee,
                                "description": ed,
                            }
                        ).eq("id", vendor["id"]).execute()
                        st.rerun()
                    if c2.form_submit_button("Delete"):
                        client.table("vendors").delete().eq("id", vendor["id"]).execute()
                        st.rerun()


def _render_society_info(client: SchemaClient, profile: dict) -> None:
    st.subheader("Society Details")
    society_id = profile.get("society_id")
    if not society_id:
        st.info("No society linked to your profile.")
        return

    society = (
        client.table("societies")
        .select("*, towers(name)")
        .eq("id", society_id)
        .single()
        .execute()
        .data
    )
    tower = None
    if profile.get("tower_id"):
        tower = (
            client.table("towers")
            .select("name")
            .eq("id", profile["tower_id"])
            .single()
            .execute()
            .data
        )

    if society:
        st.markdown(f"### {society['name']}")
        st.write(f"**Area:** {society.get('area') or '—'}")
        st.write(f"**Road:** {society.get('road') or '—'}")
        st.write(f"**Pin Code:** {society.get('pin_code') or '—'}")
        towers = society.get("towers") or []
        if towers:
            st.write("**Towers:** " + ", ".join(t["name"] for t in towers))

    if tower:
        st.divider()
        st.write(f"**Your Tower:** {tower['name']}")
        st.write(f"**Flat:** {profile.get('flat_number') or '—'}")


def _render_profile(client: SchemaClient, profile: dict) -> None:
    st.subheader("My Profile")

    with st.form("update_profile"):
        full_name = st.text_input("Full Name", value=profile.get("full_name") or "")
        phone = st.text_input("Phone", value=profile.get("phone") or "")
        st.text_input("Email", value=profile.get("email") or "", disabled=True)
        st.text_input("Role", value=profile.get("role") or "", disabled=True)
        st.text_input("Status", value=profile.get("status") or "", disabled=True)

        if st.form_submit_button("Update Profile", type="primary"):
            client.table("profiles").update(
                {"full_name": full_name.strip(), "phone": phone.strip() or None}
            ).eq("id", profile["id"]).execute()
            st.success("Profile updated.")
            st.rerun()
