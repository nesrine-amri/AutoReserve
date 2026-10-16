"""Import des donnees : mise a jour des sources + analyse ad hoc d'un triangle."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

import app_data
from autoreserve.config import (
    RAW_DIR, PROCESSED_DIR, BASES_SOURCES, EXCLURE_CONTRE_PASSATIONS,
)
from autoreserve.sinistres.loader import FICHIER_SINISTRES
from autoreserve.sinistres.chain_ladder import chain_ladder_full
from autoreserve.sinistres.bootstrap import bootstrap_odp
from autoreserve.reporting.charts import fig_triangle_developpement

MDT = 1_000_000

st.title("Import des donnees")
st.caption(
    "Mettre a jour les fichiers sources et relancer tout le pipeline, ou "
    "analyser un triangle externe sans toucher aux donnees de production."
)

tab_src, tab_adhoc = st.tabs(
    ["Sources & pipeline", "Analyse ad hoc d'un triangle"]
)

# ------------------------------------------------------------------
# Mode 1 : mise a jour des sources + relance du pipeline
# ------------------------------------------------------------------
with tab_src:
    st.markdown(
        "Depose les fichiers Excel bruts. Ceux que tu laisses vides restent "
        "inchanges. Au lancement : **unification -> PPNA -> methodes** sont "
        "recalcules et les caches vides."
    )

    # fichiers CA (un par fichier source distinct)
    fichiers_ca = sorted({m["fichier"] for m in BASES_SOURCES.values()})
    uploads: dict[str, "st.runtime.uploaded_file_manager.UploadedFile"] = {}

    st.markdown("**Chiffre d'affaires (primes)**")
    for fich in fichiers_ca:
        uploads[fich] = st.file_uploader(fich, type=["xlsx"], key=f"up_{fich}")

    st.markdown("**Base sinistres**")
    uploads[FICHIER_SINISTRES] = st.file_uploader(
        FICHIER_SINISTRES, type=["xlsx"], key="up_sinistres"
    )

    n_fournis = sum(1 for f in uploads.values() if f is not None)
    confirmer = st.checkbox(
        "Je confirme le remplacement des fichiers sources fournis",
        value=False,
    )

    if st.button("Enregistrer et relancer le pipeline", type="primary",
                 disabled=(n_fournis == 0 or not confirmer)):
        try:
            # 1. ecrire les fichiers fournis dans data/raw/
            ecrits = []
            for nom, up in uploads.items():
                if up is not None:
                    (RAW_DIR / nom).write_bytes(up.getbuffer())
                    ecrits.append(nom)
            st.write(f"Fichiers remplaces : {', '.join(ecrits)}")

            # 2. relancer le pipeline primes/PPNA
            from autoreserve.ingestion.unifier import build_unified_base
            from autoreserve.actuarial import compute_ppna_portefeuille
            with st.spinner("Unification + PPNA (lecture des sources, ~1-2 min)..."):
                dfu = build_unified_base(save_parquet=True)
                dpp = compute_ppna_portefeuille(
                    dfu, date_cloture=date(2024, 12, 31),
                    exclure_contre_passations=EXCLURE_CONTRE_PASSATIONS,
                )
                dpp.to_parquet(PROCESSED_DIR / "base_avec_ppna_v2.parquet", index=False)

            # 3. vider les caches pour recharger les nouvelles donnees
            st.cache_data.clear()
            st.success("Pipeline relance. Les pages refletent desormais les nouvelles sources.")

            val = app_data.validation_ppna()
            if val:
                c1, c2 = st.columns(2)
                c1.metric("Primes emises 2024", f"{val['primes_calc']/MDT:,.1f} M DT")
                c2.metric("PPNA 2024", f"{val['ppna_calc']/MDT:,.1f} M DT")
        except Exception as e:  # pragma: no cover
            st.error(f"Echec du pipeline : {e}")

    st.caption(
        "Les fichiers sources sont confidentiels et ne sont pas versionnes. "
        "Le remplacement est definitif sur le disque."
    )

# ------------------------------------------------------------------
# Mode 2 : analyse ad hoc d'un triangle externe
# ------------------------------------------------------------------
with tab_adhoc:
    st.markdown(
        "Depose un **triangle de paiements cumules** (Excel) : 1ere colonne = "
        "annee de survenance, colonnes suivantes = indices de developpement "
        "(0, 1, 2, ...), cases futures vides. On lance le Chain-Ladder dessus."
    )

    # modele telechargeable pour connaitre le format attendu
    import io
    modele = pd.DataFrame(
        {0: [400, 400, 400], 1: [700, 700, None], 2: [900, None, None]},
        index=[2022, 2023, 2024],
    )
    modele.index.name = "ANNEE_SURVENANCE"
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        modele.to_excel(w, sheet_name="triangle")
    st.download_button(
        "⬇️ Telecharger un modele de triangle (.xlsx)",
        data=buf.getvalue(), file_name="modele_triangle.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    up = st.file_uploader("Triangle (.xlsx)", type=["xlsx"], key="up_triangle")

    if up is not None:
        try:
            tri = pd.read_excel(up, index_col=0)
            tri = tri.apply(pd.to_numeric, errors="coerce")
            tri = tri.dropna(how="all").dropna(axis=1, how="all")
            tri.columns = range(len(tri.columns))  # dev 0..K-1
            valide = (not tri.empty) and tri.shape[1] >= 2
        except Exception as e:
            tri, valide = None, False
            st.error(f"Lecture impossible : {e}")
            st.caption("Verifie le format : annees en 1ere colonne, dev en colonnes, "
                       "montants numeriques, cases futures vides.")

        if valide:
            st.dataframe(tri.round(2), use_container_width=True)
            res = chain_ladder_full(tri)
            c1, c2, c3 = st.columns(3)
            c1.metric("Paye actuel", f"{res['total_paye']/MDT:,.2f} M")
            c2.metric("Ultime (CL)", f"{res['total_ultime']/MDT:,.2f} M")
            c3.metric("Reserves", f"{res['total_reserves']/MDT:,.2f} M")

            st.plotly_chart(fig_triangle_developpement(tri, "triangle importe"),
                            use_container_width=True)

            if st.checkbox("Ajouter l'incertitude (bootstrap ODP)"):
                b = bootstrap_odp(tri, n_sim=1000, seed=42)
                st.metric("Coefficient de variation", f"{b['cv_pct']:.1f} %")
                st.caption(
                    f"Provision a 99,5 % : {b['quantiles']['99.5%']/MDT:,.2f} M DT"
                )
        elif tri is not None:
            st.warning("Triangle invalide : il faut au moins 2 colonnes de developpement.")
