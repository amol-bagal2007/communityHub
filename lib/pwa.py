import streamlit as st


def inject_pwa_meta() -> None:
    st.markdown(
        """
        <link rel="manifest" href="app/static/manifest.json">
        <meta name="theme-color" content="#1a5276">
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="default">
        <meta name="apple-mobile-web-app-title" content="CommunityHub">
        <meta name="format-detection" content="telephone=yes">
        <link rel="apple-touch-icon" href="app/static/icon-192.png">
        """,
        unsafe_allow_html=True,
    )
