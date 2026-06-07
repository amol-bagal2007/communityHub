import streamlit as st

from lib.auth import (
    clear_session,
    get_profile,
    is_admin,
    is_approved_user,
    is_logged_in,
    restore_session,
)
from lib.pwa import inject_pwa_meta
from lib.supabase_client import get_client
from views.admin import render_admin_dashboard
from views.auth import render_auth
from views.user import render_user_dashboard


def main() -> None:
    st.set_page_config(
        page_title="CommunityHub",
        page_icon="🏘️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_pwa_meta()

    client = get_client()
    restore_session(client)

    _render_sidebar(client)

    if not is_logged_in():
        st.title("🏘️ CommunityHub")
        st.markdown("Your society community portal — events, vendors, and more.")
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
        if st.button("Logout"):
            client.auth.sign_out()
            clear_session()
            st.rerun()
        return

    if profile.get("status") == "rejected":
        st.error("Your registration was rejected. Contact your society admin.")
        if st.button("Logout"):
            client.auth.sign_out()
            clear_session()
            st.rerun()
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
        if is_logged_in():
            profile = get_profile()
            if profile:
                st.write(profile.get("full_name", ""))
                st.caption(f"{profile.get('role', '').title()} · {profile.get('status', '')}")
            if st.button("Logout", use_container_width=True):
                try:
                    client.auth.sign_out()
                except Exception:
                    pass
                clear_session()
                st.rerun()


if __name__ == "__main__":
    main()
