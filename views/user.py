from __future__ import annotations

from datetime import date, datetime, time

import streamlit as st
from lib.supabase_client import SchemaClient

from lib.auth import PROFILE_KEY, fetch_profile, get_profile
from lib.event_responses import (
    INTEREST_INTERESTED,
    INTEREST_NOT_INTERESTED,
    PARTICIPATION_ROLES,
    interest_counts_caption,
    interest_label,
    load_event_responses,
    load_my_event_response,
    render_response_summary,
    role_label,
    upsert_event_response,
)
from lib.event_schedule import format_clock, format_event_schedule
from lib.profile_utils import format_name, render_recommended_by_readonly
from lib.member_groups import load_member_groups
from lib.member_sub_groups import render_group_sub_group_fields
from lib.profile_extended_fields import (
    render_extended_profile_fields,
    validate_extended_profile_fields,
)
from lib.profile_update import (
    build_profile_update_payload,
    collect_profile_update_errors,
    profile_has_changes,
)
from lib.roles import ROLE_TENANT, SIGNUP_ROLES, is_owner, role_label as member_role_label
from lib.tenant_utils import parse_profile_date
from lib.titles import TITLE_OPTIONS, is_valid_title
from lib.user_demographics import MAX_AGE, MIN_AGE, SEX_OPTIONS, normalize_age, sex_age_validation_errors
from lib.validation import validate_password
from lib.vendor_categories import (
    category_display_name,
    load_vendor_categories,
    render_category_select,
    render_vendor_filter_and_page,
)
from lib.vendor_ratings import (
    ensure_vendor_recommendation,
    feedback_caption,
    find_my_rating,
    load_vendor_ratings,
    load_vendor_recommendations,
    render_rating_form,
    render_vendor_reviews,
    summarize_vendor_feedback,
    user_has_recommended,
)
from lib.admin_contacts import render_admin_contacts
from lib.local_businesses import render_local_businesses
from lib.visibility import (
    FLAG_EVENTS_TAB,
    FLAG_LOCAL_BUSINESS_TAB,
    FLAG_VENDORS_TAB,
    is_feature_enabled,
    load_societies,
    load_towers,
)


def render_user_dashboard(client: SchemaClient) -> None:
    profile = get_profile()
    st.title("CommunityHub")
    st.caption(f"Welcome, {format_name(profile, 'Resident')}")

    show_events = is_feature_enabled(client, FLAG_EVENTS_TAB, default=False)
    show_vendors = is_feature_enabled(client, FLAG_VENDORS_TAB, default=False)
    show_local_business = is_feature_enabled(
        client, FLAG_LOCAL_BUSINESS_TAB, default=False
    )

    tab_defs: list[tuple[str, str]] = []
    if show_events:
        tab_defs.append(("Events", "events"))
    if show_vendors:
        tab_defs.append(("Vendors", "vendors"))
    if show_local_business:
        tab_defs.append(("Local Business", "local_business"))
    tab_defs.append(("My Society", "society"))
    tab_defs.append(("Contact", "contact"))

    tabs = st.tabs([label for label, _ in tab_defs])
    for tab, (_, kind) in zip(tabs, tab_defs):
        with tab:
            if kind == "events":
                _render_events(client, profile)
            elif kind == "vendors":
                _render_vendors(client, profile)
            elif kind == "local_business":
                render_local_businesses(client, profile, admin=False)
            elif kind == "contact":
                render_admin_contacts(client)
            else:
                _render_society_info(client, profile)


def render_profile_page(client: SchemaClient, profile: dict) -> None:
    """Public entry point for the sidebar Profile screen."""
    _render_profile(client, profile)


