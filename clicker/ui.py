"""
Streamlit page setup and shared UI helpers.
"""

import streamlit as st


def configure_page():
    st.set_page_config(
        page_title="STL to Cherry MX Clicker",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def inject_css():
    st.markdown(
        """
        <style>
            header[data-testid="stHeader"] {height: 0rem; visibility: hidden;}
            div[data-testid="stToolbar"] {visibility: hidden; height: 0%; position: fixed;}
            div[data-testid="stDecoration"] {visibility: hidden; height: 0%;}
            footer {visibility: hidden;}
            .block-container {
                padding-top: 0.35rem !important;
                padding-bottom: 0.25rem !important;
                padding-left: 1.25rem !important;
                padding-right: 1.25rem !important;
                max-width: 100% !important;
            }
            section[data-testid="stSidebar"] .block-container {
                padding-top: 1rem !important;
                padding-bottom: 1rem !important;
            }
            div[data-testid="stVerticalBlock"] {gap: 0.35rem !important;}
            .stPlotlyChart {margin-top: -0.25rem !important;}
            h1, h2, h3, p {margin-top: 0rem !important; margin-bottom: 0.2rem !important;}
            .small-note {font-size: 0.78rem; color: #6b7280;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_session_state():
    for key, value in {
        "generated": False,
        "top_mesh": None,
        "bottom_mesh": None,
        "last_signature": None,
        "export_name": "clicker",
    }.items():
        st.session_state.setdefault(key, value)


def reset_generated_meshes():
    st.session_state.generated = False
    st.session_state.top_mesh = None
    st.session_state.bottom_mesh = None
