from __future__ import annotations

import streamlit as st
from lib.supabase_client import SchemaClient

from lib.auth import get_profile


def render_admin_dashboard(client: SchemaClient) -> None:
    profile = get_profile()
    st.title("Admin Dashboard")
    st.caption(f"Signed in as {profile.get('full_name', 'Admin')}")

    tab_approvals, tab_users, tab_societies, tab_vendors, tab_events = st.tabs(
        ["Pending Approvals", "Users", "Societies & Towers", "Vendors", "Events"]
    )

    with tab_approvals:
        _render_pending_approvals(client)

    with tab_users:
        _render_users_crud(client)

    with tab_societies:
        _render_societies_crud(client)

    with tab_vendors:
        _render_vendors_crud(client)

    with tab_events:
        _render_events_crud(client)


def _render_pending_approvals(client: SchemaClient) -> None:
    st.subheader("Pending User Registrations")
    pending = (
        client.table("profiles")
        .select("*, societies(name), towers(name)")
        .eq("status", "pending")
        .order("created_at")
        .execute()
        .data
        or []
    )

    if not pending:
        st.info("No pending registrations.")
        return

    for user in pending:
        society = (user.get("societies") or {}).get("name", "—")
        tower = (user.get("towers") or {}).get("name", "—")
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(
                    f"**{user['full_name']}** ({user['role']})  \n"
                    f"{user['email']} · {user.get('phone') or '—'}  \n"
                    f"{society} · Tower {tower} · Flat {user.get('flat_number') or '—'}"
                )
            with col2:
                if st.button("Approve", key=f"approve_{user['id']}", type="primary"):
                    client.table("profiles").update({"status": "approved"}).eq(
                        "id", user["id"]
                    ).execute()
                    st.success(f"Approved {user['full_name']}")
                    st.rerun()
            with col3:
                if st.button("Reject", key=f"reject_{user['id']}"):
                    client.table("profiles").update({"status": "rejected"}).eq(
                        "id", user["id"]
                    ).execute()
                    st.warning(f"Rejected {user['full_name']}")
                    st.rerun()


def _render_users_crud(client: SchemaClient) -> None:
    st.subheader("Manage Users")

    users = (
        client.table("profiles")
        .select("*, societies(name), towers(name)")
        .neq("role", "admin")
        .order("full_name")
        .execute()
        .data
        or []
    )

    societies = client.table("societies").select("id, name").order("name").execute().data or []
    society_map = {s["name"]: s["id"] for s in societies}

    if not users:
        st.info("No users yet.")
        return

    edit_id = st.selectbox(
        "Select user to edit",
        options=[""] + [u["id"] for u in users],
        format_func=lambda uid: next(
            (f"{u['full_name']} ({u['email']})" for u in users if u["id"] == uid), "Select..."
        ),
    )

    if edit_id and society_map:
        user = next(u for u in users if u["id"] == edit_id)
        towers = (
            client.table("towers")
            .select("id, name")
            .eq("society_id", user.get("society_id") or "")
            .execute()
            .data
            or []
        )
        tower_map = {t["name"]: t["id"] for t in towers}
        current_society = (user.get("societies") or {}).get("name", "")
        current_tower = (user.get("towers") or {}).get("name", "")

        with st.form("edit_user"):
            full_name = st.text_input("Full Name", value=user["full_name"])
            phone = st.text_input("Phone", value=user.get("phone") or "")
            role = st.selectbox(
                "Role", ["resident", "tenant"], index=0 if user["role"] == "resident" else 1
            )
            status = st.selectbox(
                "Status",
                ["pending", "approved", "rejected"],
                index=["pending", "approved", "rejected"].index(user["status"]),
            )
            society_names = list(society_map.keys())
            society_name = st.selectbox(
                "Society",
                society_names,
                index=society_names.index(current_society) if current_society in society_map else 0,
            )
            tower_names = list(tower_map.keys())
            tower_name = (
                st.selectbox(
                    "Tower",
                    tower_names,
                    index=tower_names.index(current_tower) if current_tower in tower_names else 0,
                )
                if tower_names
                else None
            )
            flat_number = st.text_input("Flat Number", value=user.get("flat_number") or "")

            col1, col2 = st.columns(2)
            save = col1.form_submit_button("Save Changes", type="primary")
            delete = col2.form_submit_button("Delete User")

        if save:
            client.table("profiles").update(
                {
                    "full_name": full_name.strip(),
                    "phone": phone.strip() or None,
                    "role": role,
                    "status": status,
                    "society_id": society_map.get(society_name),
                    "tower_id": tower_map.get(tower_name) if tower_name else None,
                    "flat_number": flat_number.strip() or None,
                }
            ).eq("id", edit_id).execute()
            st.success("User updated.")
            st.rerun()

        if delete:
            client.table("profiles").delete().eq("id", edit_id).execute()
            st.success("User profile deleted.")
            st.rerun()


