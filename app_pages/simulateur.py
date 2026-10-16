"""Simulateur : validation des methodes sur donnees a verite connue."""

from __future__ import annotations

import numpy as np
import streamlit as st

from autoreserve.simulation import generer_triangle_paiements, ultimes_croissance
from autoreserve.sinistres.chain_ladder import chain_ladder_full
from autoreserve.sinistres.bootstrap import bootstrap_odp
from autoreserve.reporting.charts import fig_simulation_recuperation

MDT = 1_000_000

st.title("Simulateur de validation")
st.caption(
    "On fabrique un triangle dont l'ultime est CONNU par construction, puis on "
    "verifie que le Chain-Ladder le retrouve. Sans bruit, il doit tomber juste ; "
    "avec du bruit, l'ecart mesure la robustesse."
)

# --- Parametres ---
c1, c2, c3 = st.columns(3)
with c1:
    n_annees = st.slider("Nombre d'annees", 3, 8, 5)
    ultime_base = st.number_input("Ultime de base (M DT)", 1.0, 100.0, 10.0, step=1.0)
with c2:
    croissance = st.slider("Croissance annuelle (%)", -10, 30, 8)
    decay = st.slider("Decroissance du developpement", 0.3, 0.9, 0.6, step=0.05,
                      help="Plus c'est bas, plus les paiements sont concentres au debut")
with c3:
    bruit = st.slider("Niveau de bruit (CV %)", 0, 40, 0,
                      help="0 = triangle parfait (recuperation exacte attendue)")
    seed = st.number_input("Graine aleatoire", 0, 9999, 1)

# --- Construction du triangle a verite connue ---
annees = list(range(2025 - n_annees, 2025))
ultimes = ultimes_croissance(annees, ultime_base * MDT, croissance)
pattern = np.array([decay ** k for k in range(n_annees)])
pattern = (pattern / pattern.sum()).tolist()

tri = generer_triangle_paiements(ultimes, pattern, cv_bruit=bruit / 100, seed=int(seed))
res = chain_ladder_full(tri)

# --- Resultats ---
vrais = [ultimes[a] for a in annees]
estimes = [float(res["resultats"].loc[a, "charge_ultime"]) for a in annees]
total_vrai = sum(vrais)
total_est = res["total_ultime"]
err = 100 * abs(total_est - total_vrai) / total_vrai

c1, c2, c3 = st.columns(3)
c1.metric("Ultime VRAI (connu)", f"{total_vrai/MDT:,.1f} M DT")
c2.metric("Ultime ESTIME (CL)", f"{total_est/MDT:,.1f} M DT")
c3.metric("Erreur de recuperation", f"{err:.2f} %",
          delta="exact" if err < 1e-6 else None,
          delta_color="normal")

if bruit == 0 and err < 1e-6:
    st.success(
        "✅ Sans bruit, le Chain-Ladder retrouve l'ultime **exactement** "
        "— la methode est correcte par construction."
    )
elif err < 5:
    st.info(f"Avec {bruit}% de bruit, l'estimation reste proche de la verite "
            f"(erreur {err:.2f} %).")
else:
    st.warning(f"Avec {bruit}% de bruit, l'ecart monte a {err:.2f} % "
               "— l'incertitude d'estimation devient visible.")

st.plotly_chart(fig_simulation_recuperation(annees, vrais, estimes),
                use_container_width=True)

# --- Bootstrap : la verite tombe-t-elle dans l'intervalle ? ---
if bruit > 0:
    st.subheader("Incertitude : la verite est-elle dans l'intervalle bootstrap ?")
    b = bootstrap_odp(tri, n_sim=1000, seed=int(seed))
    reserve_vraie = total_vrai - res["total_paye"]
    q = b["quantiles"]
    dans = reserve_vraie <= q["99.5%"]
    cc1, cc2, cc3 = st.columns(3)
    cc1.metric("Reserve vraie", f"{reserve_vraie/MDT:,.1f} M DT")
    cc2.metric("Reserve mediane (bootstrap)", f"{q['50%']/MDT:,.1f} M DT")
    cc3.metric("Quantile 99,5 %", f"{q['99.5%']/MDT:,.1f} M DT")
    st.caption(
        ("La reserve vraie est **sous** le quantile 99,5 % : l'intervalle couvre "
         "bien la verite." if dans else
         "La reserve vraie depasse le quantile 99,5 % (cas rare / bruit eleve).")
    )

st.divider()
st.caption(
    "Ce simulateur reprend le moteur des tests automatises (16 tests pytest) : "
    "memes fonctions de generation a verite connue."
)
