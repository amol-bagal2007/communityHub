from __future__ import annotations

import streamlit as st

DISCLAIMER_VERSION = "1.2"

DISCLAIMER_TITLE = "User Acknowledgement & Disclaimer"

DISCLAIMER_TEXT = """
By creating an account on CommunityHub, you acknowledge and agree to the following:

1. **No warranty / platform risk.** CommunityHub and its owner(s), administrators, and affiliates provide this platform on an “as is” and “as available” basis. Reasonable technical and administrative measures have been considered to reduce the likelihood of data loss, unauthorized access, or compromise of personal information; however, **no absolute guarantee can be given**, and residual risk remains. Users should remain mindful of this when sharing information online. To the fullest extent permitted by law, the owner(s), administrators, and affiliates shall not be liable for any data loss, service interruption, unauthorized access, disclosure, alteration, or compromise of personal or other information, including any transmission to or exposure involving third parties.

2. **Limitation of liability.** Although reasonable steps have been taken by the administrator to mitigate platform and operational risks, **such measures do not constitute a warranty or assurance of uninterrupted, error-free, or fully secure service.** The owner(s) and administrators of this CommunityHub shall not be responsible or answerable for any claim, loss, damage, cost, expense, dispute, or inquiry arising out of or related to your use of the platform, your interactions with other members or vendors, or any reliance on information shared through the application. Users are advised to exercise due care and remain mindful of these inherent limitations.

3. **User responsibility & credential security.** You are solely responsible for the accuracy of information you submit, for safeguarding your login credentials, and for all activity conducted under your account. **Do not share your User ID, email login, or password with any other person.** You remain responsible for any misuse arising from disclosure of your credentials.

4. **Password recovery.** Passwords are stored only in hashed form by the authentication provider and **cannot be retrieved or emailed in plain text** by this application. If you forget your password, request a reset through the in-app **Forgot Password** flow (administrator-assisted temporary password), or contact the administrator offline: **Amol Bagal — 9535113766**.

5. **Truthful information.** You agree not to provide false, incomplete, or misleading information, and not to misrepresent yourself or otherwise deceive society members or administrators in any manner.

6. **Intended use — vendors.** CommunityHub is intended to help society members discover and share **recommended vendors** and related community service information. Vendor details, ratings, and reviews are member-contributed and are not guarantees or endorsements by the application owner.

7. **Intended use — groups & interests.** Members may state interest in society groups so that people with similar interests can identify one another and **connect offline** at their own discretion. The platform does not guarantee introductions, outcomes, or the conduct of any member.

8. **Enforcement without prior consent.** If you are found, in the reasonable judgment of the application owner/administrator, to have violated these terms or misused the platform, the owner/administrator may suspend, deactivate, or permanently disable your account without your prior consent and without prior notice where reasonably necessary to protect the community or the platform.

9. **Further action.** Where misconduct is established or reasonably suspected, the application owner/administrator reserves the right to take all lawful actions available, which may include internal disciplinary measures and, where appropriate, civil and/or criminal legal proceedings.

If you do not agree to these terms, do not register or use CommunityHub.
""".strip()


def render_signup_disclaimer(*, key: str = "signup_disclaimer_accepted") -> bool:
    """Show disclaimer text and required acceptance checkbox. Returns whether accepted."""
    st.markdown(f"**{DISCLAIMER_TITLE}**")
    with st.container(border=True):
        st.markdown(DISCLAIMER_TEXT)
    accepted = st.checkbox(
        "I have read, understood, and agree to the User Acknowledgement & Disclaimer above. *",
        key=key,
    )
    st.caption("You must accept the disclaimer to complete registration.")
    return bool(accepted)
