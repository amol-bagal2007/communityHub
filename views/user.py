from __future__ import annotations

from datetime import date, datetime

import streamlit as st
from lib.supabase_client import SchemaClient

from lib.auth import PROFILE_KEY, fetch_profile, get_profile
from lib.profile_utils import format_name, render_recommended_by_readonly
from lib.member_groups import load_member_groups
from lib.member_sub_groups import render_group_sub_group_fields
from lib.profile_update import (
    build_profile_update_payload,
    collect_profile_update_errors,
    profile_has_changes,
)
from lib.roles import ROLE_TENANT, SIGNUP_ROLES, is_owner, role_label
from lib.tenant_utils import parse_profile_date
from lib.titles import TITLE_OPTIONS
from lib.user_demographics import MAX_AGE, MIN_AGE, SEX_OPTIONS
from lib.vendor_categories import (
    category_display_name,
    load_vendor_categories,
    render_category_select,
)


def render_user_dashboard(client: SchemaClient) -> None:
    profile = get_profile()
    st.title("CommunityHub")
    st.caption(f"Welcome, {format_name(profile, 'Resident')}")

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
    recommender_name = format_name(profile)
    categories = load_vendor_categories(client)
    if not society_id:
        st.info("No society linked to your profile.")
        return

    with st.expander("Add a Vendor"):
        with st.form("user_add_vendor"):
            c1, c2 = st.columns(2)
            first_name = c1.text_input("Vendor First Name *")
            last_name = c2.text_input("Vendor Last Name *")
            render_recommended_by_readonly(recommender_name)
            category_id = render_category_select(categories, key="user_add_vendor_category")
            phone = st.text_input("Phone")
            email = st.text_input("Email")
            description = st.text_area("Description")
            if st.form_submit_button("Submit Vendor", type="primary"):
                if not first_name.strip():
                    st.error("Vendor first name is required.")
                elif not last_name.strip():
                    st.error("Vendor last name is required.")
                elif not category_id:
                    st.error("Select a category.")
                else:
                    client.table("vendors").insert(
                        {
                            "first_name": first_name.strip(),
                            "last_name": last_name.strip(),
                            "recommended_by": recommender_name,
                            "category_id": category_id,
                            "contact_phone": phone.strip() or None,
                            "contact_email": email.strip() or None,
                            "description": description.strip() or None,
                            "society_id": society_id,
                            "added_by": profile["id"],
                        }
                    ).execute()
                    st.success("Vendor added!")
                    st.rerun()

    vendors = (
        client.table("vendors")
        .select("*, profiles(first_name, last_name), vendor_categories(name)")
        .eq("society_id", society_id)
        .order("first_name")
        .execute()
        .data
        or []
    )

    if not vendors:
        st.info("No vendors listed yet.")
        return

    for vendor in vendors:
        added_by = format_name(vendor.get("profiles"), "Community")
        can_edit = vendor.get("added_by") == profile["id"]
        vendor_label = format_name(vendor, "Vendor")

        with st.container(border=True):
            st.markdown(f"**{vendor_label}** — {category_display_name(vendor)}")
            st.caption(f"Added by {added_by}")
            if vendor.get("recommended_by"):
                st.caption(f"Recommended by {vendor['recommended_by']}")
            if vendor.get("contact_phone") or vendor.get("contact_email"):
                st.write(
                    f"📞 {vendor.get('contact_phone') or '—'}  "
                    f"| ✉️ {vendor.get('contact_email') or '—'}"
                )
            if vendor.get("description"):
                st.write(vendor["description"])

            if can_edit:
                with st.form(f"user_edit_vendor_{vendor['id']}"):
                    c1, c2 = st.columns(2)
                    fn = c1.text_input("Vendor First Name", value=vendor.get("first_name") or "")
                    ln = c2.text_input("Vendor Last Name", value=vendor.get("last_name") or "")
                    render_recommended_by_readonly(
                        vendor.get("recommended_by") or recommender_name
                    )
                    category_id = render_category_select(
                        categories,
                        key=f"user_edit_vendor_category_{vendor['id']}",
                        current_category_id=vendor.get("category_id"),
                    )
                    ep = st.text_input("Phone", value=vendor.get("contact_phone") or "")
                    ee = st.text_input("Email", value=vendor.get("contact_email") or "")
                    ed = st.text_area("Description", value=vendor.get("description") or "")
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("Update"):
                        client.table("vendors").update(
                            {
                                "first_name": fn.strip(),
                                "last_name": ln.strip(),
                                "category_id": category_id,
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


def _on_profile_society_change() -> None:
    st.session_state.profile_tower = ""


def _render_profile(client: SchemaClient, profile: dict) -> None:
    st.subheader("My Profile")
    st.caption(
        "You can update any field except Status. Saving changes sends your profile "
        "to the admin for approval."
    )

    groups = load_member_groups(client)
    societies = client.table("societies").select("id, name").order("name").execute().data or []
    society_map = {s["name"]: s["id"] for s in societies}
    society_id_to_name = {s["id"]: s["name"] for s in societies}
    current_society_name = society_id_to_name.get(profile.get("society_id"), "")

    society_name = st.selectbox(
        "Society *",
        options=[""] + list(society_map.keys()),
        index=(
            (list(society_map.keys()).index(current_society_name) + 1)
            if current_society_name in society_map
            else 0
        ),
        format_func=lambda value: "Select society..." if value == "" else value,
        key="profile_society",
        on_change=_on_profile_society_change,
    )
    selected_society_id = society_map.get(society_name)

    tower_map: dict[str, str] = {}
    if selected_society_id:
        towers = (
            client.table("towers")
            .select("id, name")
            .eq("society_id", selected_society_id)
            .order("name")
            .execute()
            .data
            or []
        )
        tower_map = {t["name"]: t["id"] for t in towers}

    tower_id_to_name = {tid: name for name, tid in tower_map.items()}
    current_tower_name = tower_id_to_name.get(profile.get("tower_id"), "")

    tower_name = st.selectbox(
        "Tower *",
        options=[""] + list(tower_map.keys()),
        index=(
            (list(tower_map.keys()).index(current_tower_name) + 1)
            if current_tower_name in tower_map
            else 0
        ),
        format_func=lambda value: "Select tower..." if value == "" else value,
        disabled=not selected_society_id,
        key="profile_tower",
    )
    selected_tower_id = tower_map.get(tower_name)

    role = st.selectbox(
        "I am a *",
        SIGNUP_ROLES,
        format_func=role_label,
        index=0 if is_owner(profile.get("role")) else 1,
        key="profile_role",
    )

    staying_within_society = False
    if is_owner(role):
        staying_within_society = st.checkbox(
            "Staying within Society *",
            value=bool(profile.get("staying_within_society")),
            key="profile_staying_within_society",
        )

    tenant_expiry = None
    if role == ROLE_TENANT:
        current_expiry = parse_profile_date(profile.get("tenant_expiry_date"))
        tenant_expiry = st.date_input(
            "Tenant Expiry Date *",
            value=current_expiry or date.today(),
            min_value=date.today(),
            key="profile_tenant_expiry",
        )

    current_title = profile.get("title") or ""
    title_index = TITLE_OPTIONS.index(current_title) if current_title in TITLE_OPTIONS else 0

    email = st.text_input("Email *", value=profile.get("email") or "", key="profile_email")
    member_group_id, member_sub_group_id = render_group_sub_group_fields(
        client,
        groups,
        group_key="profile_member_group",
        sub_group_key="profile_member_sub_group",
        current_group_id=profile.get("member_group_id"),
        current_sub_group_id=profile.get("member_sub_group_id"),
    )

    with st.form("update_profile"):
        title = st.selectbox("Title *", TITLE_OPTIONS, index=title_index)
        c1, c2 = st.columns(2)
        first_name = c1.text_input("First Name *", value=profile.get("first_name") or "")
        last_name = c2.text_input("Last Name *", value=profile.get("last_name") or "")
        current_sex = profile.get("sex") or ""
        sex_index = SEX_OPTIONS.index(current_sex) if current_sex in SEX_OPTIONS else 0
        c3, c4 = st.columns(2)
        sex = c3.selectbox("Sex *", SEX_OPTIONS, index=sex_index)
        age = c4.number_input(
            "Age *",
            min_value=MIN_AGE,
            max_value=MAX_AGE,
            value=int(profile.get("age") or MIN_AGE),
            step=1,
        )
        phone = st.text_input("Phone", value=profile.get("phone") or "")
        flat_number = st.text_input("Flat / Unit Number *", value=profile.get("flat_number") or "")
        st.text_input("Status", value=(profile.get("status") or "").title(), disabled=True)

        submitted = st.form_submit_button("Save & Submit for Approval", type="primary")

    if submitted:
        errors = collect_profile_update_errors(
            title=title,
            first_name=first_name,
            last_name=last_name,
            sex=sex,
            age=age,
            role=role,
            flat_number=flat_number,
            staying_within_society=staying_within_society,
            tenant_expiry=tenant_expiry,
            society_id=selected_society_id,
            tower_id=selected_tower_id,
            email=email,
        )
        if errors:
            for err in errors:
                st.error(err)
            return

        payload = build_profile_update_payload(
            title=title,
            first_name=first_name,
            last_name=last_name,
            sex=sex,
            age=age,
            phone=phone,
            email=email,
            member_group_id=member_group_id,
            member_sub_group_id=member_sub_group_id,
            role=role,
            society_id=selected_society_id,
            tower_id=selected_tower_id,
            flat_number=flat_number,
            staying_within_society=staying_within_society,
            tenant_expiry=tenant_expiry,
            for_reapproval=False,
        )

        if not profile_has_changes(profile, payload):
            st.info("No changes to save.")
            return

        payload["status"] = "pending"

        try:
            if email.strip().lower() != (profile.get("email") or "").lower():
                client.auth.update_user({"email": email.strip()})
        except Exception as exc:
            st.error(f"Could not update login email: {exc}")
            return

        try:
            client.table("profiles").update(payload).eq("id", profile["id"]).execute()
        except Exception as exc:
            st.error(f"Could not update profile: {exc}")
            return

        refreshed = fetch_profile(client)
        if refreshed:
            st.session_state[PROFILE_KEY] = refreshed
        st.success("Profile updated and sent to admin for approval.")
        st.rerun()
