from __future__ import annotations

from datetime import date

import streamlit as st
from lib.supabase_client import SchemaClient

from lib.auth import clear_session, set_session
from lib.disclaimer import (
    DISCLAIMER_VERSION,
    is_disclaimer_view,
    render_disclaimer_screen,
    render_signup_disclaimer,
)
from lib.member_groups import load_member_groups
from lib.member_sub_groups import render_group_sub_group_fields
from lib.password_recovery import render_forgot_password
from lib.profile_extended_fields import (
    render_extended_profile_fields,
    validate_extended_profile_fields,
)
from lib.profile_repair import registration_error_message, try_repair_orphan_profile
from lib.roles import ROLE_OWNER, ROLE_TENANT, SIGNUP_ROLES, is_owner, role_label
from lib.titles import TITLE_OPTIONS, is_valid_title
from lib.user_demographics import MAX_AGE, MIN_AGE, SEX_OPTIONS, sex_age_validation_errors
from lib.validation import validate_password
from lib.visibility import load_societies, load_towers


def render_auth(client: SchemaClient) -> None:
    if is_disclaimer_view():
        render_disclaimer_screen()
        return

    if st.session_state.get("auth_prefer_signup"):
        if st.button("← Back to Login"):
            st.session_state.auth_prefer_signup = False
            st.rerun()
        st.subheader("Sign Up")
        _render_signup(client)
        return

    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    with tab_login:
        _render_login(client)

    with tab_signup:
        _render_signup(client)


def _render_login(client: SchemaClient) -> None:
    if st.session_state.get("show_forgot_password"):
        render_forgot_password(client)
        if st.button("← Back to Login"):
            st.session_state.show_forgot_password = False
            st.rerun()
        return

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", type="primary", use_container_width=True)

    if st.button("Forgot Password?", type="secondary", use_container_width=True):
        st.session_state.show_forgot_password = True
        st.rerun()

    if submitted:
        if not email or not password:
            st.error("Email and password are required.")
            return
        try:
            response = client.auth.sign_in_with_password(
                {"email": email.strip(), "password": password}
            )
            if response.session:
                profile = set_session(client, response.session)
                if profile and profile.get("status") == "rejected":
                    clear_session()
                    st.error("Your registration was rejected. Contact your society admin.")
                    return
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Login failed. Check your credentials.")
        except Exception as exc:
            msg = str(exc)
            if "Email not confirmed" in msg:
                st.error(
                    "Your email is not confirmed yet. Check your inbox for the confirmation "
                    "link, or use Forgot Password to reset your account."
                )
            else:
                st.error(f"Login failed: {exc}")


def _on_signup_society_change() -> None:
    st.session_state.signup_tower = ""


