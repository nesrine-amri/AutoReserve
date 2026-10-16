"""
Consolidation PSAP / IBNR : synthese multi-methodes et Best Estimate.

Pour chaque segment (CORPOREL / MATERIEL), compare les ultimes et reserves
des differentes methodes :
    - Chain-Ladder brut
    - Chain-Ladder ecrete (capping des graves)
    - Bornhuetter-Ferguson
    - Methode CM (encadrant)

et les confronte au SAP COMPTABLE REEL (provisions dossier/dossier effectivement
constituees, = diagonale courante de la base). Cela donne :
    - IBNR estime      = reserves estimees - SAP comptable
    - boni (+) / mali (-) comptable = SAP comptable - reserves estimees

Le Best Estimate retient une methode par segment (configurable), et l'on peut
y ajouter la PPNA (provision de primes) pour les provisions techniques totales.

Toutes les sorties sont des DataFrames / dicts prets a afficher (plateforme).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from autoreserve.sinistres.triangles import build_triangle_paiements
from autoreserve.sinistres.chain_ladder import chain_ladder_full
from autoreserve.sinistres.bornhuetter_ferguson import bornhuetter_ferguson
from autoreserve.sinistres.ecretement import chain_ladder_ecrete
from autoreserve.sinistres.methode_cm import methode_cm_encadrant

logger = logging.getLogger(__name__)

SEGMENTS = ["CORPOREL", "MATERIEL"]


# ------------------------------------------------------------------
# Benchmark reel : SAP comptable courant
# ------------------------------------------------------------------
def sap_comptable_courant(
    df: pd.DataFrame,
    nature: str,
    annee_observation: int | None = None,
) -> float:
    """
    SAP comptable reel = somme du SAP sur la DERNIERE diagonale observee
    (provisions dossier/dossier effectivement constituees a la cloture).
    """
    d = df[df["NATURE_SINISTRE"] == nature]
    dev_cal = pd.to_numeric(d["ANNEE_DEVELOPPEMENT"], errors="coerce")
    if annee_observation is None:
        annee_observation = int(dev_cal.max())
    sap = pd.to_numeric(d["SAP"], errors="coerce").fillna(0)
    return float(sap[dev_cal == annee_observation].sum())


# ------------------------------------------------------------------
# Prime acquise (pour BF) : total portefeuille, completee pour l'historique
# ------------------------------------------------------------------
def premium_reel_par_annee(
    df_ppna: pd.DataFrame,
    col_prime: str = "PRIME_ACQUISE_NETTE",
    col_annee: str = "ANNEE_EXERCICE",
) -> pd.Series:
    """Prime acquise reellement observee par annee d'exercice."""
    pa = pd.to_numeric(df_ppna[col_prime], errors="coerce")
    s = pa.groupby(df_ppna[col_annee]).sum()
    s.index = pd.to_numeric(s.index, errors="coerce")
    return s[s.index.notna()].sort_index()


def annees_prime_fiables(
    pa_reelle: pd.Series,
    seuil_partiel: float = 0.90,
) -> list[int]:
    """
    Annees a prime REELLE et COMPLETE, pour calibrer le loss ratio.
    La derniere annee observee est ecartee si elle semble partielle
    (prime < seuil_partiel x prime de l'annee precedente).
    """
    annees = sorted(int(a) for a in pa_reelle.index)
    if len(annees) <= 1:
        return annees
    fiables = annees.copy()
    derniere, avant = annees[-1], annees[-2]
    if pa_reelle[derniere] < seuil_partiel * pa_reelle[avant]:
        fiables.remove(derniere)  # annee partielle
        logger.info("Annee %d ecartee du loss ratio (prime partielle)", derniere)
    return fiables


