"""Synthese Best Estimate — comparatif des methodes vs SAP comptable reel."""

from __future__ import annotations

from datetime import date

import streamlit as st

import app_data
from autoreserve.reporting.charts import fig_reserves_par_methode, fig_boni_mali
from autoreserve.reporting.export_excel import exporter_best_estimate

MDT = 1_000_000


@st.cache_data(show_spinner=False)
def _export_xlsx(quantile: float) -> bytes:
    return exporter_best_estimate(app_data.consolidation(quantile),
                                  date_arrete=date(2024, 12, 31))


st.title("Synthese Best Estimate")
st.caption("Comparatif des 4 methodes par segment, confronte au SAP comptable reel.")

try:
    conso = app_data.consolidation()
except Exception as e:
    st.error(f"Donnees indisponibles : {e}")
    st.stop()

synthese = conso["synthese"]
comparatifs = conso["comparatifs_par_segment"]
total = conso["total"]

col_dl, _ = st.columns([1, 3])
with col_dl:
    st.download_button(
        "⬇️ Exporter la synthese (Excel)",
        data=_export_xlsx(0.99),
        file_name="autoreserve_synthese_best_estimate.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

c1, c2, c3 = st.columns(3)
c1.metric("Best Estimate sinistres", f"{total['best_estimate_sinistres']/MDT:,.1f} M DT")
c2.metric("SAP comptable reel", f"{total['sap_comptable']/MDT:,.1f} M DT")
c3.metric("IBNR net estime", f"{total['ibnr_estime']/MDT:+,.1f} M DT")

st.divider()

cols = st.columns(len(comparatifs))
for col, (seg, tab) in zip(cols, comparatifs.items()):
    with col:
        st.plotly_chart(fig_reserves_par_methode(tab, seg), use_container_width=True)

st.plotly_chart(fig_boni_mali(synthese), use_container_width=True)

st.divider()

st.subheader("Detail par segment (methode retenue)")
affichage = synthese.copy()
for c in ["paye", "ultime", "reserves_estimees", "sap_comptable", "ibnr_estime", "boni_mali"]:
    affichage[c] = (affichage[c] / MDT).round(2)
affichage = affichage.rename(columns={
    "methode_retenue": "Methode", "paye": "Paye", "ultime": "Ultime",
    "reserves_estimees": "Reserves est.", "sap_comptable": "SAP reel",
    "ibnr_estime": "IBNR est.", "boni_mali": "Boni/Mali",
})
st.dataframe(affichage, use_container_width=True)
st.caption("Montants en M DT. Boni (+) = sur-provision comptable, Mali (-) = sous-provision.")

with st.expander("Voir toutes les methodes (par segment)"):
    for seg, tab in comparatifs.items():
        st.markdown(f"**{seg}**")
        t = (tab[["paye", "ultime", "reserves", "sap_comptable", "ibnr_estime", "boni_mali"]]
             / MDT).round(2)
        st.dataframe(t, use_container_width=True)
