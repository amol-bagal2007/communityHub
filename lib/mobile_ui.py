from __future__ import annotations

import streamlit as st


def inject_mobile_styles() -> None:
    """Viewport + CSS so CommunityHub is usable primarily on phone browsers."""
    st.markdown(
        """
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
        <style>
        html, body, [data-testid="stAppViewContainer"] {
            max-width: 100vw;
            overflow-x: hidden;
        }

        /* Comfortable tap targets */
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
            font-size: 16px !important; /* avoids iOS zoom-on-focus */
        }

        /* Tabs: horizontal scroll instead of crushing labels */
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

        /* Expanders and bordered cards breathe on small screens */
        [data-testid="stExpander"],
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 0.75rem;
        }

        /* Main content padding for notched phones */
        [data-testid="stAppViewContainer"] > .main {
            padding-left: max(0.6rem, env(safe-area-inset-left));
            padding-right: max(0.6rem, env(safe-area-inset-right));
            padding-bottom: max(1.25rem, env(safe-area-inset-bottom));
        }

        /* Compact header */
        h1 { font-size: 1.55rem !important; line-height: 1.25 !important; }
        h2, h3 { font-size: 1.2rem !important; }

        /* Mobile nav chips */
        .ch-mobile-nav {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin: 0.25rem 0 0.75rem 0;
        }

        @media (max-width: 768px) {
            /* Hide wide desktop sidebar chrome pressure; users use top nav */
            section[data-testid="stSidebar"] {
                min-width: 0 !important;
            }

            /* Stack most horizontal column rows for readability */
            div[data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
                gap: 0.35rem 0 !important;
            }
            div[data-testid="stHorizontalBlock"] > div {
                min-width: min(100%, 16rem) !important;
                flex: 1 1 100% !important;
            }

            /* Keep compact action rows usable (e.g. title + View) */
            div[data-testid="stHorizontalBlock"].ch-keep-row > div,
            div.ch-keep-row div[data-testid="column"] {
                flex: 1 1 auto !important;
            }

            .main .block-container {
                padding-top: 1rem !important;
                padding-left: 0.75rem !important;
                padding-right: 0.75rem !important;
                max-width: 100% !important;
            }

            /* Full-width primary actions */
            div.stButton > button,
            div.stDownloadButton > button,
            div[data-testid="stFormSubmitButton"] > button {
                width: 100%;
            }

            /* Metric / caption density */
            [data-testid="stMetricValue"] {
                font-size: 1.25rem !important;
            }

            /* Forms: less cramped vertical rhythm */
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
        """,
        unsafe_allow_html=True,
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
