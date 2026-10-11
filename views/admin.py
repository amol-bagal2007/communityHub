from __future__ import annotations

from datetime import date, datetime, time

import streamlit as st
from lib.supabase_client import SchemaClient

from lib.admin_password_reset import admin_reset_user_password
from lib.auth import get_profile
from lib.event_responses import (
    interest_counts_caption,
    load_event_responses,
    render_response_summary,
)
from lib.event_schedule import (
    build_event_schedule_payload,
    format_event_schedule,
    parse_time_value,
    validate_event_schedule,
)
from lib.member_groups import group_display_name, load_member_groups
from lib.member_sub_groups import (
    SHOW_MEMBER_GROUP_FIELDS,
    load_all_member_sub_groups,
    render_group_sub_group_fields,
    sub_group_display_name,
)
from lib.password_reset_requests import (
    cancel_password_reset_request,
    complete_password_reset_request,
    load_pending_password_reset_requests,
    whatsapp_chat_url,
)
from lib.interest_groups import render_interest_groups_crud
from lib.profile_extended_fields import render_extended_profile_fields
from lib.profile_update import collect_profile_update_errors
from lib.profile_utils import format_name, render_recommended_by_field
from lib.roles import ROLE_TENANT, SIGNUP_ROLES, is_owner, role_label
from lib.supabase_client import get_service_client
from lib.tenant_utils import format_profile_date, parse_profile_date
from lib.titles import TITLE_OPTIONS
from lib.user_demographics import MAX_AGE, MIN_AGE, SEX_OPTIONS
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
from lib.local_businesses import render_local_businesses
from lib.visibility import (
    FLAG_EVENTS_TAB,
    FLAG_LOCAL_BUSINESS_TAB,
    FLAG_VENDORS_TAB,
    load_societies,
    render_feature_toggle,
    set_society_enabled,
    set_tower_enabled,
)


def render_admin_dashboard(client: SchemaClient) -> None:
    profile = get_profile()
    st.title("Admin Dashboard")
    st.caption(f"Signed in as {format_name(profile, 'Admin')}")

    (
        tab_approvals,
        tab_users,
        tab_societies,
        tab_vendors,
        tab_local_business,
        tab_events,
    ) = st.tabs(
        [
            "Pending Approvals",
            "Users",
            "Societies & Towers",
            "Vendors",
            "Local Business",
            "Events",
        ]
    )

    with tab_approvals:
        _render_pending_approvals(client)

    with tab_users:
        _render_users_crud(client)

    with tab_societies:
        _render_societies_crud(client)

    with tab_vendors:
        _render_vendors_crud(client)

    with tab_local_business:
        _render_local_business_crud(client)

    with tab_events:
        _render_events_crud(client)