def _render_signup(client: SchemaClient) -> None:
    groups = load_member_groups(client)
    societies = load_societies(client, enabled_only=True)
    society_options = {s["name"]: s["id"] for s in societies}

    if not society_options:
        st.warning(
            "No societies are enabled for registration yet. "
            "Ask your admin to add and enable society details first."
        )

    society_name = st.selectbox(
        "Society *",
        options=[""] + list(society_options.keys()),
        format_func=lambda x: "Select society..." if x == "" else x,
        key="signup_society",
        on_change=_on_signup_society_change,
    )
    society_id = society_options.get(society_name)

    tower_options: dict[str, str] = {}
    if society_id:
        towers = load_towers(client, society_id, enabled_only=True)
        tower_options = {t["name"]: t["id"] for t in towers}

    if society_id and not tower_options:
        st.info(
            "No towers are enabled for this society yet. "
            "Ask your admin to add and enable towers first."
        )

    tower_name = st.selectbox(
        "Tower *",
        options=[""] + list(tower_options.keys()),
        format_func=lambda x: "Select tower..." if x == "" else x,
        disabled=not society_id,
        key="signup_tower",
    )

    role = st.selectbox(
        "I am a *",
        SIGNUP_ROLES,
        format_func=role_label,
        key="signup_role",
    )
    staying_within_society = False
    if is_owner(role):
        staying_within_society = st.checkbox(
            "Staying within Society *",
            key="signup_staying_within_society",
        )
    tenant_expiry_date = None
    if role == ROLE_TENANT:
        tenant_expiry_date = st.date_input(
            "Tenant Expiry Date *",
            min_value=date.today(),
            key="signup_tenant_expiry",
        )

    email = st.text_input("Email *", placeholder="you@example.com", key="signup_email")
    member_group_id, member_sub_group_id = render_group_sub_group_fields(
        client,
        groups,
        group_key="signup_member_group",
        sub_group_key="signup_member_sub_group",
    )
    extended_fields = render_extended_profile_fields(key_prefix="signup")
    disclaimer_accepted = render_signup_disclaimer(key="signup_disclaimer_accepted")

    title = st.selectbox(
        "Title *",
        options=[""] + TITLE_OPTIONS,
        format_func=lambda value: "Select title..." if value == "" else value,
        key="signup_title",
    )
    col1, col2 = st.columns(2)
    first_name = col1.text_input("First Name *", key="signup_first_name")
    last_name = col2.text_input("Last Name *", key="signup_last_name")
    col3, col4 = st.columns(2)
    sex = col3.selectbox(
        "Sex *",
        options=[""] + SEX_OPTIONS,
        format_func=lambda value: "Select sex..." if value == "" else value,
        key="signup_sex",
    )
    age = col4.number_input(
        "Age *",
        min_value=MIN_AGE,
        max_value=MAX_AGE,
        step=1,
        key="signup_age",
    )
    phone = st.text_input("Phone", key="signup_phone")
    password = st.text_input(
        "Password *",
        type="password",
        help="At least 7 characters with at least one letter and one number.",
        key="signup_password",
    )
    confirm = st.text_input(
        "Confirm Password *",
        type="password",
        key="signup_confirm_password",
    )
    flat_number = st.text_input("Flat / Unit Number *", key="signup_flat_number")

    submitted = st.button(
        "Register",
        type="primary",
        use_container_width=True,
        disabled=not disclaimer_accepted,
        key="signup_register",
    )

    if submitted:
        errors = []
        if not disclaimer_accepted:
            errors.append(
                "You must accept the User Acknowledgement & Disclaimer to register."
            )
        if not is_valid_title(title):
            errors.append("Please select a title.")
        if not first_name.strip():
            errors.append("First name is required.")
        if not last_name.strip():
            errors.append("Last name is required.")
        errors.extend(sex_age_validation_errors(sex, age))
        if not email.strip():
            errors.append("Email is required.")
        pwd_error = validate_password(password)
        if pwd_error:
            errors.append(pwd_error)
        if password != confirm:
            errors.append("Passwords do not match.")
        if not society_id:
            errors.append("Please select a society.")
        if not tower_options.get(tower_name):
            errors.append("Please select a tower.")
        if not flat_number.strip():
            errors.append("Flat number is required.")
        if role == ROLE_TENANT and not tenant_expiry_date:
            errors.append("Tenant expiry date is required for tenants.")
        if is_owner(role) and not staying_within_society:
            errors.append(
                "Owners must confirm that they are staying within the society."
            )
        errors.extend(validate_extended_profile_fields(extended_fields))

        if errors:
            for err in errors:
                st.error(err)
            return

        metadata = {
            "title": title,
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "sex": sex,
            "age": int(age),
            "phone": phone.strip() or None,
            "role": role,
            "society_id": society_id,
            "tower_id": tower_options[tower_name],
            "flat_number": flat_number.strip(),
            "disclaimer_accepted": True,
            "disclaimer_version": DISCLAIMER_VERSION,
            **{
                key: (
                    str(value)
                    if key in ("parking_availability_value", "parking_charges") and value is not None
                    else value
                )
                for key, value in extended_fields.items()
                if value is not None
            },
        }
        if member_group_id:
            metadata["member_group_id"] = member_group_id
        if member_sub_group_id:
            metadata["member_sub_group_id"] = member_sub_group_id
        if role == ROLE_TENANT and tenant_expiry_date:
            metadata["tenant_expiry_date"] = tenant_expiry_date.isoformat()
        if is_owner(role):
            metadata["staying_within_society"] = staying_within_society

        try:
            response = client.auth.sign_up(
                {
                    "email": email.strip(),
                    "password": password,
                    "options": {"data": metadata},
                }
            )
            if response.user:
                st.success(
                    "Registration submitted! Your account is pending admin approval."
                )
            else:
                st.error("Registration failed. Please try again.")
        except Exception as exc:
            from lib.profile_repair import _is_already_registered_error

            if _is_already_registered_error(str(exc)) and try_repair_orphan_profile(
                client, email.strip(), metadata
            ):
                st.success(registration_error_message(exc, repaired=True))
            else:
                st.error(registration_error_message(exc))