def _render_events(client: SchemaClient, profile: dict) -> None:
    st.subheader("Upcoming Events")
    society_id = profile.get("society_id")
    if not society_id:
        st.info("No society linked to your profile.")
        return

    today_start = datetime.combine(date.today(), time.min).astimezone()
    events = (
        client.table("events")
        .select("*")
        .eq("society_id", society_id)
        .eq("is_published", True)
        .gte("event_date", today_start.isoformat())
        .order("event_date")
        .execute()
        .data
        or []
    )

    if not events:
        st.info("No events from today onwards yet. Check back later!")
        return

    for event in events:
        event_dt = datetime.fromisoformat(event["event_date"].replace("Z", "+00:00"))
        open_key = f"user_event_open_{event['id']}"
        pending_key = f"user_event_pending_interest_{event['id']}"
        responses = load_event_responses(client, event["id"])

        with st.container(border=True):
            summary, action = st.columns([5, 1])
            summary.markdown(f"**{event['title']}**")
            summary.caption(
                f"📅 {event_dt.strftime('%a, %d %b %Y')} · "
                f"{format_event_schedule(event)}  "
                f"| 📍 {event.get('location') or 'TBA'}"
            )
            summary.caption(interest_counts_caption(responses))
            if action.button(
                "Hide" if st.session_state.get(open_key) else "View",
                key=f"user_event_view_{event['id']}",
                use_container_width=True,
            ):
                st.session_state[open_key] = not st.session_state.get(open_key, False)
                st.rerun()

            if not st.session_state.get(open_key):
                continue

            st.write(
                f"**From:** {format_clock(event_dt.time())}  ·  "
                f"**To:** {format_clock(event.get('end_time'))}"
            )
            if event.get("break_start_time") and event.get("break_end_time"):
                st.write(
                    f"**Break:** {format_clock(event.get('break_start_time'))} – "
                    f"{format_clock(event.get('break_end_time'))}"
                )
            if event.get("description"):
                st.write(event["description"])

            render_response_summary(responses)

            my_response = load_my_event_response(client, event["id"], profile["id"])
            if my_response:
                st.info(
                    f"Your response: {interest_label(my_response.get('interest'))}"
                    + (
                        f" · {role_label(my_response.get('participation_role'))}"
                        if my_response.get("participation_role")
                        else ""
                    )
                )

            c1, c2 = st.columns(2)
            if c1.button("Interested", key=f"event_interested_{event['id']}"):
                st.session_state[pending_key] = INTEREST_INTERESTED
                st.rerun()
            if c2.button("Not Interested", key=f"event_not_interested_{event['id']}"):
                try:
                    upsert_event_response(
                        client,
                        event_id=event["id"],
                        user_id=profile["id"],
                        interest=INTEREST_NOT_INTERESTED,
                        participation_role=None,
                    )
                    st.session_state.pop(pending_key, None)
                    st.success("Marked as Not Interested.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not save response: {exc}")

            if st.session_state.get(pending_key) == INTEREST_INTERESTED:
                st.markdown("**How would you like to participate?**")
                participation = st.radio(
                    "Participation role *",
                    PARTICIPATION_ROLES,
                    format_func=role_label,
                    horizontal=True,
                    key=f"event_role_{event['id']}",
                )
                if st.button(
                    "Confirm Interest",
                    type="primary",
                    key=f"event_confirm_interest_{event['id']}",
                ):
                    try:
                        upsert_event_response(
                            client,
                            event_id=event["id"],
                            user_id=profile["id"],
                            interest=INTEREST_INTERESTED,
                            participation_role=participation,
                        )
                        st.session_state.pop(pending_key, None)
                        st.success(
                            f"Marked as Interested ({role_label(participation)})."
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not save response: {exc}")


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
                    inserted = (
                        client.table("vendors")
                        .insert(
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
                        )
                        .execute()
                        .data
                        or []
                    )
                    if inserted:
                        ensure_vendor_recommendation(
                            client,
                            vendor_id=inserted[0]["id"],
                            user_id=profile["id"],
                        )
                    st.success("Vendor added!")
                    st.rerun()

    vendors = (
        client.table("vendors")
        .select("*, profiles(first_name, last_name), vendor_categories(name)")
        .eq("society_id", society_id)
        .order("first_name")
        .order("last_name")
        .execute()
        .data
        or []
    )

    page_vendors = render_vendor_filter_and_page(
        categories,
        vendors,
        key_prefix="user_vendors",
    )
    if not page_vendors:
        return

    vendor_ids = [v["id"] for v in page_vendors]
    try:
        ratings = load_vendor_ratings(client, vendor_ids)
        recommendations = load_vendor_recommendations(client, vendor_ids)
        feedback = summarize_vendor_feedback(ratings, recommendations)
    except Exception as exc:
        st.warning(
            f"Vendor ratings/recommendations unavailable (run migration 022): {exc}"
        )
        ratings = []
        feedback = {}

    ratings_by_vendor: dict[str, list] = {}
    for row in ratings:
        ratings_by_vendor.setdefault(row["vendor_id"], []).append(row)

    for vendor in page_vendors:
        added_by = format_name(vendor.get("profiles"), "Community")
        can_edit = vendor.get("added_by") == profile["id"]
        vendor_label = format_name(vendor, "Vendor")
        open_key = f"user_vendor_open_{vendor['id']}"
        summary_data = feedback.get(vendor["id"])

        with st.container(border=True):
            summary, action = st.columns([5, 1])
            summary.markdown(f"**{vendor_label}** — {category_display_name(vendor)}")
            summary.caption(feedback_caption(summary_data))
            if action.button(
                "Hide" if st.session_state.get(open_key) else "View",
                key=f"user_vendor_view_{vendor['id']}",
                use_container_width=True,
            ):
                st.session_state[open_key] = not st.session_state.get(open_key, False)
                st.rerun()

            if not st.session_state.get(open_key):
                continue

            st.caption(f"Added by {added_by}")
            if vendor.get("recommended_by"):
                st.caption(f"Originally recommended by {vendor['recommended_by']}")
            st.write(feedback_caption(summary_data))
            if vendor.get("contact_phone") or vendor.get("contact_email"):
                st.write(
                    f"📞 {vendor.get('contact_phone') or '—'}  "
                    f"| ✉️ {vendor.get('contact_email') or '—'}"
                )
            if vendor.get("description"):
                st.write(vendor["description"])

            if not user_has_recommended(summary_data, profile["id"]):
                if st.button(
                    "Recommend this Vendor",
                    key=f"user_recommend_vendor_{vendor['id']}",
                ):
                    err = ensure_vendor_recommendation(
                        client,
                        vendor_id=vendor["id"],
                        user_id=profile["id"],
                    )
                    if err:
                        st.error(err)
                    else:
                        st.success("Thanks — you recommended this vendor.")
                        st.rerun()
            else:
                st.caption("You have recommended this vendor.")

            vendor_ratings = ratings_by_vendor.get(vendor["id"], [])
            render_vendor_reviews(vendor_ratings)
            my_rating = find_my_rating(vendor_ratings, profile["id"])
            render_rating_form(
                client,
                vendor_id=vendor["id"],
                user_id=profile["id"],
                existing=my_rating,
                key_prefix=f"user_vendor_{vendor['id']}",
            )

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
    is_admin_user = profile.get("role") == "admin"
    st.subheader("My Profile")
    st.caption(
        "User ID cannot be changed. "
        + (
            "Update your details below and save."
            if is_admin_user
            else "Saving changes (except password) sends your profile to the admin for approval."
        )
    )

    st.text_input(
        "User ID",
        value=str(profile.get("id") or ""),
        disabled=True,
        help="System user id — not editable.",
        key="profile_user_id_display",
    )

    groups = load_member_groups(client)
    societies = load_societies(
        client,
        enabled_only=True,
        include_id=profile.get("society_id"),
    )
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
        towers = load_towers(
            client,
            selected_society_id,
            enabled_only=True,
            include_id=profile.get("tower_id"),
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

    if is_admin_user:
        st.text_input("Role", value="Admin", disabled=True, key="profile_role_admin_display")
        role = "admin"
        staying_within_society = False
        tenant_expiry = None
    else:
        role = st.selectbox(
            "I am a *",
            SIGNUP_ROLES,
            format_func=member_role_label,
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
    extended_fields = render_extended_profile_fields(
        client,
        key_prefix="profile",
        current=profile,
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
        flat_number = st.text_input(
            "Flat / Unit Number *" if not is_admin_user else "Flat / Unit Number",
            value=profile.get("flat_number") or "",
        )
        st.text_input("Status", value=(profile.get("status") or "").title(), disabled=True)

        save_label = "Save Profile" if is_admin_user else "Save & Submit for Approval"
        submitted = st.form_submit_button(save_label, type="primary")

    st.markdown("**Change Password**")
    st.caption("Optional. User ID stays the same; only your login password changes.")
    with st.form("update_profile_password"):
        new_password = st.text_input(
            "New Password",
            type="password",
            help="At least 7 characters with at least one letter and one number.",
        )
        confirm_password = st.text_input("Confirm New Password", type="password")
        password_submitted = st.form_submit_button("Update Password", type="secondary")

    if password_submitted:
        pwd_errors = []
        pwd_error = validate_password(new_password)
        if pwd_error:
            pwd_errors.append(pwd_error)
        if new_password != confirm_password:
            pwd_errors.append("Passwords do not match.")
        if pwd_errors:
            for err in pwd_errors:
                st.error(err)
        else:
            try:
                client.auth.update_user({"password": new_password})
                st.success("Password updated successfully.")
            except Exception as exc:
                st.error(f"Could not update password: {exc}")

    if submitted:
        if is_admin_user:
            errors = []
            if not is_valid_title(title):
                errors.append("Please select a title.")
            if not first_name.strip():
                errors.append("First name is required.")
            if not last_name.strip():
                errors.append("Last name is required.")
            errors.extend(sex_age_validation_errors(sex, age))
            if not email.strip():
                errors.append("Email is required.")
            errors.extend(validate_extended_profile_fields(extended_fields))
            if errors:
                for err in errors:
                    st.error(err)
                return

            payload = {
                "title": title,
                "first_name": first_name.strip(),
                "last_name": last_name.strip(),
                "sex": sex,
                "age": normalize_age(age),
                "phone": phone.strip() or None,
                "email": email.strip(),
                "member_group_id": member_group_id,
                "member_sub_group_id": member_sub_group_id,
                "society_id": selected_society_id,
                "tower_id": selected_tower_id,
                "flat_number": flat_number.strip() or None,
                **extended_fields,
            }
        else:
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
                extended_fields=extended_fields,
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
                extended_fields=extended_fields,
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
        if is_admin_user:
            st.success("Profile updated.")
        else:
            st.success("Profile updated and sent to admin for approval.")
        st.rerun()
