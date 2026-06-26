APP_CSS = """
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
"""