def _render_pending_approvals(client: SchemaClient) -> None:
    st.subheader("Pending User Registrations")
    pending = (
        client.table("profiles")
        .select("*, societies(name), towers(name), member_groups(name), member_sub_groups(name)")
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
                expiry_line = ""
                if user.get("role") == "tenant":
                    expiry_line = (
                        f"  \nTenant expiry: {format_profile_date(user.get('tenant_expiry_date'))}"
                    )
                elif user.get("role") == "resident":
                    staying = "Yes" if user.get("staying_within_society") else "No"
                    expiry_line = f"  \nStaying within Society: {staying}"
                group_line = (
                    f"Group: {group_display_name(user)} · Sub-Group: {sub_group_display_name(user)}  \n"
                    if SHOW_MEMBER_GROUP_FIELDS
                    else ""
                )
                st.markdown(
                    f"**{user.get('title') or ''} {format_name(user)}** ({role_label(user['role'])})  \n"
                    f"{user['email']} · {user.get('phone') or '—'}  \n"
                    f"Sex: {user.get('sex') or '—'} · Age: {user.get('age') or '—'}  \n"
                    f"{group_line}"
                    f"{society} · Tower {tower} · Flat {user.get('flat_number') or '—'}"
                    f"{expiry_line}"
                )
            with col2:
                if st.button("Approve", key=f"approve_{user['id']}", type="primary"):
                    client.table("profiles").update({"status": "approved"}).eq(
                        "id", user["id"]
                    ).execute()
                    st.success(f"Approved {format_name(user)}")
                    st.rerun()
            with col3:
                if st.button("Reject", key=f"reject_{user['id']}"):
                    client.table("profiles").update({"status": "rejected"}).eq(
                        "id", user["id"]
                    ).execute()
                    st.warning(f"Rejected {format_name(user)}")
                    st.rerun()


def _on_admin_add_society_change() -> None:
    st.session_state.admin_add_user_tower = ""


def _render_password_reset_requests(client: SchemaClient) -> None:
    admin = get_profile() or {}
    st.markdown("**Password Reset Requests**")
    st.caption(
        "Users who requested a password reset from the login screen. "
        "Reset one by one, then share the temporary password on WhatsApp."
    )

    try:
        requests = load_pending_password_reset_requests(client)
    except Exception as exc:
        st.warning(
            f"Could not load password reset requests (table may need migration 019): {exc}"
        )
        return

    if not requests:
        st.info("No pending password reset requests.")
        return

    for req in requests:
        profile = req.get("profiles") or {}
        display_name = format_name(profile, req.get("email") or "User")
        created = req.get("created_at") or ""
        created_label = str(created)[:19].replace("T", " ")
        wa = req.get("whatsapp_number") or ""

        with st.container(border=True):
            st.markdown(f"**{display_name}**")
            st.caption(f"Email: {req.get('email')} · Requested: {created_label}")
            st.write(f"WhatsApp: `{wa}`")
            st.markdown(f"[Open WhatsApp chat]({whatsapp_chat_url(wa)})")

            with st.form(f"admin_handle_reset_{req['id']}"):
                new_password = st.text_input(
                    "New temporary password *",
                    type="password",
                    help="At least 7 characters with at least one letter and one number.",
                    key=f"reset_pwd_{req['id']}",
                )
                confirm_password = st.text_input(
                    "Confirm temporary password *",
                    type="password",
                    key=f"reset_pwd_confirm_{req['id']}",
                )
                c1, c2 = st.columns(2)
                reset_clicked = c1.form_submit_button("Reset Password", type="primary")
                cancel_clicked = c2.form_submit_button("Dismiss Request")

            if reset_clicked:
                if not new_password:
                    st.error("Temporary password is required.")
                elif new_password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    err = complete_password_reset_request(
                        client,
                        request=req,
                        new_password=new_password,
                        admin_id=admin.get("id"),
                    )
                    if err:
                        st.error(err)
                    else:
                        st.success(
                            f"Password reset for {display_name}. "
                            f"Share it on WhatsApp ({wa})."
                        )
                        st.rerun()

            if cancel_clicked:
                err = cancel_password_reset_request(
                    client,
                    request_id=req["id"],
                    admin_id=admin.get("id"),
                )
                if err:
                    st.error(err)
                else:
                    st.info("Request dismissed.")
                    st.rerun()


def _render_users_crud(client: SchemaClient) -> None:
    st.subheader("Manage Users")

    _render_password_reset_requests(client)
    st.divider()

    if SHOW_MEMBER_GROUP_FIELDS:
        _render_member_groups_crud(client)
        _render_member_sub_groups_crud(client)
        st.divider()

    render_interest_groups_crud(client)
    st.divider()

    groups = load_member_groups(client) if SHOW_MEMBER_GROUP_FIELDS else []

    st.markdown("**Add New User (auto-approved)**")
    st.caption(
        "Creates a Supabase Auth user with Approved status. "
        "Requires `SUPABASE_SERVICE_ROLE_KEY` in your local `.env`."
    )

    societies = client.table("societies").select("id, name").order("name").execute().data or []
    society_map = {s["name"]: s["id"] for s in societies}

    society_name = st.selectbox(
        "Society *",
        options=[""] + list(society_map.keys()),
        format_func=lambda value: "Select society..." if value == "" else value,
        key="admin_add_user_society",
        on_change=_on_admin_add_society_change,
    )
    society_id = society_map.get(society_name)

    tower_map: dict[str, str] = {}
    if society_id:
        towers = (
            client.table("towers")
            .select("id, name")
            .eq("society_id", society_id)
            .order("name")
            .execute()
            .data
            or []
        )
        tower_map = {t["name"]: t["id"] for t in towers}

    if society_id and not tower_map:
        st.info("No towers found for this society. Add towers under Societies & Towers first.")

    tower_name = st.selectbox(
        "Tower *",
        options=[""] + list(tower_map.keys()),
        format_func=lambda value: "Select tower..." if value == "" else value,
        disabled=not society_id,
        key="admin_add_user_tower",
    )
    tower_id = tower_map.get(tower_name)

    add_role = st.selectbox(
        "I am a *",
        SIGNUP_ROLES,
        format_func=role_label,
        key="admin_add_user_role",
    )
    add_staying_within_society = False
    if is_owner(add_role):
        add_staying_within_society = st.checkbox(
            "Staying within Society *",
            key="admin_add_user_staying_within_society",
        )
    add_tenant_expiry = None
    if add_role == ROLE_TENANT:
        add_tenant_expiry = st.date_input(
            "Tenant Expiry Date *",
            min_value=date.today(),
            key="admin_add_user_tenant_expiry",
        )

    email = st.text_input("Email *", placeholder="user@example.com", key="admin_add_user_email")
    member_group_id, member_sub_group_id = render_group_sub_group_fields(
        client,
        groups,
        group_key="admin_add_user_member_group",
        sub_group_key="admin_add_user_member_sub_group",
    )
    add_extended_fields = render_extended_profile_fields(
        client, key_prefix="admin_add_user"
    )

    with st.form("admin_add_user"):
        title = st.selectbox(
            "Title *",
            options=[""] + TITLE_OPTIONS,
            format_func=lambda value: "Select title..." if value == "" else value,
        )
        c1, c2 = st.columns(2)
        first_name = c1.text_input("First Name *")
        last_name = c2.text_input("Last Name *")
        c3, c4 = st.columns(2)
        sex = c3.selectbox(
            "Sex *",
            options=[""] + SEX_OPTIONS,
            format_func=lambda value: "Select sex..." if value == "" else value,
        )
        age = c4.number_input("Age *", min_value=MIN_AGE, max_value=MAX_AGE, step=1)
        phone = st.text_input("Phone")
        temp_password = st.text_input(
            "Temporary Password *",
            type="password",
            help="At least 7 characters with at least one letter and one number.",
        )
        flat_number = st.text_input("Flat / Unit Number *")

        create = st.form_submit_button("Create Approved User", type="primary")

    if create:
        errors = collect_profile_update_errors(
            title=title,
            first_name=first_name,
            last_name=last_name,
            sex=sex,
            age=age,
            role=add_role,
            flat_number=flat_number,
            staying_within_society=add_staying_within_society,
            tenant_expiry=add_tenant_expiry,
            society_id=society_id,
            tower_id=tower_id,
            email=email,
            extended_fields=add_extended_fields,
        )
        pwd_error = validate_password(temp_password)
        if pwd_error:
            errors.append(pwd_error)
        if not temp_password:
            errors.append("Temporary password is required.")

        if errors:
            for err in errors:
                st.error(err)
        else:
            try:
                svc = get_service_client()
            except Exception as exc:
                st.error(str(exc))
            else:
                try:
                    user_metadata = {
                        "title": title,
                        "first_name": first_name.strip(),
                        "last_name": last_name.strip(),
                        "sex": sex,
                        "age": int(age),
                        "phone": phone.strip() or None,
                        "role": add_role,
                        "society_id": society_id,
                        "tower_id": tower_id,
                        "flat_number": flat_number.strip(),
                        **{
                            key: (
                                str(value)
                                if key
                                in ("parking_availability_value", "parking_charges")
                                and value is not None
                                else value
                            )
                            for key, value in add_extended_fields.items()
                            if value is not None
                        },
                    }
                    if member_group_id:
                        user_metadata["member_group_id"] = member_group_id
                    if member_sub_group_id:
                        user_metadata["member_sub_group_id"] = member_sub_group_id
                    profile_update = {
                        "title": title,
                        "status": "approved",
                        "role": add_role,
                        "first_name": first_name.strip(),
                        "last_name": last_name.strip(),
                        "sex": sex,
                        "age": int(age),
                        "phone": phone.strip() or None,
                        "email": email.strip(),
                        "member_group_id": member_group_id,
                        "member_sub_group_id": member_sub_group_id,
                        "society_id": society_id,
                        "tower_id": tower_id,
                        "flat_number": flat_number.strip(),
                        "tenant_expiry_date": None,
                        "staying_within_society": False,
                        **add_extended_fields,
                    }
                    if add_role == ROLE_TENANT and add_tenant_expiry:
                        expiry = add_tenant_expiry.isoformat()
                        user_metadata["tenant_expiry_date"] = expiry
                        profile_update["tenant_expiry_date"] = expiry
                    if is_owner(add_role):
                        user_metadata["staying_within_society"] = add_staying_within_society
                        profile_update["staying_within_society"] = add_staying_within_society

                    created = svc.raw.auth.admin.create_user(
                        {
                            "email": email.strip(),
                            "password": temp_password,
                            "email_confirm": True,
                            "user_metadata": user_metadata,
                        }
                    )
                    user_id = getattr(getattr(created, "user", None), "id", None) or getattr(
                        created, "id", None
                    )
                    if not user_id and isinstance(created, dict):
                        user_id = created.get("id") or (created.get("user") or {}).get("id")
                    if not user_id:
                        raise RuntimeError("User created but could not read user id.")

                    svc.table("profiles").update(profile_update).eq("id", user_id).execute()

                    st.success("User created and approved.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not create user: {exc}")

    st.divider()

    admin_profile = get_profile() or {}
    admin_id = admin_profile.get("id")

    users = (
        client.table("profiles")
        .select("*, societies(name), towers(name), member_groups(name), member_sub_groups(name)")
        # Admins should be able to manage/edit any existing user (including other admins)
        .order("first_name")
        .execute()
        .data
        or []
    )
    # Do not allow editing your own account here — use sidebar Profile instead.
    users = [u for u in users if u.get("id") != admin_id]

    if not users:
        st.info("No other users to edit.")
        return

    edit_id = st.selectbox(
        "Select user to edit",
        options=[""] + [u["id"] for u in users],
        format_func=lambda uid: next(
            (f"{format_name(u)} ({u['email']})" for u in users if u["id"] == uid), "Select..."
        ),
    )

    if edit_id and society_map:
        user = next(u for u in users if u["id"] == edit_id)
        current_society = (user.get("societies") or {}).get("name", "")
        current_tower = (user.get("towers") or {}).get("name", "")

        # Society selection must be outside the form so tower list updates immediately
        society_names = list(society_map.keys())
        selected_society = st.selectbox(
            "Society",
            society_names,
            index=society_names.index(current_society) if current_society in society_names else 0,
            key=f"edit_user_society_{edit_id}",
        )
        selected_society_id = society_map.get(selected_society)
        towers = (
            client.table("towers")
            .select("id, name")
            .eq("society_id", selected_society_id or "")
            .order("name")
            .execute()
            .data
            or []
        )
        tower_map = {t["name"]: t["id"] for t in towers}
        tower_names = list(tower_map.keys())

        edit_role = st.selectbox(
            "Role",
            SIGNUP_ROLES,
            format_func=role_label,
            index=0 if is_owner(user["role"]) else 1,
            key=f"edit_user_role_{edit_id}",
        )
        edit_staying_within_society = False
        if is_owner(edit_role):
            edit_staying_within_society = st.checkbox(
                "Staying within Society *",
                value=bool(user.get("staying_within_society")),
                key=f"edit_user_staying_within_society_{edit_id}",
            )
        edit_tenant_expiry = None
        if edit_role == ROLE_TENANT:
            current_expiry = parse_profile_date(user.get("tenant_expiry_date"))
            edit_tenant_expiry = st.date_input(
                "Tenant Expiry Date *",
                value=current_expiry or date.today(),
                min_value=date.today(),
                key=f"edit_user_tenant_expiry_{edit_id}",
            )

        current_title = user.get("title") or ""
        title_index = TITLE_OPTIONS.index(current_title) if current_title in TITLE_OPTIONS else 0

        email = st.text_input(
            "Email *",
            value=user.get("email") or "",
            key=f"edit_user_email_{edit_id}",
        )
        member_group_id, member_sub_group_id = render_group_sub_group_fields(
            client,
            groups,
            group_key=f"edit_user_member_group_{edit_id}",
            sub_group_key=f"edit_user_member_sub_group_{edit_id}",
            current_group_id=user.get("member_group_id"),
            current_sub_group_id=user.get("member_sub_group_id"),
        )
        edit_extended_fields = render_extended_profile_fields(
            client,
            key_prefix=f"edit_user_{edit_id}",
            current=user,
        )

        with st.form("edit_user"):
            title = st.selectbox("Title *", TITLE_OPTIONS, index=title_index)
            c1, c2 = st.columns(2)
            first_name = c1.text_input("First Name *", value=user.get("first_name") or "")
            last_name = c2.text_input("Last Name *", value=user.get("last_name") or "")
            current_sex = user.get("sex") or ""
            sex_index = SEX_OPTIONS.index(current_sex) if current_sex in SEX_OPTIONS else 0
            c3, c4 = st.columns(2)
            sex = c3.selectbox("Sex *", SEX_OPTIONS, index=sex_index)
            age = c4.number_input(
                "Age *",
                min_value=MIN_AGE,
                max_value=MAX_AGE,
                value=int(user.get("age") or MIN_AGE),
                step=1,
            )
            phone = st.text_input("Phone", value=user.get("phone") or "")
            st.text_input(
                "Status",
                value=(user.get("status") or "").title(),
                disabled=True,
                help="Admin saves set the user to Approved automatically.",
            )
            tower_name = (
                st.selectbox(
                    "Tower",
                    tower_names,
                    index=tower_names.index(current_tower) if current_tower in tower_names else 0,
                )
                if tower_names
                else None
            )
            flat_number = st.text_input("Flat / Unit Number *", value=user.get("flat_number") or "")

            col1, col2 = st.columns(2)
            save = col1.form_submit_button("Save Changes", type="primary")
            delete = col2.form_submit_button("Delete User")

        if save:
            errors = collect_profile_update_errors(
                title=title,
                first_name=first_name,
                last_name=last_name,
                sex=sex,
                age=age,
                role=edit_role,
                flat_number=flat_number,
                staying_within_society=edit_staying_within_society,
                tenant_expiry=edit_tenant_expiry,
                society_id=selected_society_id,
                tower_id=tower_map.get(tower_name) if tower_name else None,
                email=email,
                extended_fields=edit_extended_fields,
            )
            if errors:
                for err in errors:
                    st.error(err)
            else:
                update_data = {
                    "title": title,
                    "first_name": first_name.strip(),
                    "last_name": last_name.strip(),
                    "sex": sex,
                    "age": int(age),
                    "phone": phone.strip() or None,
                    "email": email.strip(),
                    "member_group_id": member_group_id,
                    "member_sub_group_id": member_sub_group_id,
                    "role": edit_role,
                    "status": "approved",
                    "society_id": selected_society_id,
                    "tower_id": tower_map.get(tower_name) if tower_name else None,
                    "flat_number": flat_number.strip() or None,
                    "tenant_expiry_date": (
                        edit_tenant_expiry.isoformat()
                        if edit_role == ROLE_TENANT and edit_tenant_expiry
                        else None
                    ),
                    "staying_within_society": (
                        edit_staying_within_society if is_owner(edit_role) else False
                    ),
                    **edit_extended_fields,
                }
                client.table("profiles").update(update_data).eq("id", edit_id).execute()
                st.success("User updated and approved.")
                st.rerun()

        if delete:
            client.table("profiles").delete().eq("id", edit_id).execute()
            st.success("User profile deleted.")
            st.rerun()

        st.divider()
        st.markdown("**Reset Password (temporary)**")
        st.caption(
            "Set a new temporary password for this user without email. "
            "Share it securely and ask them to change it after login if needed. "
            "Requires `SUPABASE_SERVICE_ROLE_KEY` in `.env`."
        )
        with st.form(f"admin_reset_password_{edit_id}"):
            new_password = st.text_input(
                "New temporary password *",
                type="password",
                help="At least 7 characters with at least one letter and one number.",
            )
            confirm_password = st.text_input("Confirm temporary password *", type="password")
            reset_clicked = st.form_submit_button("Reset Password", type="primary")

        if reset_clicked:
            if not new_password:
                st.error("Temporary password is required.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                err = admin_reset_user_password(edit_id, new_password)
                if err:
                    st.error(err)
                else:
                    st.success(
                        f"Password reset for {format_name(user)} ({user.get('email')}). "
                        "Share the temporary password with them securely."
                    )


def _render_member_groups_crud(client: SchemaClient) -> None:
    st.markdown("**Member Groups**")
    st.caption("Groups shown in user forms. Only admins can add or change these.")

    with st.form("add_member_group"):
        name = st.text_input("Group Name *")
        if st.form_submit_button("Add Group", type="primary"):
            if not name.strip():
                st.error("Group name is required.")
            else:
                client.table("member_groups").insert({"name": name.strip()}).execute()
                st.success("Group added.")
                st.rerun()

    groups = load_member_groups(client)
    if not groups:
        st.info("No groups yet. Add one above.")
        return

    for group in groups:
        with st.expander(group["name"]):
            with st.form(f"edit_member_group_{group['id']}"):
                new_name = st.text_input("Name", value=group["name"])
                c1, c2 = st.columns(2)
                if c1.form_submit_button("Update"):
                    if not new_name.strip():
                        st.error("Group name is required.")
                    else:
                        client.table("member_groups").update(
                            {"name": new_name.strip()}
                        ).eq("id", group["id"]).execute()
                        st.rerun()
                if c2.form_submit_button("Delete"):
                    client.table("member_groups").delete().eq("id", group["id"]).execute()
                    st.rerun()


def _render_member_sub_groups_crud(client: SchemaClient) -> None:
    st.markdown("**Member Sub-Groups**")
    st.caption("Sub-groups are linked to a parent group and shown based on group selection.")

    groups = load_member_groups(client)
    group_map = {g["name"]: g["id"] for g in groups}
    group_names = list(group_map.keys())

    with st.form("add_member_sub_group"):
        parent_group = st.selectbox("Group *", group_names if group_names else [""])
        name = st.text_input("Sub-Group Name *")
        if st.form_submit_button("Add Sub-Group", type="primary"):
            if not name.strip():
                st.error("Sub-group name is required.")
            elif parent_group not in group_map:
                st.error("Select a parent group.")
            else:
                client.table("member_sub_groups").insert(
                    {"member_group_id": group_map[parent_group], "name": name.strip()}
                ).execute()
                st.success("Sub-group added.")
                st.rerun()

    sub_groups = load_all_member_sub_groups(client)
    if not sub_groups:
        st.info("No sub-groups yet. Add one above.")
        return

    for sub_group in sub_groups:
        parent_name = (sub_group.get("member_groups") or {}).get("name", "—")
        with st.expander(f"{parent_name} → {sub_group['name']}"):
            with st.form(f"edit_member_sub_group_{sub_group['id']}"):
                new_parent = st.selectbox(
                    "Group *",
                    group_names,
                    index=group_names.index(parent_name) if parent_name in group_names else 0,
                )
                new_name = st.text_input("Sub-Group Name", value=sub_group["name"])
                c1, c2 = st.columns(2)
                if c1.form_submit_button("Update"):
                    if not new_name.strip() or new_parent not in group_map:
                        st.error("Group and sub-group name are required.")
                    else:
                        client.table("member_sub_groups").update(
                            {
                                "member_group_id": group_map[new_parent],
                                "name": new_name.strip(),
                            }
                        ).eq("id", sub_group["id"]).execute()
                        st.rerun()
                if c2.form_submit_button("Delete"):
                    client.table("member_sub_groups").delete().eq(
                        "id", sub_group["id"]
                    ).execute()
                    st.rerun()


def _render_societies_crud(client: SchemaClient) -> None:
    st.subheader("Societies & Towers")
    st.caption(
        "Enable a society or tower for members before it appears on Sign Up / Profile."
    )

    col_add, col_list = st.columns([1, 2])

    with col_add:
        st.markdown("**Add Society**")
        with st.form("add_society"):
            name = st.text_input("Society Name")
            area = st.text_input("Area")
            road = st.text_input("Road")
            pin_code = st.text_input("Pin Code")
            enable_society = st.checkbox(
                "Enable for members",
                value=False,
                help="Only enabled societies appear for other users.",
            )
            if st.form_submit_button("Add Society", type="primary"):
                if name.strip():
                    client.table("societies").insert(
                        {
                            "name": name.strip(),
                            "area": area.strip(),
                            "road": road.strip(),
                            "pin_code": pin_code.strip(),
                            "is_enabled": enable_society,
                        }
                    ).execute()
                    st.success("Society added.")
                    st.rerun()
                else:
                    st.error("Society name is required.")

        st.markdown("**Add Tower**")
        societies = load_societies(client, enabled_only=False)
        soc_map = {s["name"]: s["id"] for s in societies}
        with st.form("add_tower"):
            soc_name = st.selectbox("Society", list(soc_map.keys()) if soc_map else [""])
            tower_name = st.text_input("Tower Name")
            enable_tower = st.checkbox(
                "Enable for members",
                value=False,
                help="Only enabled towers appear for other users.",
            )
            if st.form_submit_button("Add Tower", type="primary"):
                if tower_name.strip() and soc_name in soc_map:
                    client.table("towers").insert(
                        {
                            "society_id": soc_map[soc_name],
                            "name": tower_name.strip(),
                            "is_enabled": enable_tower,
                        }
                    ).execute()
                    st.success("Tower added.")
                    st.rerun()

    with col_list:
        st.markdown("**Existing Societies**")
        all_societies = (
            client.table("societies")
            .select("*, towers(id, name, is_enabled)")
            .order("name")
            .execute()
            .data
            or []
        )
        for soc in all_societies:
            status = "Enabled" if soc.get("is_enabled") else "Disabled"
            with st.expander(f"{soc['name']} — {soc.get('area') or ''} ({status})"):
                st.write(f"Road: {soc.get('road') or '—'} | Pin: {soc.get('pin_code') or '—'}")

                soc_enabled = st.checkbox(
                    "Enable society for members",
                    value=bool(soc.get("is_enabled")),
                    key=f"soc_enabled_{soc['id']}",
                )
                if soc_enabled != bool(soc.get("is_enabled")):
                    err = set_society_enabled(client, soc["id"], soc_enabled)
                    if err:
                        st.error(f"Could not update society visibility: {err}")
                    else:
                        st.rerun()

                towers = soc.get("towers") or []
                if not towers:
                    st.write("No towers yet.")
                else:
                    st.markdown("**Towers**")
                    for tower in sorted(towers, key=lambda t: (t.get("name") or "").lower()):
                        tower_enabled = st.checkbox(
                            f"Enable tower: {tower['name']}",
                            value=bool(tower.get("is_enabled")),
                            key=f"tower_enabled_{tower['id']}",
                        )
                        if tower_enabled != bool(tower.get("is_enabled")):
                            err = set_tower_enabled(client, tower["id"], tower_enabled)
                            if err:
                                st.error(f"Could not update tower visibility: {err}")
                            else:
                                st.rerun()

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


def _render_local_business_crud(client: SchemaClient) -> None:
    render_feature_toggle(
        client,
        key=FLAG_LOCAL_BUSINESS_TAB,
        label="Enable Local Business tab for members",
        help_text="When checked, approved members see the Local Business tab.",
        widget_key="admin_enable_local_business_tab",
    )
    st.divider()
    profile = get_profile()
    societies = load_societies(client, enabled_only=False)
    render_local_businesses(client, profile, admin=True, societies=societies)


def _render_vendors_crud(client: SchemaClient) -> None:
    st.subheader("Vendors")
    render_feature_toggle(
        client,
        key=FLAG_VENDORS_TAB,
        label="Enable Vendors tab for members",
        help_text="When checked, approved members see the Vendors tab on their dashboard.",
        widget_key="admin_enable_vendors_tab",
    )
    st.divider()
    _render_vendor_categories_crud(client)
    st.divider()

    profile = get_profile()
    admin_name = format_name(profile, "Admin")
    categories = load_vendor_categories(client)
    societies = client.table("societies").select("id, name").order("name").execute().data or []
    soc_map = {s["name"]: s["id"] for s in societies}

    with st.form("add_vendor"):
        st.markdown("**Add Vendor**")
        c1, c2 = st.columns(2)
        first_name = c1.text_input("Vendor First Name *")
        last_name = c2.text_input("Vendor Last Name *")
        recommended_by = render_recommended_by_field(
            admin=True,
            default_name=admin_name,
        )
        c3, c4 = st.columns(2)
        category_id = render_category_select(categories, key="admin_add_vendor_category")
        contact_phone = c4.text_input("Phone")
        contact_email = st.text_input("Email")
        description = st.text_area("Description")
        society_name = st.selectbox("Society", list(soc_map.keys()) if soc_map else [""])
        if st.form_submit_button("Add Vendor", type="primary"):
            if not first_name.strip():
                st.error("Vendor first name is required.")
            elif not last_name.strip():
                st.error("Vendor last name is required.")
            elif not category_id:
                st.error("Select a category.")
            elif society_name in soc_map:
                inserted = (
                    client.table("vendors")
                    .insert(
                        {
                            "first_name": first_name.strip(),
                            "last_name": last_name.strip(),
                            "recommended_by": recommended_by.strip() or None,
                            "category_id": category_id,
                            "contact_phone": contact_phone.strip() or None,
                            "contact_email": contact_email.strip() or None,
                            "description": description.strip() or None,
                            "society_id": soc_map[society_name],
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
                st.success("Vendor added.")
                st.rerun()

    vendors = (
        client.table("vendors")
        .select("*, societies(name), profiles(first_name, last_name), vendor_categories(name)")
        .order("first_name")
        .order("last_name")
        .execute()
        .data
        or []
    )

    page_vendors = render_vendor_filter_and_page(
        categories,
        vendors,
        key_prefix="admin_vendors",
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
        added_by = format_name(vendor.get("profiles"), "Unknown")
        society = (vendor.get("societies") or {}).get("name", "—")
        vendor_label = format_name(vendor, "Vendor")
        open_key = f"admin_vendor_open_{vendor['id']}"
        summary_data = feedback.get(vendor["id"])

        with st.container(border=True):
            summary, action = st.columns([5, 1])
            summary.markdown(f"**{vendor_label}** — {category_display_name(vendor)}")
            summary.caption(feedback_caption(summary_data))
            if action.button(
                "Hide" if st.session_state.get(open_key) else "View",
                key=f"admin_vendor_view_{vendor['id']}",
                use_container_width=True,
            ):
                st.session_state[open_key] = not st.session_state.get(open_key, False)
                st.rerun()

            if not st.session_state.get(open_key):
                continue

            st.write(f"Society: {society} | Added by: {added_by}")
            st.write(f"Originally recommended by: {vendor.get('recommended_by') or '—'}")
            st.write(feedback_caption(summary_data))
            st.write(
                f"Phone: {vendor.get('contact_phone') or '—'} | "
                f"Email: {vendor.get('contact_email') or '—'}"
            )
            if vendor.get("description"):
                st.write(vendor["description"])

            if not user_has_recommended(summary_data, profile["id"]):
                if st.button(
                    "Recommend this Vendor",
                    key=f"admin_recommend_vendor_{vendor['id']}",
                ):
                    err = ensure_vendor_recommendation(
                        client,
                        vendor_id=vendor["id"],
                        user_id=profile["id"],
                    )
                    if err:
                        st.error(err)
                    else:
                        st.success("Recommendation saved.")
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
                key_prefix=f"admin_vendor_{vendor['id']}",
            )

            with st.form(f"edit_vendor_{vendor['id']}"):
                c1, c2 = st.columns(2)
                fn = c1.text_input("Vendor First Name", value=vendor.get("first_name") or "")
                ln = c2.text_input("Vendor Last Name", value=vendor.get("last_name") or "")
                rb = render_recommended_by_field(
                    admin=True,
                    default_name=admin_name,
                    current_value=vendor.get("recommended_by") or "",
                )
                category_id = render_category_select(
                    categories,
                    key=f"admin_edit_vendor_category_{vendor['id']}",
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
                            "recommended_by": rb.strip() or None,
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


def _render_vendor_categories_crud(client: SchemaClient) -> None:
    st.markdown("**Vendor Categories**")
    st.caption("Categories shown in vendor forms. Only admins can add or change these.")

    with st.form("add_vendor_category"):
        name = st.text_input("Category Name *")
        if st.form_submit_button("Add Category", type="primary"):
            if not name.strip():
                st.error("Category name is required.")
            else:
                client.table("vendor_categories").insert({"name": name.strip()}).execute()
                st.success("Category added.")
                st.rerun()

    categories = load_vendor_categories(client)
    if not categories:
        st.info("No categories yet. Add one above.")
        return

    for category in categories:
        with st.expander(category["name"]):
            with st.form(f"edit_vendor_category_{category['id']}"):
                new_name = st.text_input("Name", value=category["name"])
                c1, c2 = st.columns(2)
                if c1.form_submit_button("Update"):
                    if not new_name.strip():
                        st.error("Category name is required.")
                    else:
                        client.table("vendor_categories").update(
                            {"name": new_name.strip()}
                        ).eq("id", category["id"]).execute()
                        st.rerun()
                if c2.form_submit_button("Delete"):
                    client.table("vendor_categories").delete().eq(
                        "id", category["id"]
                    ).execute()
                    st.rerun()


def _render_events_crud(client: SchemaClient) -> None:
    st.subheader("Society Events")
    render_feature_toggle(
        client,
        key=FLAG_EVENTS_TAB,
        label="Enable Events tab for members",
        help_text="When checked, approved members see the Events tab on their dashboard.",
        widget_key="admin_enable_events_tab",
    )
    st.divider()
    profile = get_profile()
    societies = load_societies(client, enabled_only=False)
    soc_map = {s["name"]: s["id"] for s in societies}

    st.markdown("**Create Event**")
    include_break = st.checkbox("Include Break", key="add_event_include_break")
    with st.form("add_event"):
        title = st.text_input("Title")
        description = st.text_area("Description")
        event_date = st.date_input("Event Date")
        c1, c2 = st.columns(2)
        from_time = c1.time_input("From Time", value=time(9, 0))
        to_time = c2.time_input("To Time", value=time(12, 0))

        break_from = None
        break_to = None
        if include_break:
            st.markdown("**Break**")
            b1, b2 = st.columns(2)
            break_from = b1.time_input("Break From", value=time(10, 30))
            break_to = b2.time_input("Break To", value=time(10, 45))

        location = st.text_input("Location")
        society_name = st.selectbox(
            "Society", list(soc_map.keys()) if soc_map else [""], key="event_soc"
        )
        is_published = st.checkbox("Publish immediately", value=True)
        if st.form_submit_button("Create Event", type="primary"):
            errors = []
            if not title.strip():
                errors.append("Title is required.")
            if society_name not in soc_map:
                errors.append("Select a society.")
            errors.extend(
                validate_event_schedule(
                    from_time=from_time,
                    to_time=to_time,
                    include_break=include_break,
                    break_from=break_from,
                    break_to=break_to,
                )
            )
            if errors:
                for err in errors:
                    st.error(err)
            else:
                schedule = build_event_schedule_payload(
                    event_date=event_date,
                    from_time=from_time,
                    to_time=to_time,
                    include_break=include_break,
                    break_from=break_from,
                    break_to=break_to,
                )
                client.table("events").insert(
                    {
                        "title": title.strip(),
                        "description": description.strip() or None,
                        "location": location.strip() or None,
                        "society_id": soc_map[society_name],
                        "is_published": is_published,
                        "created_by": profile["id"],
                        **schedule,
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

    if not events:
        st.info("No events yet. Create one above.")
        return

    st.markdown("**Existing Events**")
    st.caption("Open an event to update or delete it, and to see interest responses.")

    for event in events:
        society = (event.get("societies") or {}).get("name", "—")
        status = "Published" if event.get("is_published") else "Draft"
        open_key = f"admin_event_open_{event['id']}"
        event_dt = datetime.fromisoformat(str(event["event_date"]).replace("Z", "+00:00"))
        edit_break_key = f"edit_event_include_break_{event['id']}"
        if edit_break_key not in st.session_state:
            st.session_state[edit_break_key] = bool(
                event.get("break_start_time") and event.get("break_end_time")
            )

        responses = load_event_responses(client, event["id"])

        with st.container(border=True):
            summary, action = st.columns([5, 1])
            summary.markdown(f"**{event['title']}** — {status}")
            summary.caption(
                f"Society: {society} · {event_dt.strftime('%a, %d %b %Y')} · "
                f"{format_event_schedule(event)}"
            )
            summary.caption(interest_counts_caption(responses))
            if action.button(
                "Hide" if st.session_state.get(open_key) else "View / Edit",
                key=f"admin_event_view_{event['id']}",
                use_container_width=True,
            ):
                st.session_state[open_key] = not st.session_state.get(open_key, False)
                st.rerun()

            if not st.session_state.get(open_key):
                continue

            st.write(f"Location: {event.get('location') or '—'}")
            st.write(f"Schedule: {format_event_schedule(event)}")
            if event.get("description"):
                st.write(event["description"])

            render_response_summary(responses)

            st.markdown("**Update / Delete Event**")
            include_break_edit = st.checkbox(
                "Include Break",
                key=edit_break_key,
            )
            current_from = event_dt.time().replace(second=0, microsecond=0)
            current_to = parse_time_value(event.get("end_time")) or time(12, 0)
            current_break_from = parse_time_value(event.get("break_start_time")) or time(
                10, 30
            )
            current_break_to = parse_time_value(event.get("break_end_time")) or time(
                10, 45
            )

            with st.form(f"edit_event_{event['id']}"):
                et = st.text_input("Title", value=event["title"])
                ed = st.text_area("Description", value=event.get("description") or "")
                edit_date = st.date_input(
                    "Event Date",
                    value=event_dt.date(),
                    key=f"edit_event_date_{event['id']}",
                )
                t1, t2 = st.columns(2)
                edit_from = t1.time_input(
                    "From Time",
                    value=current_from,
                    key=f"edit_event_from_{event['id']}",
                )
                edit_to = t2.time_input(
                    "To Time",
                    value=current_to,
                    key=f"edit_event_to_{event['id']}",
                )

                edit_break_from = None
                edit_break_to = None
                if include_break_edit:
                    st.markdown("**Break**")
                    b1, b2 = st.columns(2)
                    edit_break_from = b1.time_input(
                        "Break From",
                        value=current_break_from,
                        key=f"edit_event_break_from_{event['id']}",
                    )
                    edit_break_to = b2.time_input(
                        "Break To",
                        value=current_break_to,
                        key=f"edit_event_break_to_{event['id']}",
                    )

                el = st.text_input(
                    "Location",
                    value=event.get("location") or "",
                    key=f"edit_event_location_{event['id']}",
                )
                ep = st.checkbox("Published", value=event.get("is_published", False))
                c1, c2 = st.columns(2)
                update_clicked = c1.form_submit_button("Update Event", type="primary")
                delete_clicked = c2.form_submit_button("Delete Event")

            if update_clicked:
                errors = validate_event_schedule(
                    from_time=edit_from,
                    to_time=edit_to,
                    include_break=include_break_edit,
                    break_from=edit_break_from,
                    break_to=edit_break_to,
                )
                if not et.strip():
                    errors.append("Title is required.")
                if errors:
                    for err in errors:
                        st.error(err)
                else:
                    try:
                        schedule = build_event_schedule_payload(
                            event_date=edit_date,
                            from_time=edit_from,
                            to_time=edit_to,
                            include_break=include_break_edit,
                            break_from=edit_break_from,
                            break_to=edit_break_to,
                        )
                        client.table("events").update(
                            {
                                "title": et.strip(),
                                "description": ed.strip() or None,
                                "location": el.strip() or None,
                                "is_published": ep,
                                **schedule,
                            }
                        ).eq("id", event["id"]).execute()
                        st.success("Event updated.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not update event: {exc}")

            if delete_clicked:
                try:
                    client.table("events").delete().eq("id", event["id"]).execute()
                    st.session_state.pop(open_key, None)
                    st.success("Event deleted.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not delete event: {exc}")
