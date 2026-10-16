"""Primes & PPNA (Etape 1) : unification, PPNA reglementaire, validation encadrant."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import app_data
from autoreserve.reporting.charts import fig_validation_ppna

MDT = 1_000_000

st.title("Primes & PPNA")
st.caption(
    "Etape 1 : unification des bases de production, calcul de la PPNA "
    "reglementaire (norme CGA) au 31/12/2024 et validation contre le "
    "Compte Technique de l'encadrant."
)

# --- Unification ---
st.subheader("Unification des bases de production")
dfu = app_data.charger_base_unifiee()
if dfu is not None:
    c1, c2, c3 = st.columns(3)
    c1.metric("Bases sources unifiees", "6", help="3 fichiers CA (2022/2023/2024) x 2 onglets (individuelle + flotte)")
    c2.metric("Polices consolidees", f"{len(dfu):,}".replace(",", " "))
    exs = sorted(pd.to_numeric(dfu["ANNEE_EXERCICE"], errors="coerce").dropna().astype(int).unique())
    c3.metric("Exercices", f"{exs[0]}–{exs[-1]}" if exs else "—")
    st.caption(
        "Normalisation des colonnes (coquilles, doublons emise/corrigee), "
        "selection de la **prime corrigee** et exclusion des contre-passations."
    )
else:
    st.info("Base unifiee indisponible (data/processed/base_unifiee.parquet).")

st.divider()

# --- Validation vs Compte Technique ---
st.subheader("Validation 2024 vs Compte Technique de l'encadrant")
val = app_data.validation_ppna()
if val:
    c1, c2, c3 = st.columns(3)
    e_p = 100 * (val["primes_calc"] - val["primes_cible"]) / val["primes_cible"]
    e_pp = 100 * (val["ppna_calc"] - val["ppna_cible"]) / val["ppna_cible"]
    c1.metric("Primes emises 2024", f"{val['primes_calc']/MDT:,.1f} M DT",
              delta=f"{e_p:+.2f}% vs cible", delta_color="off")
    c2.metric("PPNA 2024", f"{val['ppna_calc']/MDT:,.1f} M DT",
              delta=f"{e_pp:+.2f}% vs cible", delta_color="off")
    c3.metric("Taux de non-acquisition", f"{val['taux_calc']:.1f} %",
              delta=f"cible {val['taux_cible']:.1f} %", delta_color="off")

    st.plotly_chart(fig_validation_ppna(val), use_container_width=True)
    st.caption(
        "Primes emises rapprochees a −0,18 % (base corrigee brute). Le taux de "
        "non-acquisition reproduit celui du Compte Technique. L'ecart residuel "
        "sur la PPNA reflete une difference de perimetre d'extraction."
    )

    # --- Base de calcul PPNA au regard de NC 29 ---
    st.markdown("##### Base de calcul PPNA (norme NC 29)")
    com = val.get("ppna_commerciale", float("nan"))
    b1, b2 = st.columns(2)
    b1.metric("PPNA sur prime nette (retenue)", f"{val['ppna_calc']/MDT:,.1f} M DT",
              help="Base alignee sur le Compte Technique de l'encadrant ; "
                   "les frais sont traites en frais d'acquisition differes.")
    if com == com:  # not NaN
        b2.metric("PPNA sur prime commerciale (NC 29)", f"{com/MDT:,.1f} M DT",
                  delta=f"+{(com-val['ppna_calc'])/MDT:,.1f} M (chargements)",
                  delta_color="off",
                  help="NC 29 : prorata temporis sur la prime commerciale = "
                       "prime de risque + chargements.")
    st.caption(
        "NC 29 definit la PPNA sur la **prime commerciale** (prime + chargements). "
        "La base **prime nette** retenue ici correspond a la pratique de l'encadrant "
        "(chargements d'acquisition differes separement) et doit etre justifiee en "
        "annexe. La version prime commerciale est fournie pour transparence."
    )
else:
    st.info("Base PPNA indisponible (data/processed/base_avec_ppna_v2.parquet).")

st.divider()

# --- PPNA par exercice x type ---
st.subheader("PPNA reglementaire par exercice et type de base")
agg = app_data.ppna_par_segment()
if agg is not None:
    aff = agg.copy()
    for c in ["prime_emise_nette", "frais_emis", "ppna_reglementaire", "prime_acquise_nette"]:
        if c in aff.columns:
            aff[c] = (aff[c] / MDT).round(2)
    cols = {"nb_polices": "Nb polices", "prime_emise_nette": "Prime emise (M)",
            "ppna_reglementaire": "PPNA (M)", "prime_acquise_nette": "Prime acquise (M)",
            "taux_non_acquis_pct": "Taux non-acquis %"}
    aff = aff[[c for c in cols if c in aff.columns]].rename(columns=cols)
    st.dataframe(aff, use_container_width=True)
    st.caption(
        "La PPNA se concentre sur l'exercice 2024 (les contrats 2022/2023 sont "
        "eteints au 31/12/2024). Montants en M DT."
    )