def preparer_prime_acquise_serie(
    df_ppna: pd.DataFrame,
    annees_cibles: list[int],
    annees_fiables: list[int] | None = None,
    col_prime: str = "PRIME_ACQUISE_NETTE",
    col_annee: str = "ANNEE_EXERCICE",
    override: dict[int, float] | None = None,
) -> pd.Series:
    """
    Prime acquise par annee de survenance pour l'a priori BF.

    Prime reelle quand elle existe ; les annees sans prime (historique) et
    l'annee partielle sont remplacees par la moyenne des annees FIABLES
    (remplissage a plat, et non par extrapolation lineaire qui, sur une
    histoire courte, inverse la tendance et fabrique des primes aberrantes).

    override : valeurs a imposer pour certaines annees (ex. prime acquise
        officielle de l'encadrant pour 2024). Appliquee en dernier.
    """
    pa = premium_reel_par_annee(df_ppna, col_prime, col_annee)
    if annees_fiables is None:
        annees_fiables = annees_prime_fiables(pa)

    prime_flat = float(pa.loc[annees_fiables].mean()) if annees_fiables else float(pa.mean())

    valeurs = {}
    for a in annees_cibles:
        if a in annees_fiables:
            valeurs[a] = float(pa[a])
        else:
            # annee historique manquante OU annee partielle -> valeur a plat
            valeurs[a] = prime_flat

    if override:
        for a, v in override.items():
            if a in valeurs:
                valeurs[a] = float(v)

    return pd.Series(valeurs).reindex(annees_cibles)


def loss_ratio_segment(
    charge_ultime_cl: pd.Series,
    pa_reelle: pd.Series,
    annees_fiables: list[int],
) -> float:
    """
    Loss ratio du segment = Sum(ultime CL) / Sum(prime REELLE) sur les annees
    a prime fiable (et non sur les annees 'matures' a prime extrapolee).
    """
    ans = [a for a in annees_fiables if a in charge_ultime_cl.index and a in pa_reelle.index]
    if not ans:
        return float("nan")
    num = float(charge_ultime_cl.loc[ans].sum())
    den = float(pa_reelle.loc[ans].sum())
    return num / den if den else float("nan")


# ------------------------------------------------------------------
# Comparatif multi-methodes pour un segment
# ------------------------------------------------------------------
def comparatif_segment(
    df: pd.DataFrame,
    nature: str,
    prime_acquise_serie: pd.Series | None = None,
    pa_reelle: pd.Series | None = None,
    annees_fiables: list[int] | None = None,
    quantile_ecretement: float = 0.99,
    annee_observation: int | None = None,
) -> pd.DataFrame:
    """
    Table comparative des methodes pour un segment, avec confrontation au reel.

    Colonnes : paye, ultime, reserves, sap_comptable, ibnr_estime, boni_mali.
    BF n'est calcule que si prime_acquise_serie + pa_reelle + annees_fiables
    sont fournis (loss ratio calibre sur les annees a prime reelle).
    """
    triangle = build_triangle_paiements(df, nature=nature, cumule=True,
                                        annee_observation=annee_observation)
    sap_reel = sap_comptable_courant(df, nature, annee_observation)

    lignes = {}

    # --- Chain-Ladder brut ---
    cl = chain_ladder_full(triangle)
    lignes["Chain-Ladder brut"] = (cl["total_paye"], cl["total_ultime"], cl["total_reserves"])

    # --- Chain-Ladder ecrete ---
    cle = chain_ladder_ecrete(df, nature=nature, quantile=quantile_ecretement)
    lignes["Chain-Ladder ecrete"] = (
        cle["cl_brut"]["total_paye"], cle["ultime_ecrete"], cle["reserves_ecrete"]
    )

    # --- Bornhuetter-Ferguson (loss ratio calibre sur annees a prime reelle) ---
    if (prime_acquise_serie is not None and pa_reelle is not None
            and annees_fiables and not triangle.empty):
        loss_ratio = loss_ratio_segment(
            cl["resultats"]["charge_ultime"], pa_reelle, annees_fiables
        )
        if pd.notna(loss_ratio):
            a_priori = prime_acquise_serie * loss_ratio
            bf = bornhuetter_ferguson(triangle, a_priori)
            lignes["Bornhuetter-Ferguson"] = (
                bf["total_paye"], bf["total_ultime_bf"], bf["total_reserves_bf"]
            )

    # --- Methode CM ---
    try:
        cm = methode_cm_encadrant(df, nature=nature, annee_observation=annee_observation)
        # CM raisonne en CHARGE (paye + SAP) : reserves = ultime - paye cumule
        reserves_cm = cm["total_ultime_cm"] - cm["total_reglement"]
        lignes["Methode CM"] = (cm["total_reglement"], cm["total_ultime_cm"], reserves_cm)
    except Exception as e:  # pragma: no cover
        logger.warning("Methode CM indisponible pour %s : %s", nature, e)

    tab = pd.DataFrame.from_dict(
        lignes, orient="index", columns=["paye", "ultime", "reserves"]
    )
    tab["sap_comptable"] = sap_reel
    tab["ibnr_estime"] = tab["reserves"] - sap_reel
    tab["boni_mali"] = sap_reel - tab["reserves"]
    tab.index.name = f"Methode ({nature})"
    return tab.round(0)


