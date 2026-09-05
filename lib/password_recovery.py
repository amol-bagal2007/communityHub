from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from lib.auth import clear_session, set_session
from lib.password_reset_requests import submit_password_reset_request
from lib.supabase_client import SchemaClient
from lib.validation import validate_password

RECOVERY_FLAG = "password_recovery_active"


def get_app_redirect_url() -> str:
    from lib.supabase_client import _secret

    return _secret("APP_URL", "http://localhost:8501").rstrip("/")


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
    st.caption(
        "Request your society admin to reset your password. "
        "Provide your registered email and WhatsApp mobile number so the admin can contact you."
    )

    with st.form("forgot_password_form"):
        email = st.text_input("Registered Email *", placeholder="you@example.com")
        whatsapp = st.text_input(
            "WhatsApp Mobile Number *",
            placeholder="e.g. 9876543210 or +919876543210",
            help="Required. Admin will use this number to share your temporary password.",
        )
        submitted = st.form_submit_button(
            "Request Admin For Password Reset",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        err = submit_password_reset_request(
            client,
            email=email,
            whatsapp_number=whatsapp,
        )
        if err:
            st.error(err)
            return
        st.success(
            "Your request has been sent to Admin for review & action. "
            "Please wait — the admin will reset your password and contact you on WhatsApp."
        )


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
        submitted = st.form_submit_button(
            "Update password", type="primary", use_container_width=True
        )

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
