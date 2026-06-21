from __future__ import annotations

import streamlit as st
from lib.supabase_client import SchemaClient

SESSION_KEY = "auth_session"
PROFILE_KEY = "user_profile"


def init_session_state() -> None:
    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = None
    if PROFILE_KEY not in st.session_state:
        st.session_state[PROFILE_KEY] = None


def restore_session(client: SchemaClient) -> bool:
    init_session_state()
    session = st.session_state.get(SESSION_KEY)
    if not session:
        return False
    try:
        client.auth.set_session(session.access_token, session.refresh_token)
        profile = fetch_profile(client)
        if profile:
            st.session_state[PROFILE_KEY] = profile
            return True
    except Exception:
        clear_session()
    return False


def fetch_profile(client: SchemaClient) -> dict | None:
    user = client.auth.get_user()
    if not user or not user.user:
        return None
    result = (
        client.table("profiles")
        .select("*, member_groups(name), member_sub_groups(name)")
        .eq("id", user.user.id)
        .single()
        .execute()
    )
    return result.data


def set_session(client: SchemaClient, session) -> dict | None:
    st.session_state[SESSION_KEY] = session
    client.auth.set_session(session.access_token, session.refresh_token)
    profile = fetch_profile(client)
    st.session_state[PROFILE_KEY] = profile
    return profile


def clear_session() -> None:
    st.session_state[SESSION_KEY] = None
    st.session_state[PROFILE_KEY] = None


def get_profile() -> dict | None:
    return st.session_state.get(PROFILE_KEY)


def is_logged_in() -> bool:
    return st.session_state.get(SESSION_KEY) is not None


def is_admin() -> bool:
    profile = get_profile()
    return bool(profile and profile.get("role") == "admin" and profile.get("status") == "approved")


def is_approved_user() -> bool:
    profile = get_profile()
    return bool(profile and profile.get("status") == "approved")
