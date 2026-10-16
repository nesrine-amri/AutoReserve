"""
Construction des triangles actuariels de sinistres.

3 triangles selon la methode de l'encadrant :

1. TRIANGLE OUVERTURE (en NOMBRE)
   Nombre de sinistres uniques ouverts par (annee_survenance x indice_dev)

2. TRIANGLE PAIEMENTS (en MONTANT cumule)
   Cumul des paiements par (annee_survenance x indice_dev)

3. TRIANGLE CHARGE (Paye cumule + SAP)
   Vue "dossier/dossier"
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


Nature = Literal["CORPOREL", "MATERIEL", "GLOBAL"]


def _filter_nature(df: pd.DataFrame, nature: Nature) -> pd.DataFrame:
    if nature == "GLOBAL":
        return df.copy()
    return df[df["NATURE_SINISTRE"] == nature].copy()


def build_triangle_ouverture(
    df: pd.DataFrame,
    nature: Nature = "GLOBAL",
    cumule: bool = True,
    annee_observation: int | None = None,
) -> pd.DataFrame:
    """
    Triangle du nombre de sinistres uniques par (survenance x dev).
    Un sinistre est compte a son indice_dev MINIMUM (= annee d'ouverture).
    """
    df_f = _filter_nature(df, nature)

    if len(df_f) == 0:
        logger.warning(f"Aucun sinistre pour nature={nature}")
        return pd.DataFrame()

    if annee_observation is None:
        annee_observation = int(df_f["ANNEE_DEVELOPPEMENT"].max())

    ouvertures = df_f.groupby("NUM_SINISTRE").agg(
        annee_surv=("ANNEE_SURVENANCE", "first"),
        indice_dev_ouverture=("INDICE_DEV", "min"),
    ).reset_index()

    counts = ouvertures.groupby(["annee_surv", "indice_dev_ouverture"]).size()
    triangle_incremental = counts.unstack(fill_value=0)

    annees = sorted(df_f["ANNEE_SURVENANCE"].dropna().unique().tolist())
    dev_max = int(df_f["INDICE_DEV"].max())
    all_devs = list(range(dev_max + 1))

    triangle_incremental = triangle_incremental.reindex(
        index=annees, columns=all_devs, fill_value=0
    )
    triangle_incremental.index.name = "ANNEE_SURVENANCE"
    triangle_incremental.columns.name = "INDICE_DEV"

    triangle_incremental = triangle_incremental.astype(float)
    for annee in annees:
        dev_max_connu = annee_observation - annee
        for dev in all_devs:
            if dev > dev_max_connu:
                triangle_incremental.loc[annee, dev] = np.nan

    if cumule:
        triangle = triangle_incremental.cumsum(axis=1, skipna=False)
    else:
        triangle = triangle_incremental

    return triangle


def build_triangle_paiements(
    df: pd.DataFrame,
    nature: Nature = "GLOBAL",
    cumule: bool = True,
    annee_observation: int | None = None,
) -> pd.DataFrame:
    """Triangle des paiements par (survenance x dev)."""
    df_f = _filter_nature(df, nature)

    if len(df_f) == 0:
        logger.warning(f"Aucun sinistre pour nature={nature}")
        return pd.DataFrame()

    if annee_observation is None:
        annee_observation = int(df_f["ANNEE_DEVELOPPEMENT"].max())

    paiements_incremental = df_f.groupby(
        ["ANNEE_SURVENANCE", "INDICE_DEV"]
    )["SINISTRE_PAYE"].sum().unstack(fill_value=0)

    annees = sorted(df_f["ANNEE_SURVENANCE"].dropna().unique().tolist())
    dev_max = int(df_f["INDICE_DEV"].max())
    all_devs = list(range(dev_max + 1))

    paiements_incremental = paiements_incremental.reindex(
        index=annees, columns=all_devs, fill_value=0.0
    ).astype(float)
    paiements_incremental.index.name = "ANNEE_SURVENANCE"
    paiements_incremental.columns.name = "INDICE_DEV"

    for annee in annees:
        dev_max_connu = annee_observation - annee
        for dev in all_devs:
            if dev > dev_max_connu:
                paiements_incremental.loc[annee, dev] = np.nan

    if cumule:
        triangle = paiements_incremental.cumsum(axis=1, skipna=False)
    else:
        triangle = paiements_incremental

    return triangle


def build_triangle_charge(
    df: pd.DataFrame,
    nature: Nature = "GLOBAL",
    annee_observation: int | None = None,
) -> pd.DataFrame:
    """Triangle de la charge = Paiements cumules + SAP courant."""
    df_f = _filter_nature(df, nature)

    if len(df_f) == 0:
        return pd.DataFrame()

    if annee_observation is None:
        annee_observation = int(df_f["ANNEE_DEVELOPPEMENT"].max())

    paiements_cumul = build_triangle_paiements(
        df_f, nature="GLOBAL", cumule=True, annee_observation=annee_observation
    )

    sap_incremental = df_f.groupby(
        ["ANNEE_SURVENANCE", "INDICE_DEV"]
    )["SAP"].sum().unstack(fill_value=0)

    annees = sorted(df_f["ANNEE_SURVENANCE"].dropna().unique().tolist())
    dev_max = int(df_f["INDICE_DEV"].max())
    all_devs = list(range(dev_max + 1))

    sap_incremental = sap_incremental.reindex(
        index=annees, columns=all_devs, fill_value=0.0
    ).astype(float)

    for annee in annees:
        dev_max_connu = annee_observation - annee
        for dev in all_devs:
            if dev > dev_max_connu:
                sap_incremental.loc[annee, dev] = np.nan

    charge = paiements_cumul + sap_incremental
    charge.index.name = "ANNEE_SURVENANCE"
    charge.columns.name = "INDICE_DEV"

    return charge


def build_all_triangles(
    df: pd.DataFrame,
    nature: Nature = "GLOBAL",
) -> dict[str, pd.DataFrame]:
    """Construit les 3 triangles pour une nature donnee."""
    logger.info(f"Construction des triangles pour nature={nature}")
    return {
        "ouverture_cumul": build_triangle_ouverture(df, nature, cumule=True),
        "ouverture_increment": build_triangle_ouverture(df, nature, cumule=False),
        "paiements_cumul": build_triangle_paiements(df, nature, cumule=True),
        "paiements_increment": build_triangle_paiements(df, nature, cumule=False),
        "charge": build_triangle_charge(df, nature),
    }


def build_triangles_by_nature(df: pd.DataFrame) -> dict[str, dict[str, pd.DataFrame]]:
    """Construit tous les triangles pour CORPOREL, MATERIEL et GLOBAL."""
    result = {}
    for nature in ["CORPOREL", "MATERIEL", "GLOBAL"]:
        result[nature] = build_all_triangles(df, nature=nature)
    return result


def format_triangle_display(
    triangle: pd.DataFrame,
    decimals: int = 0,
    unit: str = "",
) -> str:
    """Formate un triangle pour affichage console lisible."""
    if triangle.empty:
        return "(triangle vide)"

    df_display = triangle.copy()

    if decimals == 0:
        def fmt(v):
            if pd.isna(v):
                return "     -    "
            return f"{int(round(v)):>10,}"
    else:
        def fmt(v):
            if pd.isna(v):
                return "     -    "
            return f"{v:>10,.{decimals}f}"

    df_display = df_display.map(fmt)

    header = f"[{unit}]" if unit else ""
    return f"{header}\n{df_display.to_string()}"