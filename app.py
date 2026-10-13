import streamlit as st

from lib.auth import (
    clear_session,
    get_profile,
    is_admin,
    is_approved_user,
    is_logged_in,
    restore_session,
)
from lib.mobile_ui import inject_mobile_styles, render_mobile_top_nav
from lib.password_recovery import (
    RECOVERY_FLAG,
    inject_recovery_url_handler,
    render_reset_password,
    try_start_recovery_session,
)
from lib.profile_utils import format_name
from lib.pwa import inject_pwa_meta
from lib.supabase_client import get_client
from views.admin import render_admin_dashboard
from views.auth import render_auth
from views.user import render_profile_page, render_user_dashboard

NAV_KEY = "app_nav_page"
NAV_DASHBOARD = "dashboard"
NAV_PROFILE = "profile"


def main() -> None:
    st.set_page_config(
        page_title="CommunityHub",
        page_icon="🏘️",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    inject_pwa_meta()
    inject_mobile_styles()
    inject_recovery_url_handler()

    client = get_client()
    try_start_recovery_session(client)
    restore_session(client)

    _render_sidebar(client)

    if st.session_state.get(RECOVERY_FLAG) and is_logged_in():
        st.title("🏘️ CommunityHub")
        render_reset_password(client)
        return

    if not is_logged_in():
        st.session_state.pop(NAV_KEY, None)
        st.title("🏘️ CommunityHub")
        st.markdown(
            """
**Welcome to Community Hub: Powered by Residents**

Your exclusive neighborhood portal built to make society living effortless. Recommend trusted vendors, support resident-run businesses, and join active community groups—all in one secure platform. Designed to help everyone, including tenants and residents, seamlessly discover and connect with our trusted local ecosystem.
            """.strip()
        )
        render_auth(client)
        return

    profile = get_profile()
    if not profile:
        st.error("Could not load your profile. Please log in again.")
        clear_session()
        st.rerun()
        return

    if profile.get("status") == "pending":
        st.warning(
            "Your registration is pending admin approval. "
            "You will get full access once approved."
        )
        if st.button("Logout", use_container_width=True):
            client.auth.sign_out()
            clear_session()
            st.rerun()
        return

    if profile.get("status") == "rejected":
        st.error("Your registration was rejected. Contact your society admin.")
        if st.button("Logout", use_container_width=True):
            client.auth.sign_out()
            clear_session()
            st.rerun()
        return

    page = st.session_state.get(NAV_KEY, NAV_DASHBOARD)
    if profile.get("status") == "approved":
        requested = render_mobile_top_nav(current=page, show_nav=True)
        if requested and requested != page:
            st.session_state[NAV_KEY] = requested
            st.rerun()

    if page == NAV_PROFILE:
        st.title("🏘️ CommunityHub")
        render_profile_page(client, profile)
        return

    if is_admin():
        render_admin_dashboard(client)
    elif is_approved_user():
        render_user_dashboard(client)
    else:
        st.error("Access denied.")


def _render_sidebar(client) -> None:
    with st.sidebar:
        st.markdown("### 🏘️ CommunityHub")
        st.caption("Menu · works on phone and desktop")
        if is_logged_in():
            profile = get_profile()
            if profile:
                st.write(format_name(profile))
                st.caption(
                    f"{profile.get('role', '').title()} · {profile.get('status', '')}"
                )
                if profile.get("status") == "approved":
                    st.divider()
                    current = st.session_state.get(NAV_KEY, NAV_DASHBOARD)
                    if st.button(
                        "Dashboard",
                        use_container_width=True,
                        type="primary" if current == NAV_DASHBOARD else "secondary",
                        key="nav_dashboard",
                    ):
                        st.session_state[NAV_KEY] = NAV_DASHBOARD
                        st.rerun()
                    if st.button(
                        "Profile",
                        use_container_width=True,
                        type="primary" if current == NAV_PROFILE else "secondary",
                        key="nav_profile",
                    ):
                        st.session_state[NAV_KEY] = NAV_PROFILE
                        st.rerun()
                    st.divider()
            if st.button("Logout", use_container_width=True):
                try:
                    client.auth.sign_out()
                except Exception:
                    pass
                clear_session()
                st.session_state.pop(RECOVERY_FLAG, None)
                st.session_state.pop(NAV_KEY, None)
                st.rerun()


if __name__ == "__main__":
    main()
