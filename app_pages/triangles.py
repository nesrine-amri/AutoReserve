"""Les 3 triangles de developpement par segment (ouverture / paiements / charge)."""

from __future__ import annotations

import streamlit as st

import app_data
from autoreserve.reporting.charts import fig_triangle_developpement

MDT = 1_000_000

st.title("Triangles de developpement")
st.caption(
    "Methodologie de l'encadrant : 3 triangles par segment — ouverture "
    "(nombre de sinistres), paiements cumules, et charge (paye + SAP)."
)

segment = st.radio("Segment", ["CORPOREL", "MATERIEL"], horizontal=True)

try:
    tris = app_data.triangles_trois(segment)
except Exception as e:
    st.error(f"Donnees indisponibles : {e}")
    st.stop()

if tris["paiements"].empty:
    st.warning("Triangle vide pour ce segment.")
    st.stop()

# Courbe de developpement (sur les paiements)
st.plotly_chart(fig_triangle_developpement(tris["paiements"], segment),
                use_container_width=True)

# Les 3 triangles en onglets
t_ouv, t_pai, t_chg = st.tabs(
    ["Ouverture (nombre)", "Paiements cumules (M DT)", "Charge = Paye + SAP (M DT)"]
)

with t_ouv:
    st.caption("Nombre de sinistres uniques ouverts par (survenance x developpement).")
    st.dataframe(tris["ouverture"].round(0), use_container_width=True)

with t_pai:
    st.caption("Paiements cumules par (survenance x developpement).")
    st.dataframe((tris["paiements"] / MDT).round(2), use_container_width=True)

with t_chg:
    st.caption("Charge dossier/dossier = paiements cumules + SAP courant.")
    st.dataframe((tris["charge"] / MDT).round(2), use_container_width=True)

st.caption("Cases vides = futur non observe (sous la diagonale courante).")

st.divider()

# --- Triangle d'entree par methode ---
st.subheader("Triangle d'entree par methode")
st.caption("Quel triangle chaque methode de provisionnement utilise-t-elle ?")

m_cl, m_bf, m_cm = st.tabs(["Chain-Ladder", "Bornhuetter-Ferguson", "Methode CM"])

with m_cl:
    st.markdown(
        "**Chain-Ladder** (brut et ecrete) projette le triangle des "
        "**paiements cumules** via les coefficients de developpement."
    )
    st.dataframe((tris["paiements"] / MDT).round(2), use_container_width=True)
    st.caption("Entree : paiements cumules (M DT).")

with m_bf:
    st.markdown(
        "**Bornhuetter-Ferguson** part du meme triangle de **paiements cumules**, "
        "mais pondere par un a priori (prime acquise x loss ratio) pour les "
        "annees recentes peu matures."
    )
    st.dataframe((tris["paiements"] / MDT).round(2), use_container_width=True)
    st.caption("Entree : paiements cumules (M DT) + a priori externe.")

with m_cm:
    st.markdown(
        "**Methode du Cout Moyen** raisonne sur la **charge** "
        "(paiements cumules + SAP), dossier par dossier."
    )
    st.dataframe((tris["charge"] / MDT).round(2), use_container_width=True)
    st.caption("Entree : charge = paye + SAP (M DT).")