def _render_societies_crud(client: SchemaClient) -> None:
    st.subheader("Societies & Towers")

    col_add, col_list = st.columns([1, 2])

    with col_add:
        st.markdown("**Add Society**")
        with st.form("add_society"):
            name = st.text_input("Society Name")
            area = st.text_input("Area")
            road = st.text_input("Road")
            pin_code = st.text_input("Pin Code")
            if st.form_submit_button("Add Society", type="primary"):
                if name.strip():
                    client.table("societies").insert(
                        {
                            "name": name.strip(),
                            "area": area.strip(),
                            "road": road.strip(),
                            "pin_code": pin_code.strip(),
                        }
                    ).execute()
                    st.success("Society added.")
                    st.rerun()
                else:
                    st.error("Society name is required.")

        st.markdown("**Add Tower**")
        societies = client.table("societies").select("id, name").order("name").execute().data or []
        soc_map = {s["name"]: s["id"] for s in societies}
        with st.form("add_tower"):
            soc_name = st.selectbox("Society", list(soc_map.keys()) if soc_map else [""])
            tower_name = st.text_input("Tower Name")
            if st.form_submit_button("Add Tower", type="primary"):
                if tower_name.strip() and soc_name in soc_map:
                    client.table("towers").insert(
                        {"society_id": soc_map[soc_name], "name": tower_name.strip()}
                    ).execute()
                    st.success("Tower added.")
                    st.rerun()

    with col_list:
        st.markdown("**Existing Societies**")
        all_societies = (
            client.table("societies")
            .select("*, towers(id, name)")
            .order("name")
            .execute()
            .data
            or []
        )
        for soc in all_societies:
            with st.expander(f"{soc['name']} — {soc.get('area') or ''}"):
                st.write(f"Road: {soc.get('road') or '—'} | Pin: {soc.get('pin_code') or '—'}")
                towers = soc.get("towers") or []
                st.write(
                    "Towers: " + ", ".join(t["name"] for t in towers) if towers else "No towers yet."
                )

                with st.form(f"edit_society_{soc['id']}"):
                    new_name = st.text_input("Name", value=soc["name"], key=f"sn_{soc['id']}")
                    new_area = st.text_input("Area", value=soc.get("area") or "", key=f"sa_{soc['id']}")
                    new_road = st.text_input("Road", value=soc.get("road") or "", key=f"sr_{soc['id']}")
                    new_pin = st.text_input(
                        "Pin Code", value=soc.get("pin_code") or "", key=f"sp_{soc['id']}"
                    )
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("Update"):
                        client.table("societies").update(
                            {
                                "name": new_name,
                                "area": new_area,
                                "road": new_road,
                                "pin_code": new_pin,
                            }
                        ).eq("id", soc["id"]).execute()
                        st.rerun()
                    if c2.form_submit_button("Delete"):
                        client.table("societies").delete().eq("id", soc["id"]).execute()
                        st.rerun()


