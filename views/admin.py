from __future__ import annotations

from datetime import date

import streamlit as st
from lib.supabase_client import SchemaClient

from lib.auth import get_profile
from lib.member_groups import group_display_name, load_member_groups
from lib.member_sub_groups import (
    load_all_member_sub_groups,
    render_group_sub_group_fields,
    sub_group_display_name,
)
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
)


def render_admin_dashboard(client: SchemaClient) -> None:
    profile = get_profile()
    st.title("Admin Dashboard")
    st.caption(f"Signed in as {format_name(profile, 'Admin')}")

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
                st.markdown(
                    f"**{user.get('title') or ''} {format_name(user)}** ({role_label(user['role'])})  \n"
                    f"{user['email']} · {user.get('phone') or '—'}  \n"
                    f"Sex: {user.get('sex') or '—'} · Age: {user.get('age') or '—'}  \n"
                    f"Group: {group_display_name(user)} · Sub-Group: {sub_group_display_name(user)}  \n"
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


def _render_users_crud(client: SchemaClient) -> None:
    st.subheader("Manage Users")

    _render_member_groups_crud(client)
    _render_member_sub_groups_crud(client)
    st.divider()

    groups = load_member_groups(client)

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

    users = (
        client.table("profiles")
        .select("*, societies(name), towers(name), member_groups(name), member_sub_groups(name)")
        # Admins should be able to manage/edit any existing user (including admins)
        .order("first_name")
        .execute()
        .data
        or []
    )

    if not users:
        st.info("No users yet.")
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
                }
                client.table("profiles").update(update_data).eq("id", edit_id).execute()
                st.success("User updated and approved.")
                st.rerun()

        if delete:
            client.table("profiles").delete().eq("id", edit_id).execute()
            st.success("User profile deleted.")
            st.rerun()


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
                client.table("vendors").insert(
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
                ).execute()
                st.success("Vendor added.")
                st.rerun()

    vendors = (
        client.table("vendors")
        .select("*, societies(name), profiles(first_name, last_name), vendor_categories(name)")
        .order("first_name")
        .execute()
        .data
        or []
    )

    for vendor in vendors:
        added_by = format_name(vendor.get("profiles"), "Unknown")
        society = (vendor.get("societies") or {}).get("name", "—")
        vendor_label = format_name(vendor, "Vendor")
        with st.expander(f"{vendor_label} — {category_display_name(vendor)}"):
            st.write(f"Society: {society} | Added by: {added_by}")
            st.write(f"Recommended by: {vendor.get('recommended_by') or '—'}")
            st.write(
                f"Phone: {vendor.get('contact_phone') or '—'} | "
                f"Email: {vendor.get('contact_email') or '—'}"
            )
            if vendor.get("description"):
                st.write(vendor["description"])

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
