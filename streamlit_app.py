"""
AutoReserve — plateforme de restitution du provisionnement auto (BH Assurance).

Routeur de l'application (st.navigation). Les pages sont dans app_pages/.
Lancer :  streamlit run streamlit_app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="AutoReserve",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Refonte visuelle globale (CSS applique a toutes les pages) ---
st.markdown(
    """
    <style>
      :root {
        --ar-blue: #2a78d6; --ar-blue-dark: #184f95;
        --ar-ink: #0b0b0b; --ar-ink-2: #52514e; --ar-muted: #898781;
        --ar-surface: #ffffff; --ar-page: #f9f9f7;
        --ar-line: #e1e0d9; --ar-border: rgba(11,11,11,0.08);
      }
      .block-container { padding-top: 2.4rem; padding-bottom: 3rem; max-width: 1180px; }
      h1 { font-weight: 700; letter-spacing: -0.02em; color: var(--ar-ink); }
      h2, h3 { font-weight: 650; letter-spacing: -0.01em; color: var(--ar-ink); }

      /* Cartes KPI */
      [data-testid="stMetric"] {
        background: var(--ar-surface);
        border: 1px solid var(--ar-border);
        border-left: 3px solid var(--ar-blue);
        border-radius: 12px;
        padding: 14px 18px;
        box-shadow: 0 1px 2px rgba(11,11,11,0.04);
      }
      [data-testid="stMetricLabel"] p { color: var(--ar-ink-2); font-weight: 500;
        white-space: normal; }
      [data-testid="stMetricValue"] { color: var(--ar-ink); font-weight: 600;
        font-size: 1.5rem; white-space: nowrap; overflow: visible; }

      /* Onglets */
      .stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid var(--ar-line); }
      .stTabs [data-baseweb="tab"] { font-weight: 500; padding: 6px 10px; }
      .stTabs [aria-selected="true"] { color: var(--ar-blue); }

      /* Sidebar */
      [data-testid="stSidebar"] { background: #fcfcfb; border-right: 1px solid var(--ar-line); }
      .ar-brand { font-size: 1.35rem; font-weight: 700; letter-spacing: -0.02em;
                  color: var(--ar-ink); margin: 2px 0 0 0; }
      .ar-brand .dot { color: var(--ar-blue); }
      .ar-sub { color: var(--ar-ink-2); font-size: 0.82rem; margin-top: 2px; }
      .ar-meta { color: var(--ar-muted); font-size: 0.78rem; }

      /* Divers */
      hr { border-color: var(--ar-line); }
      .stButton button, .stDownloadButton button { border-radius: 9px; font-weight: 500; }
      [data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
      [data-testid="stAlert"] { border-radius: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Branding sidebar ---
with st.sidebar:
    st.markdown('<div class="ar-brand">📊 Auto<span class="dot">Reserve</span></div>',
                unsafe_allow_html=True)
    st.markdown('<div class="ar-sub">Provisionnement technique — assurance auto</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="ar-meta">BH Assurance · arrete au 31/12/2024</div>',
                unsafe_allow_html=True)
    st.divider()

# --- Navigation ---
pages = [
    st.Page("app_pages/accueil.py", title="Accueil", icon=":material/home:", default=True),
    st.Page("app_pages/ppna.py", title="Primes & PPNA", icon=":material/payments:"),
    st.Page("app_pages/synthese.py", title="Synthese Best Estimate", icon=":material/target:"),
    st.Page("app_pages/sensibilite.py", title="Sensibilite aux graves", icon=":material/warning:"),
    st.Page("app_pages/triangles.py", title="Triangles", icon=":material/grid_on:"),
    st.Page("app_pages/incertitude.py", title="Incertitude (bootstrap)", icon=":material/casino:"),
    st.Page("app_pages/simulateur.py", title="Simulateur", icon=":material/science:"),
    st.Page("app_pages/import_donnees.py", title="Import des donnees", icon=":material/upload_file:"),
    st.Page("app_pages/methodologie.py", title="Methodologie", icon=":material/menu_book:"),
]

st.navigation(pages).run()