def _render_vendors_crud(client: SchemaClient) -> None:
    st.subheader("Vendors")
    profile = get_profile()
    societies = client.table("societies").select("id, name").order("name").execute().data or []
    soc_map = {s["name"]: s["id"] for s in societies}

    with st.form("add_vendor"):
        st.markdown("**Add Vendor**")
        c1, c2 = st.columns(2)
        v_name = c1.text_input("Vendor Name")
        category = c2.text_input("Category")
        c3, c4 = st.columns(2)
        contact_phone = c3.text_input("Phone")
        contact_email = c4.text_input("Email")
        description = st.text_area("Description")
        society_name = st.selectbox("Society", list(soc_map.keys()) if soc_map else [""])
        if st.form_submit_button("Add Vendor", type="primary"):
            if v_name.strip() and society_name in soc_map:
                client.table("vendors").insert(
                    {
                        "name": v_name.strip(),
                        "category": category.strip() or None,
                        "contact_phone": contact_phone.strip() or None,
                        "contact_email": contact_email.strip() or None,
                        "description": description.strip() or None,
                        "society_id": soc_map[society_name],
                        "added_by": profile["id"],
                    }
                ).execute()
                st.success("Vendor added.")
                st.rerun()

    vendors = (
        client.table("vendors")
        .select("*, societies(name), profiles(full_name)")
        .order("name")
        .execute()
        .data
        or []
    )

    for vendor in vendors:
        added_by = (vendor.get("profiles") or {}).get("full_name", "Unknown")
        society = (vendor.get("societies") or {}).get("name", "—")
        with st.expander(f"{vendor['name']} — {vendor.get('category') or 'General'}"):
            st.write(f"Society: {society} | Added by: {added_by}")
            st.write(
                f"Phone: {vendor.get('contact_phone') or '—'} | "
                f"Email: {vendor.get('contact_email') or '—'}"
            )
            if vendor.get("description"):
                st.write(vendor["description"])

            with st.form(f"edit_vendor_{vendor['id']}"):
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


def _render_events_crud(client: SchemaClient) -> None:
    st.subheader("Society Events")
    profile = get_profile()
    societies = client.table("societies").select("id, name").order("name").execute().data or []
    soc_map = {s["name"]: s["id"] for s in societies}

    with st.form("add_event"):
        st.markdown("**Create Event**")
        title = st.text_input("Title")
        description = st.text_area("Description")
        c1, c2 = st.columns(2)
        event_date = c1.date_input("Event Date")
        event_time = c2.time_input("Event Time")
        location = st.text_input("Location")
        society_name = st.selectbox("Society", list(soc_map.keys()) if soc_map else [""], key="event_soc")
        is_published = st.checkbox("Publish immediately", value=True)
        if st.form_submit_button("Create Event", type="primary"):
            if title.strip() and society_name in soc_map:
                from datetime import datetime

                dt = datetime.combine(event_date, event_time)
                client.table("events").insert(
                    {
                        "title": title.strip(),
                        "description": description.strip() or None,
                        "event_date": dt.isoformat(),
                        "location": location.strip() or None,
                        "society_id": soc_map[society_name],
                        "is_published": is_published,
                        "created_by": profile["id"],
                    }
                ).execute()
                st.success("Event created.")
                st.rerun()

    events = (
        client.table("events")
        .select("*, societies(name)")
        .order("event_date", desc=True)
        .execute()
        .data
        or []
    )

    for event in events:
        society = (event.get("societies") or {}).get("name", "—")
        status = "Published" if event.get("is_published") else "Draft"
        with st.expander(f"{event['title']} — {status}"):
            st.write(f"Society: {society}")
            st.write(f"Date: {event['event_date']} | Location: {event.get('location') or '—'}")
            if event.get("description"):
                st.write(event["description"])

            with st.form(f"edit_event_{event['id']}"):
                et = st.text_input("Title", value=event["title"])
                ed = st.text_area("Description", value=event.get("description") or "")
                ep = st.checkbox("Published", value=event.get("is_published", False))
                c1, c2 = st.columns(2)
                if c1.form_submit_button("Update"):
                    client.table("events").update(
                        {"title": et, "description": ed, "is_published": ep}
                    ).eq("id", event["id"]).execute()
                    st.rerun()
                if c2.form_submit_button("Delete"):
                    client.table("events").delete().eq("id", event["id"]).execute()
                    st.rerun()
