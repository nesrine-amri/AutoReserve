"""
Methode Cout Moyen (CM) - methodologie de l'encadrant.

Tableau final par annee de survenance :
- Reglement, SAP, Charge (dossier/dossier)
- PIC 1 (max charge pendant dev), PIC 2 (charge stabilisee)
- Nb sinistres, Cout Moyen, CM ajuste
- Nb tardifs estimes, Charge tardifs
- Ultime CM = charge actuelle + charge tardifs
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def build_cm_table(
    df_sinistres: pd.DataFrame,
    nature: str,
    annee_observation: int | None = None,
) -> pd.DataFrame:
    """Construit le tableau CM de base (colonnes Reglement/SAP/Charge/PICs/CM)."""
    df = df_sinistres[df_sinistres["NATURE_SINISTRE"] == nature].copy()

    if annee_observation is None:
        annee_observation = int(df["ANNEE_DEVELOPPEMENT"].max())

    annees_surv = sorted(df["ANNEE_SURVENANCE"].dropna().unique().tolist())

    rows = []
    for annee in annees_surv:
        df_annee = df[df["ANNEE_SURVENANCE"] == annee]

        by_dev = df_annee.groupby("INDICE_DEV").agg(
            paye=("SINISTRE_PAYE", "sum"),
            sap=("SAP", "sum"),
        ).sort_index()

        by_dev["paye_cumule"] = by_dev["paye"].cumsum()
        by_dev["charge_par_dev"] = by_dev["paye_cumule"] + by_dev["sap"]

        dev_max_annee = annee_observation - annee
        by_dev_visible = by_dev[by_dev.index <= dev_max_annee]

        if len(by_dev_visible) == 0:
            continue

        sap_courant = by_dev_visible["sap"].iloc[-1]
        charge_actuelle = by_dev_visible["paye_cumule"].iloc[-1] + sap_courant
        pic1_charge = by_dev_visible["charge_par_dev"].max()
        pic2_charge = charge_actuelle
        nb_sinistres = df_annee["NUM_SINISTRE"].nunique()

        rows.append({
            "annee_survenance": int(annee),
            "reglement": float(by_dev_visible["paye_cumule"].iloc[-1]),
            "sap_courant": float(sap_courant),
            "charge_actuelle": float(charge_actuelle),
            "pic1_charge": float(pic1_charge),
            "pic2_charge": float(pic2_charge),
            "nb_sinistres": int(nb_sinistres),
            "dev_atteint": int(dev_max_annee),
        })

    df_cm = pd.DataFrame(rows).set_index("annee_survenance")
    df_cm["cout_moyen"] = df_cm["charge_actuelle"] / df_cm["nb_sinistres"]
    df_cm["cout_moyen_pic1"] = df_cm["pic1_charge"] / df_cm["nb_sinistres"]

    return df_cm


def ajuster_cm_et_tardifs(
    df_cm: pd.DataFrame,
    df_sinistres: pd.DataFrame,
    nature: str,
    annees_reference_cm: list[int] | None = None,
    ratio_tardifs: float | None = None,
    annee_observation: int | None = None,
) -> pd.DataFrame:
    """Ajoute CM ajuste, nb tardifs estimes, charge tardifs, ultime CM."""
    df_cm = df_cm.copy()

    if annee_observation is None:
        annee_observation = int(df_sinistres["ANNEE_DEVELOPPEMENT"].max())

    if annees_reference_cm is None:
        annees_dispo = sorted(df_cm.index.tolist())
        derniere = annees_dispo[-1]
        annees_reference_cm = [a for a in annees_dispo
                              if derniere - 3 <= a < derniere][-3:]

    logger.info(f"Annees reference CM ajuste : {annees_reference_cm}")

    cm_ref_values = df_cm.loc[annees_reference_cm, "cout_moyen"].values
    cm_ajuste_derniere_annee = float(np.mean(cm_ref_values))

    df_nature = df_sinistres[df_sinistres["NATURE_SINISTRE"] == nature]

    if ratio_tardifs is None:
        ratios = []
        for annee in df_cm.index:
            dev_max = annee_observation - annee
            if dev_max < 3:
                continue

            df_a = df_nature[df_nature["ANNEE_SURVENANCE"] == annee]
            nb_dev0 = df_a[df_a["INDICE_DEV"] == 0]["NUM_SINISTRE"].nunique()
            nb_final = df_a["NUM_SINISTRE"].nunique()

            if nb_dev0 > 0:
                ratios.append((nb_final - nb_dev0) / nb_dev0)

        if ratios:
            ratio_tardifs = float(np.mean(ratios))
            logger.info(f"Ratio tardifs empirique = {100*ratio_tardifs:.2f}%")
        else:
            ratio_tardifs = 0.0

    df_cm["cout_moyen_ajuste"] = np.nan
    df_cm["nb_tardifs_estimes"] = 0
    df_cm["charge_tardifs"] = 0.0
    df_cm["ultime_cm"] = df_cm["charge_actuelle"]

    for annee in df_cm.index:
        dev_atteint = df_cm.loc[annee, "dev_atteint"]
        n_dev_restants = max(0, len(df_cm) - dev_atteint - 1)

        if n_dev_restants > 0 and dev_atteint < 3:
            df_cm.loc[annee, "cout_moyen_ajuste"] = cm_ajuste_derniere_annee

            nb_actuel = df_cm.loc[annee, "nb_sinistres"]

            if dev_atteint == 0:
                facteur = ratio_tardifs
            elif dev_atteint == 1:
                facteur = ratio_tardifs * 0.3
            elif dev_atteint == 2:
                facteur = ratio_tardifs * 0.1
            else:
                facteur = 0

            nb_tardifs = int(nb_actuel * facteur)
            df_cm.loc[annee, "nb_tardifs_estimes"] = nb_tardifs

            charge_tardifs = nb_tardifs * cm_ajuste_derniere_annee
            df_cm.loc[annee, "charge_tardifs"] = charge_tardifs
            df_cm.loc[annee, "ultime_cm"] = df_cm.loc[annee, "charge_actuelle"] + charge_tardifs
        else:
            df_cm.loc[annee, "cout_moyen_ajuste"] = df_cm.loc[annee, "cout_moyen"]

    return df_cm


def methode_cm_encadrant(
    df_sinistres: pd.DataFrame,
    nature: str,
    annee_observation: int | None = None,
    annees_reference_cm: list[int] | None = None,
    ratio_tardifs: float | None = None,
) -> dict:
    """Pipeline complet methode CM encadrant."""
    logger.info(f"Methode CM (encadrant) pour nature = {nature}")

    df_cm = build_cm_table(df_sinistres, nature, annee_observation)
    df_cm = ajuster_cm_et_tardifs(
        df_cm, df_sinistres, nature,
        annees_reference_cm=annees_reference_cm,
        ratio_tardifs=ratio_tardifs,
        annee_observation=annee_observation,
    )

    return {
        "tableau": df_cm,
        "total_reglement": float(df_cm["reglement"].sum()),
        "total_sap": float(df_cm["sap_courant"].sum()),
        "total_charge_actuelle": float(df_cm["charge_actuelle"].sum()),
        "total_charge_tardifs": float(df_cm["charge_tardifs"].sum()),
        "total_ultime_cm": float(df_cm["ultime_cm"].sum()),
    }