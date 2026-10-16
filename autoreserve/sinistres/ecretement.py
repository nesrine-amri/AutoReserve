"""
Ecretement des sinistres graves (large-loss) par CAPPING sur les paiements.

Motivation
----------
La charge corporelle (et la queue materielle) est fortement asymetrique :
quelques sinistres "graves" concentrent une part importante de la charge.
En Chain-Ladder a coefficients "volume", un grave tombant dans une case
gonfle le link ratio f_k, applique ensuite a TOUTES les annees de
survenance -> surestimation et instabilite de l'ultime.

Methode retenue : capping sur les PAIEMENTS (coherent avec le triangle de
paiements, et insensible au double-comptage du SAP, qui est un STOCK).

1. Pour chaque sinistre, on calcule le cumul de paiements "vie entiere"
   (somme des paiements incrementaux -> correct, le paye est un flux).
2. On plafonne le cumul de chaque sinistre au seuil S (capping).
   -> triangle PLAFONNE, projete par Chain-Ladder sans etre pollue par les pics.
3. L'EXCEDENT paye au-dela de S (= part grave deja decaissee, observee) est
   re-ajoute a l'ultime sans developpement supplementaire.
4. Ultime ecrete = Ultime CL(plafonne) + Excedent paye des graves.

NB : on raisonne en PAIEMENTS (pas paye+SAP). Le SAP etant un stock, il ne
doit jamais etre somme sur les annees de developpement.

Le module renvoie des objets prets a afficher (DataFrames + dict).
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
import pandas as pd

from autoreserve.sinistres.triangles import build_triangle_paiements, Nature
from autoreserve.sinistres.chain_ladder import chain_ladder_full

logger = logging.getLogger(__name__)


def paiement_total_par_sinistre(df: pd.DataFrame) -> pd.Series:
    """
    Cumul de paiements "vie entiere" par sinistre.
    Le paiement est INCREMENTAL (flux) -> la somme sur les annees est correcte.
    """
    paye = pd.to_numeric(df["SINISTRE_PAYE"], errors="coerce").fillna(0)
    return paye.groupby(df["NUM_SINISTRE"]).sum()


def determiner_seuil(
    df: pd.DataFrame,
    seuil: float | None = None,
    quantile: float = 0.99,
) -> float:
    """Seuil de gravite : explicite, sinon quantile des paiements par sinistre."""
    if seuil is not None:
        return float(seuil)
    paiements = paiement_total_par_sinistre(df)
    if paiements.empty:
        return float("inf")
    return float(paiements.quantile(quantile))


def _triangle_plafonne_et_excedent(
    df: pd.DataFrame,
    seuil: float,
) -> tuple[pd.DataFrame, float, dict]:
    """
    Construit le triangle de paiements PLAFONNE (cumul de chaque sinistre
    capé a `seuil`) et renvoie l'excedent paye total des graves.

    Returns
    -------
    (df_plafonne, excedent_paye, info)
        df_plafonne : df au grain (NUM_SINISTRE, INDICE_DEV) avec paiements capés,
                      pret pour build_triangle_paiements.
        excedent_paye : somme des (cumul - seuil) au-dela du seuil (observe).
        info : stats graves.
    """
    paye = pd.to_numeric(df["SINISTRE_PAYE"], errors="coerce").fillna(0)
    surv = pd.to_numeric(df["ANNEE_SURVENANCE"], errors="coerce")
    base = pd.DataFrame({
        "NUM_SINISTRE": df["NUM_SINISTRE"].values,
        "ANNEE_SURVENANCE": surv.values,
        "INDICE_DEV": pd.to_numeric(df["INDICE_DEV"], errors="coerce").values,
        "ANNEE_DEVELOPPEMENT": pd.to_numeric(df["ANNEE_DEVELOPPEMENT"], errors="coerce").values,
        "paye": paye.values,
    }).dropna(subset=["INDICE_DEV", "ANNEE_SURVENANCE"])

    # paiement incremental par (sinistre, indice_dev), somme sur les garanties
    grain = base.groupby(
        ["NUM_SINISTRE", "ANNEE_SURVENANCE", "INDICE_DEV", "ANNEE_DEVELOPPEMENT"],
        as_index=False,
    )["paye"].sum().sort_values(["NUM_SINISTRE", "INDICE_DEV"])

    # cumul par sinistre
    grain["cumul"] = grain.groupby("NUM_SINISTRE")["paye"].cumsum()
    # cumul plafonne au seuil, puis re-derivation de l'incremental plafonne
    grain["cumul_cap"] = grain["cumul"].clip(upper=seuil)
    grain["paye_cap"] = grain.groupby("NUM_SINISTRE")["cumul_cap"].diff().fillna(
        grain["cumul_cap"]
    )

    # excedent paye = part au-dela du seuil (observe, deja decaisse)
    total_par_sin = grain.groupby("NUM_SINISTRE")["paye"].sum()
    graves = total_par_sin[total_par_sin >= seuil]
    excedent_paye = float((graves - seuil).clip(lower=0).sum())

    # df plafonne pour le triangle (on renomme paye_cap -> SINISTRE_PAYE)
    df_plaf = grain.rename(columns={"paye_cap": "SINISTRE_PAYE"})[
        ["NUM_SINISTRE", "ANNEE_SURVENANCE", "INDICE_DEV", "ANNEE_DEVELOPPEMENT", "SINISTRE_PAYE"]
    ].copy()
    df_plaf["NATURE_SINISTRE"] = "GLOBAL"  # deja filtre en amont

    info = {
        "n_sinistres_total": int(total_par_sin.shape[0]),
        "n_graves": int(graves.shape[0]),
        "paiement_graves": float(graves.sum()),
        "paiement_total": float(total_par_sin.sum()),
        "excedent_paye": excedent_paye,
        "part_graves_pct": round(100 * graves.sum() / total_par_sin.sum(), 2)
        if total_par_sin.sum() else 0.0,
    }
    return df_plaf, excedent_paye, info


def chain_ladder_ecrete(
    df: pd.DataFrame,
    nature: Nature = "GLOBAL",
    seuil: float | None = None,
    quantile: float = 0.99,
    method: Literal["volume", "simple_average"] = "volume",
) -> dict:
    """
    Chain-Ladder ecrete : CL sur triangle plafonne + excedent paye des graves.
    Renvoie un dict comparant BRUT vs ECRETE (prets a afficher).
    """
    if nature != "GLOBAL":
        df = df[df["NATURE_SINISTRE"] == nature].copy()

    seuil_val = determiner_seuil(df, seuil=seuil, quantile=quantile)

    # --- BRUT (reference) ---
    t_brut = build_triangle_paiements(df, nature="GLOBAL", cumule=True)
    cl_brut = chain_ladder_full(t_brut, method=method)

    # --- PLAFONNE ---
    df_plaf, excedent_paye, info = _triangle_plafonne_et_excedent(df, seuil_val)
    t_plaf = build_triangle_paiements(df_plaf, nature="GLOBAL", cumule=True)
    cl_plaf = chain_ladder_full(t_plaf, method=method)

    ultime_ecrete = cl_plaf["total_ultime"] + excedent_paye
    reserves_ecrete = ultime_ecrete - cl_brut["total_paye"]
    ecart_ultime = cl_brut["total_ultime"] - ultime_ecrete

    synthese = pd.DataFrame(
        {
            "BRUT": [cl_brut["total_paye"], cl_brut["total_ultime"], cl_brut["total_reserves"]],
            "ECRETE": [cl_brut["total_paye"], ultime_ecrete, reserves_ecrete],
        },
        index=["Paye actuel", "Ultime", "Reserves"],
    )
    synthese["Ecart"] = synthese["BRUT"] - synthese["ECRETE"]

    info["seuil"] = seuil_val
    logger.info(
        "CL ecrete [%s] : ultime brut=%.0f -> ecrete=%.0f (ecart=%.0f, %.1f%%)",
        nature, cl_brut["total_ultime"], ultime_ecrete, ecart_ultime,
        100 * ecart_ultime / cl_brut["total_ultime"] if cl_brut["total_ultime"] else 0,
    )

    return {
        "nature": nature,
        "seuil": seuil_val,
        "info_graves": info,
        "cl_brut": cl_brut,
        "cl_plafonne": cl_plaf,
        "excedent_paye": excedent_paye,
        "ultime_ecrete": ultime_ecrete,
        "reserves_ecrete": reserves_ecrete,
        "ecart_ultime_vs_brut": ecart_ultime,
        "synthese": synthese,
    }


def sensibilite_seuil(
    df: pd.DataFrame,
    nature: Nature = "GLOBAL",
    quantiles: list[float] | None = None,
    method: Literal["volume", "simple_average"] = "volume",
) -> pd.DataFrame:
    """Table de sensibilite : ultime ecrete selon plusieurs seuils (quantiles)."""
    if quantiles is None:
        quantiles = [0.95, 0.975, 0.99, 0.995, 0.999]

    df_n = df[df["NATURE_SINISTRE"] == nature].copy() if nature != "GLOBAL" else df

    rows = []
    for q in quantiles:
        res = chain_ladder_ecrete(df_n, nature="GLOBAL", quantile=q, method=method)
        rows.append({
            "quantile": q,
            "seuil": round(res["seuil"], 0),
            "n_graves": res["info_graves"]["n_graves"],
            "part_graves_pct": res["info_graves"]["part_graves_pct"],
            "ultime_brut": round(res["cl_brut"]["total_ultime"], 0),
            "ultime_ecrete": round(res["ultime_ecrete"], 0),
            "ecart_vs_brut": round(res["ecart_ultime_vs_brut"], 0),
            "ecart_pct": round(
                100 * res["ecart_ultime_vs_brut"] / res["cl_brut"]["total_ultime"], 2
            ) if res["cl_brut"]["total_ultime"] else 0.0,
        })
    return pd.DataFrame(rows).set_index("quantile")
