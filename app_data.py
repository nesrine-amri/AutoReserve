"""
Chargement des donnees pour la plateforme Streamlit (avec cache).

Centralise les acces aux bases et l'execution des methodes actuarielles pour
que chaque page reste legere. Tout est mis en cache par Streamlit.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from autoreserve.config import (
    PROCESSED_DIR, ANNEE_DEBUT_SINISTRES,
    PRIMES_EMISES_2024_CT, PPNA_2024_CT,
)
from autoreserve.actuarial import aggregate_ppna_by_segment
from autoreserve.sinistres.loader import load_sinistres
from autoreserve.sinistres.triangles import (
    build_triangle_paiements,
    build_triangle_ouverture,
    build_triangle_charge,
)
from autoreserve.sinistres.consolidation import consolider_best_estimate
from autoreserve.sinistres.ecretement import sensibilite_seuil
from autoreserve.sinistres.bootstrap import bootstrap_odp

BASE_PPNA = "base_avec_ppna_v2.parquet"


@st.cache_data(show_spinner="Chargement de la base sinistres...")
def charger_sinistres() -> pd.DataFrame:
    return load_sinistres(annee_debut=ANNEE_DEBUT_SINISTRES, verbose=False)


@st.cache_data(show_spinner=False)
def charger_ppna() -> pd.DataFrame | None:
    chemin = PROCESSED_DIR / BASE_PPNA
    if not chemin.exists():
        return None
    return pd.read_parquet(chemin)


@st.cache_data(show_spinner=False)
def charger_base_unifiee() -> pd.DataFrame | None:
    chemin = PROCESSED_DIR / "base_unifiee.parquet"
    if not chemin.exists():
        return None
    return pd.read_parquet(chemin)


@st.cache_data(show_spinner="Agregation PPNA...")
def ppna_par_segment() -> pd.DataFrame | None:
    dp = charger_ppna()
    if dp is None:
        return None
    return aggregate_ppna_by_segment(dp)


@st.cache_data(show_spinner=False)
def validation_ppna() -> dict:
    """Rapprochement PPNA/primes 2024 avec le Compte Technique de l'encadrant."""
    dp = charger_ppna()
    if dp is None:
        return {}
    d24 = dp[dp["ANNEE_EXERCICE"] == 2024]
    prime = float(pd.to_numeric(d24["TOTAL_PRIME_NETTE"], errors="coerce").sum())
    ppna = float(pd.to_numeric(d24["PPNA_REGLEMENTAIRE"], errors="coerce").sum())
    pa = float(pd.to_numeric(d24["PRIME_ACQUISE_NETTE"], errors="coerce").sum())
    pa_cible = PRIMES_EMISES_2024_CT - PPNA_2024_CT
    # PPNA sur prime commerciale (prime + chargements) = base NC 29 stricte
    ppna_com = float(pd.to_numeric(d24["PPNA_TOTALE_INFO"], errors="coerce").sum()) \
        if "PPNA_TOTALE_INFO" in d24.columns else float("nan")
    return {
        "primes_calc": prime, "primes_cible": float(PRIMES_EMISES_2024_CT),
        "ppna_calc": ppna, "ppna_cible": float(PPNA_2024_CT),
        "pa_calc": pa, "pa_cible": float(pa_cible),
        "ppna_commerciale": ppna_com,
        "taux_calc": 100 * ppna / prime if prime else float("nan"),
        "taux_cible": 100 * PPNA_2024_CT / PRIMES_EMISES_2024_CT,
    }


@st.cache_data(show_spinner="Consolidation Best Estimate...")
def consolidation(quantile_ecretement: float = 0.99) -> dict:
    df = charger_sinistres()
    df_ppna = charger_ppna()
    return consolider_best_estimate(df, df_ppna=df_ppna,
                                    quantile_ecretement=quantile_ecretement)


@st.cache_data(show_spinner=False)
def triangle(segment: str) -> pd.DataFrame:
    df = charger_sinistres()
    return build_triangle_paiements(df, nature=segment, cumule=True)


@st.cache_data(show_spinner="Construction des triangles...")
def triangles_trois(segment: str) -> dict:
    """Les 3 triangles de la methodologie : ouverture (nombre), paiements, charge."""
    df = charger_sinistres()
    return {
        "ouverture": build_triangle_ouverture(df, nature=segment, cumule=True),
        "paiements": build_triangle_paiements(df, nature=segment, cumule=True),
        "charge": build_triangle_charge(df, nature=segment),
    }


@st.cache_data(show_spinner="Calcul de la sensibilite aux graves...")
def sensibilite(segment: str) -> pd.DataFrame:
    df = charger_sinistres()
    return sensibilite_seuil(df, nature=segment)


@st.cache_data(show_spinner="Simulation bootstrap ODP (quelques secondes)...")
def bootstrap(segment: str, n_sim: int = 2000) -> dict:
    return bootstrap_odp(triangle(segment), n_sim=n_sim, seed=42)
