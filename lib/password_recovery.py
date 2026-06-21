from __future__ import annotations

import os

import streamlit as st
import streamlit.components.v1 as components

from lib.auth import clear_session, set_session
from lib.supabase_client import SchemaClient
from lib.validation import validate_password

RECOVERY_FLAG = "password_recovery_active"


def get_app_redirect_url() -> str:
    return os.getenv("APP_URL", "http://localhost:8501").rstrip("/")


def inject_recovery_url_handler() -> None:
    """Move Supabase recovery tokens from URL hash into query params for Streamlit."""
    components.html(
        """
        <script>
        (function () {
            const parent = window.parent.location;
            const hash = parent.hash ? parent.hash.substring(1) : "";
            if (!hash) return;
            const params = new URLSearchParams(hash);
            const accessToken = params.get("access_token");
            const refreshToken = params.get("refresh_token");
            const type = params.get("type");
            if (accessToken && refreshToken && type === "recovery") {
                const url = new URL(parent.href);
                url.hash = "";
                url.searchParams.set("recovery", "1");
                url.searchParams.set("access_token", accessToken);
                url.searchParams.set("refresh_token", refreshToken);
                window.parent.location.replace(url.toString());
            }
        })();
        </script>
        """,
        height=0,
    )


def try_start_recovery_session(client: SchemaClient) -> bool:
    params = st.query_params
    if params.get("recovery") != "1":
        return False

    access_token = params.get("access_token")
    refresh_token = params.get("refresh_token")
    if not access_token or not refresh_token:
        return False

    try:
        response = client.auth.set_session(access_token, refresh_token)
        if response and response.session:
            set_session(client, response.session)
            st.session_state[RECOVERY_FLAG] = True
            st.query_params.clear()
            return True
    except Exception:
        clear_session()
    return False


def render_forgot_password(client: SchemaClient) -> None:
    st.subheader("Forgot Password")
    st.caption("Enter your email and we will send a password reset link.")

    with st.form("forgot_password_form"):
        email = st.text_input("Email", placeholder="you@example.com")
        submitted = st.form_submit_button("Send reset link", type="primary", use_container_width=True)

    if submitted:
        if not email.strip():
            st.error("Email is required.")
            return
        try:
            client.auth.reset_password_for_email(
                email.strip(),
                {"redirect_to": get_app_redirect_url()},
            )
            st.success(
                "If an account exists for that email, a reset link has been sent. "
                "Check your inbox and spam folder."
            )
        except Exception as exc:
            st.error(f"Could not send reset link: {exc}")


def render_reset_password(client: SchemaClient) -> None:
    st.subheader("Set New Password")
    st.caption("Choose a new password for your account.")

    with st.form("reset_password_form"):
        password = st.text_input(
            "New Password",
            type="password",
            help="At least 7 characters with at least one letter and one number.",
        )
        confirm = st.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button("Update password", type="primary", use_container_width=True)

    if submitted:
        errors = []
        pwd_error = validate_password(password)
        if pwd_error:
            errors.append(pwd_error)
        if password != confirm:
            errors.append("Passwords do not match.")
        if errors:
            for err in errors:
                st.error(err)
            return

        try:
            client.auth.update_user({"password": password})
            st.session_state.pop(RECOVERY_FLAG, None)
            st.success("Password updated successfully. You can continue using the app.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not update password: {exc}")