# ------------------------------------------------------------------
# Consolidation Best Estimate (choix d'une methode par segment)
# ------------------------------------------------------------------
def consolider_best_estimate(
    df: pd.DataFrame,
    df_ppna: pd.DataFrame | None = None,
    methode_par_segment: dict[str, str] | None = None,
    quantile_ecretement: float = 0.99,
    annee_observation: int | None = None,
    ppna_totale: float | None = None,
) -> dict:
    """
    Consolide le Best Estimate sinistres par segment, confronte au reel,
    et ajoute optionnellement la PPNA pour les provisions techniques totales.

    methode_par_segment : ex {"CORPOREL": "Chain-Ladder ecrete",
                              "MATERIEL": "Chain-Ladder ecrete"}
    """
    if methode_par_segment is None:
        methode_par_segment = {s: "Chain-Ladder ecrete" for s in SEGMENTS}

    # prime acquise commune (pour BF)
    prime_serie = None
    pa_reelle = None
    annees_fiables = None
    if df_ppna is not None:
        annees = sorted(
            pd.to_numeric(df["ANNEE_SURVENANCE"], errors="coerce").dropna().astype(int).unique()
        )
        pa_reelle = premium_reel_par_annee(df_ppna)
        annees_fiables = annees_prime_fiables(pa_reelle)
        # a priori BF : on remplace la prime acquise 2024 par la valeur
        # officielle de l'encadrant (Compte Technique), les autres annees
        # restant sur nos valeurs calculees.
        from autoreserve.config import PRIME_ACQUISE_ENCADRANT
        prime_serie = preparer_prime_acquise_serie(
            df_ppna, annees, annees_fiables, override=PRIME_ACQUISE_ENCADRANT
        )

    comparatifs = {}
    synthese_rows = []
    for seg in SEGMENTS:
        tab = comparatif_segment(
            df, seg, prime_acquise_serie=prime_serie,
            pa_reelle=pa_reelle, annees_fiables=annees_fiables,
            quantile_ecretement=quantile_ecretement,
            annee_observation=annee_observation,
        )
        comparatifs[seg] = tab

        methode = methode_par_segment.get(seg, "Chain-Ladder ecrete")
        if methode not in tab.index:
            methode = "Chain-Ladder ecrete"
        choix = tab.loc[methode]
        synthese_rows.append({
            "segment": seg,
            "methode_retenue": methode,
            "paye": choix["paye"],
            "ultime": choix["ultime"],
            "reserves_estimees": choix["reserves"],
            "sap_comptable": choix["sap_comptable"],
            "ibnr_estime": choix["ibnr_estime"],
            "boni_mali": choix["boni_mali"],
        })

    synthese = pd.DataFrame(synthese_rows).set_index("segment")

    total = {
        "reserves_estimees": float(synthese["reserves_estimees"].sum()),
        "sap_comptable": float(synthese["sap_comptable"].sum()),
        "ibnr_estime": float(synthese["ibnr_estime"].sum()),
        "boni_mali": float(synthese["boni_mali"].sum()),
        "best_estimate_sinistres": float(synthese["reserves_estimees"].sum()),
    }
    if ppna_totale is not None:
        total["ppna"] = float(ppna_totale)
        total["provisions_techniques_totales"] = (
            total["best_estimate_sinistres"] + float(ppna_totale)
        )

    logger.info(
        "Best Estimate sinistres = %.0f DT (SAP comptable %.0f, IBNR %.0f)",
        total["best_estimate_sinistres"], total["sap_comptable"], total["ibnr_estime"],
    )

    return {
        "comparatifs_par_segment": comparatifs,
        "synthese": synthese.round(0),
        "total": {k: round(v, 0) for k, v in total.items()},
        "methode_par_segment": methode_par_segment,
    }
