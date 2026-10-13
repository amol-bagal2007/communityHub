from __future__ import annotations

import textwrap

import streamlit as st

from lib.admin_contacts import format_admin_contact_offline, load_admin_contacts
from lib.supabase_client import SchemaClient

DISCLAIMER_VERSION = "1.4"

DISCLAIMER_TITLE = "User Acknowledgement & Disclaimer"

SHOW_DISCLAIMER_KEY = "show_disclaimer_screen"

_DISCLAIMER_INTRO = """
By creating an account on CommunityHub, you acknowledge and agree to the following:

1. **This platform is restricted to society members only. If you are not a society residential 
(Owner & Tenant), then please do not create an account.

2. **It is a platform for society members to discover, add/update information about the genuine vendors, freelancers,  local-businesses, 
local-services, etc. Note : It is not a platform for social media posts or comments.

3. **No warranty / platform risk.** CommunityHub and its owner(s), administrators, and affiliates provide this platform on an “as is” and “as available” basis. Reasonable technical and administrative measures have been considered to reduce the likelihood of data loss, unauthorized access, or compromise of personal information; however, **no absolute guarantee can be given**, and residual risk remains. Users should remain mindful of this when sharing information online. To the fullest extent permitted by law, the owner(s), administrators, and affiliates shall not be liable for any data loss, service interruption, unauthorized access, disclosure, alteration, or compromise of personal or other information, including any transmission to or exposure involving third parties.

4. **Limitation of liability.** Although reasonable steps have been taken by the administrator to mitigate platform and operational risks, **such measures do not constitute a warranty or assurance of uninterrupted, error-free, or fully secure service.** The owner(s) and administrators of this CommunityHub shall not be responsible or answerable for any claim, loss, damage, cost, expense, dispute, or inquiry arising out of or related to your use of the platform, your interactions with other members or vendors, or any reliance on information shared through the application. Users are advised to exercise due care and remain mindful of these inherent limitations.

5. **User responsibility & credential security.** You are solely responsible for the accuracy of information you submit, for safeguarding your login credentials, and for all activity conducted under your account. **Do not share your User ID, email login, or password with any other person.** You remain responsible for any misuse arising from disclosure of your credentials.
""".strip()

_DISCLAIMER_OUTRO = """
7. **Truthful information.** You agree not to provide false, incomplete, or misleading information, and not to misrepresent yourself or otherwise deceive society members or administrators in any manner.

8. **Intended use — vendors.** CommunityHub is intended to help society members discover and share **recommended vendors** and related community service information. Vendor details, ratings, and reviews are member-contributed and are not guarantees or endorsements by the application owner.

9. **Intended use — groups & interests.** Members may state interest in society groups so that people with similar interests can identify one another and **connect offline** at their own discretion. The platform does not guarantee introductions, outcomes, or the conduct of any member.

10. **Enforcement without prior consent.** If you are found, in the reasonable judgment of the application owner/administrator, to have violated these terms or misused the platform, the owner/administrator may suspend, deactivate, or permanently disable your account without your prior consent and without prior notice where reasonably necessary to protect the community or the platform.

11. **Further action.** Where misconduct is established or reasonably suspected, the application owner/administrator reserves the right to take all lawful actions available, which may include internal disciplinary measures and, where appropriate, civil and/or criminal legal proceedings.

If you do not agree to these terms, do not register or use CommunityHub.
""".strip()


def build_disclaimer_text(client: SchemaClient) -> str:
    admins, _error = load_admin_contacts(client)
    contact_line = format_admin_contact_offline(admins)
    point_6 = (
        "6. **Password recovery.** Passwords are stored only in hashed form by the "
        "authentication provider and **cannot be retrieved or emailed in plain text** "
        "by this application. If you forget your password, request a reset through the "
        "in-app **Forgot Password** flow (administrator-assisted temporary password), "
        f"or contact the administrator offline: {contact_line}."
    )
    return f"{_DISCLAIMER_INTRO}\n\n{point_6}\n\n{_DISCLAIMER_OUTRO}"


def is_disclaimer_view() -> bool:
    return bool(st.session_state.get(SHOW_DISCLAIMER_KEY))


def open_disclaimer_view() -> None:
    st.session_state[SHOW_DISCLAIMER_KEY] = True


def close_disclaimer_view() -> None:
    st.session_state[SHOW_DISCLAIMER_KEY] = False


def render_disclaimer_screen(client: SchemaClient) -> None:
    """Full-page disclaimer (opened from the signup checkbox link)."""
    st.subheader(DISCLAIMER_TITLE)
    st.caption("Please read carefully before accepting on the Sign Up page.")
    with st.container(border=True):
        st.markdown(build_disclaimer_text(client))
    if st.button("← Back to Sign Up", type="primary", use_container_width=True):
        close_disclaimer_view()
        st.session_state["auth_prefer_signup"] = True
        st.rerun()


def render_signup_disclaimer(*, key: str = "signup_disclaimer_accepted") -> bool:
    """Checkbox with highlighted disclaimer link; full text is on a separate screen."""
    st.html(
        textwrap.dedent(
            """
            <style>
            div.ch-disclaimer-accept button[kind="secondary"] {
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
                padding: 0.15rem 0 !important;
                color: #0b57d0 !important;
                font-weight: 700 !important;
                text-decoration: underline !important;
                min-height: 1.5rem !important;
                height: auto !important;
                line-height: 1.4 !important;
            }
            div.ch-disclaimer-accept button[kind="secondary"]:hover {
                color: #0842a0 !important;
                background: transparent !important;
                border: none !important;
            }
            </style>
            """
        )
    )

    check_col, text_col = st.columns([0.06, 0.94])
    with check_col:
        accepted = st.checkbox(
            "Accept disclaimer",
            key=key,
            label_visibility="collapsed",
        )
    with text_col:
        st.markdown('<div class="ch-disclaimer-accept">', unsafe_allow_html=True)
        prefix, link = st.columns([0.55, 0.45])
        prefix.markdown("I have read, understood, and agree to the")
        if link.button(DISCLAIMER_TITLE, key="open_disclaimer_link", type="secondary"):
            open_disclaimer_view()
            st.session_state["auth_prefer_signup"] = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    return bool(accepted)
