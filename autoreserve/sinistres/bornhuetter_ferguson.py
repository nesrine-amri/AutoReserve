"""
Methode Bornhuetter-Ferguson (BF) - from scratch.

Formule : Ultime_BF(i) = Paye_actuel(i) + A_priori(i) x (1 - Beta_i)
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
import pandas as pd

from autoreserve.sinistres.chain_ladder import compute_link_ratios

logger = logging.getLogger(__name__)


def compute_beta_from_link_ratios(link_ratios: pd.Series) -> pd.Series:
    """
    Beta_k = 1 / (produit des f_j pour j >= k)
    = fraction de la charge ultime deja atteinte a la fin de la dev k.
    """
    if link_ratios.empty:
        return pd.Series(dtype=float)

    devs_lr = sorted(link_ratios.index.tolist())
    dev_max = max(devs_lr) + 1

    beta = {dev_max: 1.0}

    for k in reversed(devs_lr):
        f_k = link_ratios[k]
        if pd.isna(f_k) or f_k == 0:
            beta[k] = np.nan
        else:
            beta[k] = beta[k + 1] / f_k

    return pd.Series(beta, name="beta").sort_index()


def compute_empirical_loss_ratio(
    charge_ultime_cl: pd.Series,
    prime_acquise: pd.Series,
    annees_matures: list[int] | None = None,
    seuil_maturite_pct: float = 90.0,
    taux_dev_par_annee: pd.Series | None = None,
) -> tuple[float, dict]:
    """
    Loss Ratio = Sum(Ultime CL annees matures) / Sum(Prime Acquise annees matures)
    """
    if annees_matures is None:
        if taux_dev_par_annee is None:
            raise ValueError("annees_matures ou taux_dev_par_annee requis")
        annees_matures = taux_dev_par_annee[
            taux_dev_par_annee >= seuil_maturite_pct
        ].index.tolist()

    if not annees_matures:
        return np.nan, {"annees_utilisees": [], "n_annees": 0}

    annees_ok = [a for a in annees_matures
                 if a in charge_ultime_cl.index and a in prime_acquise.index]

    if not annees_ok:
        return np.nan, {"annees_utilisees": [], "n_annees": 0}

    total_ultime = charge_ultime_cl.loc[annees_ok].sum()
    total_prime = prime_acquise.loc[annees_ok].sum()

    if total_prime == 0:
        return np.nan, {"annees_utilisees": annees_ok, "erreur": "prime nulle"}

    loss_ratio = total_ultime / total_prime

    details = {
        "annees_utilisees": annees_ok,
        "n_annees": len(annees_ok),
        "total_ultime_annees_matures": float(total_ultime),
        "total_prime_annees_matures": float(total_prime),
        "loss_ratio": float(loss_ratio),
    }

    logger.info(
        f"Loss Ratio empirique = {100*loss_ratio:.2f}% "
        f"(base {len(annees_ok)} annees matures)"
    )

    return loss_ratio, details


def bornhuetter_ferguson(
    triangle: pd.DataFrame,
    a_priori: pd.Series,
    method_link_ratios: Literal["volume", "simple_average"] = "volume",
) -> dict:
    """
    Applique BF. Formule : Ultime_BF(i) = Paye_actuel(i) + A_priori(i) x (1 - Beta_i)
    """
    if triangle.empty:
        return {"error": "Triangle vide"}

    logger.info(f"Bornhuetter-Ferguson sur triangle {triangle.shape}")

    link_ratios = compute_link_ratios(triangle, method=method_link_ratios)
    betas = compute_beta_from_link_ratios(link_ratios)

    devs = list(triangle.columns)
    paye_actuel = {}
    dev_actuel = {}

    for annee in triangle.index:
        ligne = triangle.loc[annee]
        connus = ligne.dropna()
        if len(connus) == 0:
            paye_actuel[annee] = 0
            dev_actuel[annee] = 0
        else:
            paye_actuel[annee] = connus.iloc[-1]
            dev_actuel[annee] = connus.index[-1]

    paye_actuel = pd.Series(paye_actuel, name="paiement_cumule_actuel")
    dev_actuel = pd.Series(dev_actuel, name="dev_actuel")

    beta_par_annee = dev_actuel.map(betas)
    a_priori_aligned = a_priori.reindex(triangle.index)

    ultime_bf = paye_actuel + a_priori_aligned * (1 - beta_par_annee)
    reserves_bf = ultime_bf - paye_actuel

    resultats = pd.DataFrame({
        "paiement_cumule_actuel": paye_actuel,
        "dev_actuel": dev_actuel,
        "beta": beta_par_annee,
        "a_priori": a_priori_aligned,
        "ultime_bf": ultime_bf,
        "reserves_bf": reserves_bf,
    })
    resultats.index.name = "ANNEE_SURVENANCE"

    total_paye = float(paye_actuel.sum())
    total_ultime = float(ultime_bf.sum())
    total_reserves = float(reserves_bf.sum())

    logger.info(f"  Paye actuel   : {total_paye:>15,.0f} DT")
    logger.info(f"  Ultime BF     : {total_ultime:>15,.0f} DT")
    logger.info(f"  Reserves BF   : {total_reserves:>15,.0f} DT")

    return {
        "link_ratios": link_ratios,
        "betas": betas,
        "a_priori": a_priori_aligned,
        "resultats": resultats,
        "total_paye": total_paye,
        "total_ultime_bf": total_ultime,
        "total_reserves_bf": total_reserves,
    }


def estimer_prime_acquise_historique(
    prime_acquise_recente: dict,
    annees_a_estimer: list,
    methode: Literal["progression_lineaire", "moyenne", "extrapolation"] = "progression_lineaire",
) -> pd.Series:
    """Estime la Prime Acquise pour les annees anterieures a la base primes."""
    annees_connues = sorted(prime_acquise_recente.keys())
    valeurs_connues = np.array([prime_acquise_recente[a] for a in annees_connues])

    if len(annees_connues) < 2:
        raise ValueError("Il faut au moins 2 annees connues")

    if methode == "progression_lineaire":
        annees_np = np.array(annees_connues, dtype=float)
        coefs = np.polyfit(annees_np, valeurs_connues, 1)
        pente, ordonnee = coefs
        estimations = {a: max(0, pente * a + ordonnee) for a in annees_a_estimer}

    elif methode == "moyenne":
        moy = float(np.mean(valeurs_connues))
        estimations = {a: moy for a in annees_a_estimer}

    elif methode == "extrapolation":
        ratios = valeurs_connues[1:] / valeurs_connues[:-1]
        taux = float(np.mean(ratios))
        annee_ref = annees_connues[0]
        val_ref = valeurs_connues[0]
        estimations = {a: val_ref * (taux ** (a - annee_ref)) for a in annees_a_estimer}

    else:
        raise ValueError(f"Methode inconnue : {methode}")

    toutes_valeurs = {**prime_acquise_recente, **estimations}
    result = pd.Series(toutes_valeurs).sort_index()
    result.name = "prime_acquise_estimee"

    return result