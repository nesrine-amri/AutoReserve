"""Page d'accueil : presentation et KPIs du Best Estimate consolide."""

from __future__ import annotations

import streamlit as st

import app_data

MDT = 1_000_000

st.title("AutoReserve")
st.caption(
    "Automatisation des provisions techniques — assurance automobile · "
    "PPNA · Chain-Ladder · Bornhuetter-Ferguson · Methode CM · Bootstrap ODP"
)
st.markdown(
    "Plateforme de **provisionnement sinistres auto** : triangles, methodes "
    "deterministes codees *from scratch*, ecretement des sinistres graves, "
    "**confrontation au SAP comptable reel** (boni / mali, IBNR) et "
    "**quantification de l'incertitude** (bootstrap ODP)."
)

st.divider()

try:
    conso = app_data.consolidation()
    total = conso["total"]

    st.subheader("Best Estimate consolide (Chain-Ladder ecrete)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Reserves estimees", f"{total['reserves_estimees']/MDT:,.1f} M DT")
    c2.metric("SAP comptable reel", f"{total['sap_comptable']/MDT:,.1f} M DT")
    ibnr = total["ibnr_estime"] / MDT
    c3.metric("IBNR net estime", f"{ibnr:+,.1f} M DT",
              delta="sous-provision" if ibnr > 0 else "boni",
              delta_color="inverse" if ibnr > 0 else "normal")
    paye = conso["synthese"]["paye"].sum() / MDT
    c4.metric("Paye cumule", f"{paye:,.1f} M DT")

    st.caption(
        "Lecture : les provisions comptables couvrent globalement le Best "
        "Estimate, avec une compensation entre corporel (sous-provisionne) et "
        "materiel (en boni). Detail dans **Synthese Best Estimate**."
    )
except FileNotFoundError:
    st.warning(
        "Base de primes (PPNA) introuvable dans data/processed/. "
        "Les methodes sinistres restent disponibles ; le BF sera desactive."
    )
except Exception as e:  # pragma: no cover
    st.error(f"Erreur au chargement des donnees : {e}")

st.divider()
st.markdown(
    "#### Navigation\n"
    "- **Synthese Best Estimate** — comparatif des 4 methodes vs reel, par segment\n"
    "- **Sensibilite aux graves** — impact de l'ecretement des sinistres graves\n"
    "- **Triangles** — developpement des paiements par segment\n"
    "- **Incertitude** — distribution bootstrap ODP (erreur de prediction, VaR 99,5%)\n"
    "- **Methodologie** — rappel des methodes actuarielles implementees"
)
