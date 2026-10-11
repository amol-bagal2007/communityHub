from __future__ import annotations

import textwrap

import streamlit as st


def inject_mobile_styles() -> None:
    """Viewport + CSS so CommunityHub is usable primarily on phone browsers."""
    # Use st.html (not markdown): indented <style> in markdown becomes a visible code block.
    st.html(
        textwrap.dedent(
            """
            <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
            <style>
            html, body, [data-testid="stAppViewContainer"] {
                max-width: 100vw;
                overflow-x: hidden;
            }

            button,
            [data-testid="stBaseButton-primary"],
            [data-testid="stBaseButton-secondary"],
            [data-testid="baseButton-primary"],
            [data-testid="baseButton-secondary"] {
                min-height: 2.75rem !important;
            }

            input, textarea, select,
            [data-baseweb="input"],
            [data-baseweb="textarea"],
            [data-baseweb="select"] {
                font-size: 16px !important;
            }

            .stTabs [data-baseweb="tab-list"] {
                gap: 0.35rem;
                overflow-x: auto !important;
                flex-wrap: nowrap !important;
                -webkit-overflow-scrolling: touch;
                scrollbar-width: thin;
            }
            .stTabs [data-baseweb="tab"] {
                white-space: nowrap;
                font-size: 0.92rem;
                padding-left: 0.7rem;
                padding-right: 0.7rem;
            }

            [data-testid="stExpander"],
            div[data-testid="stVerticalBlockBorderWrapper"] {
                border-radius: 0.75rem;
            }

            [data-testid="stAppViewContainer"] > .main {
                padding-left: max(0.6rem, env(safe-area-inset-left));
                padding-right: max(0.6rem, env(safe-area-inset-right));
                padding-bottom: max(1.25rem, env(safe-area-inset-bottom));
            }

            h1 { font-size: 1.55rem !important; line-height: 1.25 !important; }
            h2, h3 { font-size: 1.2rem !important; }

            @media (max-width: 768px) {
                section[data-testid="stSidebar"] {
                    min-width: 0 !important;
                }

                div[data-testid="stHorizontalBlock"] {
                    flex-wrap: wrap !important;
                    gap: 0.35rem 0 !important;
                }
                div[data-testid="stHorizontalBlock"] > div {
                    min-width: min(100%, 16rem) !important;
                    flex: 1 1 100% !important;
                }

                .main .block-container {
                    padding-top: 1rem !important;
                    padding-left: 0.75rem !important;
                    padding-right: 0.75rem !important;
                    max-width: 100% !important;
                }

                div.stButton > button,
                div.stDownloadButton > button,
                div[data-testid="stFormSubmitButton"] > button {
                    width: 100%;
                }

                [data-testid="stMetricValue"] {
                    font-size: 1.25rem !important;
                }

                [data-testid="stForm"] {
                    padding: 0.35rem 0;
                }
            }

            @media (max-width: 420px) {
                h1 { font-size: 1.35rem !important; }
                .stTabs [data-baseweb="tab"] {
                    font-size: 0.85rem;
                    padding-left: 0.55rem;
                    padding-right: 0.55rem;
                }
            }
            </style>
            """
        )
    )


def render_mobile_top_nav(*, current: str, show_nav: bool) -> str | None:
    """
    Phone-friendly Dashboard / Profile controls in the main pane.
    Returns requested page key when a nav button is pressed, else None.
    """
    if not show_nav:
        return None

    st.caption("Quick navigation")
    c1, c2 = st.columns(2)
    requested = None
    if c1.button(
        "Dashboard",
        key="mobile_nav_dashboard",
        use_container_width=True,
        type="primary" if current == "dashboard" else "secondary",
    ):
        requested = "dashboard"
    if c2.button(
        "Profile",
        key="mobile_nav_profile",
        use_container_width=True,
        type="primary" if current == "profile" else "secondary",
    ):
        requested = "profile"
    return requested
