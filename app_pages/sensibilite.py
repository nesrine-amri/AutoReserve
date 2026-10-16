"""Sensibilite aux sinistres graves (ecretement par capping)."""

from __future__ import annotations

import streamlit as st

import app_data
from autoreserve.reporting.charts import fig_sensibilite_graves

MDT = 1_000_000

st.title("Sensibilite aux sinistres graves")
st.caption(
    "La charge sinistre est asymetrique : quelques graves gonflent les "
    "coefficients Chain-Ladder. L'ecretement (capping des paiements au seuil) "
    "stabilise la projection ; l'excedent paye est provisionne a part."
)

segment = st.radio("Segment", ["CORPOREL", "MATERIEL"], horizontal=True)

try:
    sens = app_data.sensibilite(segment)
except Exception as e:
    st.error(f"Donnees indisponibles : {e}")
    st.stop()

st.plotly_chart(fig_sensibilite_graves(sens, segment), use_container_width=True)

st.subheader("Table de sensibilite")
aff = sens.copy()
aff["seuil"] = (aff["seuil"] / MDT).round(3)
for c in ["ultime_brut", "ultime_ecrete", "ecart_vs_brut"]:
    aff[c] = (aff[c] / MDT).round(2)
aff = aff.rename(columns={
    "seuil": "Seuil (M DT)", "n_graves": "Nb graves",
    "part_graves_pct": "% charge graves", "ultime_brut": "Ultime brut (M)",
    "ultime_ecrete": "Ultime ecrete (M)", "ecart_vs_brut": "Ecart (M)",
    "ecart_pct": "Ecart %",
})
st.dataframe(aff, use_container_width=True)
st.caption(
    "Seuil = quantile des paiements vie-entiere par sinistre. "
    "Plus le seuil baisse, plus on ecrete, plus l'ultime projete diminue."
)
