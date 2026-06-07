from __future__ import annotations

import streamlit as st
from lib.supabase_client import SchemaClient

from lib.auth import clear_session, set_session
from lib.validation import validate_password


def render_auth(client: SchemaClient) -> None:
    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    with tab_login:
        _render_login(client)

    with tab_signup:
        _render_signup(client)


def _render_login(client: SchemaClient) -> None:
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", type="primary", use_container_width=True)

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
                    "Your email is not confirmed yet. Check your inbox for the Supabase "
                    "confirmation link, or ask your admin to confirm your account."
                )
            else:
                st.error(f"Login failed: {exc}")


def _on_signup_society_change() -> None:
    st.session_state.signup_tower = ""


def _render_signup(client: SchemaClient) -> None:
    societies = client.table("societies").select("id, name").order("name").execute().data or []
    society_options = {s["name"]: s["id"] for s in societies}

    if not society_options:
        st.warning(
            "No societies registered yet. Ask your admin to add society details first."
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
        towers = (
            client.table("towers")
            .select("id, name")
            .eq("society_id", society_id)
            .order("name")
            .execute()
            .data
            or []
        )
        tower_options = {t["name"]: t["id"] for t in towers}

    if society_id and not tower_options:
        st.info("No towers found for this society. Ask your admin to add towers first.")

    tower_name = st.selectbox(
        "Tower *",
        options=[""] + list(tower_options.keys()),
        format_func=lambda x: "Select tower..." if x == "" else x,
        disabled=not society_id,
        key="signup_tower",
    )

    with st.form("signup_form"):
        full_name = st.text_input("Full Name *")
        email = st.text_input("Email *", placeholder="you@example.com")
        phone = st.text_input("Phone")
        password = st.text_input(
            "Password *",
            type="password",
            help="At least 7 alphanumeric characters (letters and numbers only).",
        )
        confirm = st.text_input("Confirm Password *", type="password")
        flat_number = st.text_input("Flat / Unit Number *")
        role = st.selectbox("I am a *", ["resident", "tenant"])

        submitted = st.form_submit_button("Register", type="primary", use_container_width=True)

    if submitted:
        errors = []
        if not full_name.strip():
            errors.append("Full name is required.")
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

        if errors:
            for err in errors:
                st.error(err)
            return

        try:
            response = client.auth.sign_up(
                {
                    "email": email.strip(),
                    "password": password,
                    "options": {
                        "data": {
                            "full_name": full_name.strip(),
                            "phone": phone.strip() or None,
                            "role": role,
                            "society_id": society_id,
                            "tower_id": tower_options[tower_name],
                            "flat_number": flat_number.strip(),
                        }
                    },
                }
            )
            if response.user:
                st.success(
                    "Registration submitted! Your account is pending admin approval."
                )
            else:
                st.error("Registration failed. Please try again.")
        except Exception as exc:
            st.error(f"Registration failed: {exc}")
