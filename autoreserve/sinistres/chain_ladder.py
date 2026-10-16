"""
Methode Chain-Ladder deterministe (from scratch).

Fonctions principales :
- compute_link_ratios : calcul des coefficients de developpement f_k
- project_triangle : projection Chain-Ladder complete
- compute_ultimate_and_reserves : charge ultime + reserves (IBNR + IBNER)
- chain_ladder_full : pipeline complet
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_link_ratios(
    triangle: pd.DataFrame,
    method: Literal["volume", "simple_average"] = "volume",
) -> pd.Series:
    """
    Calcule les coefficients de developpement (link ratios) f_k.

    - "volume" : f_k = sum(C[i,k+1]) / sum(C[i,k])  (Chain-Ladder standard)
    - "simple_average" : moyenne des ratios individuels
    """
    if triangle.empty:
        return pd.Series(dtype=float)

    devs = list(triangle.columns)
    link_ratios = {}

    for k in range(len(devs) - 1):
        dev_k = devs[k]
        dev_k1 = devs[k + 1]

        col_k = triangle[dev_k]
        col_k1 = triangle[dev_k1]

        mask = col_k.notna() & col_k1.notna()

        if mask.sum() == 0:
            link_ratios[dev_k] = np.nan
            continue

        if method == "volume":
            num = col_k1[mask].sum()
            denom = col_k[mask].sum()
            link_ratios[dev_k] = num / denom if denom != 0 else np.nan
        elif method == "simple_average":
            ratios = col_k1[mask] / col_k[mask]
            ratios = ratios.replace([np.inf, -np.inf], np.nan).dropna()
            link_ratios[dev_k] = ratios.mean() if len(ratios) > 0 else np.nan
        else:
            raise ValueError(f"Methode inconnue : {method}")

    return pd.Series(link_ratios, name="link_ratio")


def compute_link_ratios_individuels(triangle: pd.DataFrame) -> pd.DataFrame:
    """Ratios individuels par annee (diagnostic)."""
    if triangle.empty:
        return pd.DataFrame()

    devs = list(triangle.columns)
    ratios_df = pd.DataFrame(index=triangle.index, columns=devs[:-1], dtype=float)

    for k in range(len(devs) - 1):
        dev_k = devs[k]
        dev_k1 = devs[k + 1]
        col_k = triangle[dev_k]
        col_k1 = triangle[dev_k1]

        mask = col_k.notna() & col_k1.notna() & (col_k != 0)
        ratios_df.loc[mask, dev_k] = col_k1[mask] / col_k[mask]

    ratios_df.columns.name = "DEV_transition"
    return ratios_df


def project_triangle(
    triangle: pd.DataFrame,
    link_ratios: pd.Series,
) -> pd.DataFrame:
    """Projette les cases manquantes du triangle avec les link ratios."""
    if triangle.empty:
        return triangle.copy()

    projected = triangle.copy().astype(float)
    devs = list(projected.columns)

    for annee in projected.index:
        ligne = projected.loc[annee]
        connus = ligne.dropna()
        if len(connus) == 0:
            continue

        dernier_dev_connu = connus.index[-1]
        idx_dernier = devs.index(dernier_dev_connu)

        valeur_courante = ligne[dernier_dev_connu]
        for k in range(idx_dernier, len(devs) - 1):
            dev_courant = devs[k]
            dev_suivant = devs[k + 1]

            f_k = link_ratios.get(dev_courant, np.nan)
            if pd.isna(f_k):
                projected.loc[annee, dev_suivant] = valeur_courante
            else:
                valeur_courante = valeur_courante * f_k
                projected.loc[annee, dev_suivant] = valeur_courante

    return projected


def compute_ultimate_and_reserves(
    triangle_observe: pd.DataFrame,
    triangle_projete: pd.DataFrame,
) -> pd.DataFrame:
    """Calcule ultime, reserves, taux de developpement par annee."""
    if triangle_projete.empty:
        return pd.DataFrame()

    devs = list(triangle_projete.columns)
    dernier_dev = devs[-1]

    result = pd.DataFrame(index=triangle_projete.index)

    paye_actuel = []
    for annee in triangle_observe.index:
        connus = triangle_observe.loc[annee].dropna()
        paye_actuel.append(connus.iloc[-1] if len(connus) > 0 else 0)
    result["paiement_cumule_actuel"] = paye_actuel

    result["charge_ultime"] = triangle_projete[dernier_dev].values
    result["reserves"] = result["charge_ultime"] - result["paiement_cumule_actuel"]
    result["taux_developpement_pct"] = (
        100 * result["paiement_cumule_actuel"] / result["charge_ultime"]
    ).round(2)

    result.index.name = "ANNEE_SURVENANCE"
    return result


def chain_ladder_full(
    triangle: pd.DataFrame,
    method: Literal["volume", "simple_average"] = "volume",
) -> dict:
    """Pipeline complet Chain-Ladder deterministe."""
    if triangle.empty:
        return {"error": "Triangle vide"}

    logger.info(f"Chain-Ladder (methode = {method}) sur triangle {triangle.shape}")

    link_ratios = compute_link_ratios(triangle, method=method)
    ratios_indiv = compute_link_ratios_individuels(triangle)
    projete = project_triangle(triangle, link_ratios)
    resultats = compute_ultimate_and_reserves(triangle, projete)

    total_paye = resultats["paiement_cumule_actuel"].sum()
    total_ultime = resultats["charge_ultime"].sum()
    total_reserves = resultats["reserves"].sum()

    logger.info(f"  Paye actuel   : {total_paye:>15,.0f} DT")
    logger.info(f"  Charge ultime : {total_ultime:>15,.0f} DT")
    logger.info(f"  Reserves      : {total_reserves:>15,.0f} DT")

    return {
        "link_ratios": link_ratios,
        "link_ratios_individuels": ratios_indiv,
        "triangle_observe": triangle,
        "triangle_projete": projete,
        "resultats": resultats,
        "total_paye": total_paye,
        "total_ultime": total_ultime,
        "total_reserves": total_reserves,
        "method": method,
    }