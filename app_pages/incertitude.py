"""Incertitude — bootstrap ODP (distribution des provisions)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import app_data
from autoreserve.reporting.charts import fig_bootstrap_distribution

MDT = 1_000_000

st.title("Incertitude des provisions — bootstrap ODP")
st.caption(
    "Bootstrap Over-Dispersed Poisson (England & Verrall) : au lieu d'une valeur "
    "unique, une distribution de la provision, combinant erreur d'estimation "
    "(reechantillonnage des residus) et erreur de processus (simulation Gamma)."
)

segment = st.radio("Segment", ["CORPOREL", "MATERIEL"], horizontal=True)
n_sim = st.select_slider("Nombre de simulations", [500, 1000, 2000, 5000], value=2000)

try:
    res = app_data.bootstrap(segment, n_sim=n_sim)
except Exception as e:
    st.error(f"Donnees indisponibles : {e}")
    st.stop()

if "error" in res:
    st.warning(res["error"])
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Best Estimate (CL)", f"{res['best_estimate_cl']/MDT:,.1f} M DT")
c2.metric("Erreur de prediction (SE)", f"{res['std']/MDT:,.1f} M DT",
          help="Ecart-type de la distribution predictive")
c3.metric("Coefficient de variation", f"{res['cv_pct']:.1f} %",
          help="SE / Best Estimate — mesure relative de l'incertitude")
c4.metric("Provision a 99,5 % (SII)", f"{res['quantiles']['99.5%']/MDT:,.1f} M DT",
          help="Quantile 99,5 % ~ niveau de securite Solvabilite II")

st.plotly_chart(fig_bootstrap_distribution(res, segment), use_container_width=True)

st.subheader("Quantiles de la provision")
qdf = pd.DataFrame(
    {"Provision (M DT)": {k: v / MDT for k, v in res["quantiles"].items()}}
).round(2)
qdf["Marge vs Best Estimate (M DT)"] = (
    qdf["Provision (M DT)"] - res["best_estimate_cl"] / MDT
).round(2)
st.dataframe(qdf, use_container_width=True)

st.caption(
    f"Dispersion phi = {res['phi']:,.0f} · {res['n_sim']} simulations. "
    "La marge au quantile 99,5 % represente le capital de securite a immobiliser "
    "au-dela du Best Estimate (lecture Solvabilite II)."
)
