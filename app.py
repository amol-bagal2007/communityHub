import streamlit as st

from lib.admin_contacts import render_admin_contacts
from lib.auth import (
    clear_session,
    get_profile,
    is_admin,
    is_approved_user,
    is_logged_in,
    restore_session,
)
from lib.feedback import render_feedback
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
from lib.visibility import FLAG_FEEDBACK_TAB, is_feature_enabled, render_feature_toggle
from views.admin import render_admin_dashboard
from views.auth import render_auth
from views.user import render_profile_page, render_society_page, render_user_dashboard

NAV_KEY = "app_nav_page"
NAV_DASHBOARD = "dashboard"
NAV_PROFILE = "profile"
NAV_SOCIETY = "society"
NAV_CONTACT = "contact"
NAV_FEEDBACK = "feedback"


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

    if page == NAV_SOCIETY:
        st.title("🏘️ CommunityHub")
        render_society_page(client, profile)
        return

    if page == NAV_CONTACT:
        st.title("🏘️ CommunityHub")
        render_admin_contacts(client)
        return

    if page == NAV_FEEDBACK:
        st.title("🏘️ CommunityHub")
        if is_admin():
            render_feature_toggle(
                client,
                key=FLAG_FEEDBACK_TAB,
                label="Enable Feedback/Suggestion for members",
                help_text="When checked, approved members see Feedback/Suggestion in the left menu.",
                widget_key="admin_enable_feedback_tab",
            )
            st.divider()
            render_feedback(client, admin=True)
        elif is_feature_enabled(client, FLAG_FEEDBACK_TAB, default=False):
            render_feedback(client, admin=False)
        else:
            st.info("Feedback/Suggestion is not enabled yet. Ask your admin to turn it on.")
        return

    if is_admin():
        render_admin_dashboard(client)
    elif is_approved_user():
        render_user_dashboard(client)
    else:
        st.error("Access denied.")


def _show_feedback_nav(client) -> bool:
    if is_admin():
        return True
    return is_feature_enabled(client, FLAG_FEEDBACK_TAB, default=False)


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
                    if st.button(
                        "My Society",
                        use_container_width=True,
                        type="primary" if current == NAV_SOCIETY else "secondary",
                        key="nav_society",
                    ):
                        st.session_state[NAV_KEY] = NAV_SOCIETY
                        st.rerun()
                    if st.button(
                        "Contact",
                        use_container_width=True,
                        type="primary" if current == NAV_CONTACT else "secondary",
                        key="nav_contact",
                    ):
                        st.session_state[NAV_KEY] = NAV_CONTACT
                        st.rerun()
                    if _show_feedback_nav(client) and st.button(
                        "Feedback/Suggestion",
                        use_container_width=True,
                        type="primary" if current == NAV_FEEDBACK else "secondary",
                        key="nav_feedback",
                    ):
                        st.session_state[NAV_KEY] = NAV_FEEDBACK
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
