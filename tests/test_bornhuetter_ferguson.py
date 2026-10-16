"""Bornhuetter-Ferguson : betas et formule d'ultime."""

import pandas as pd

from autoreserve.simulation import generer_triangle_paiements
from autoreserve.sinistres.bornhuetter_ferguson import (
    compute_beta_from_link_ratios,
    bornhuetter_ferguson,
)

PATTERN = [0.4, 0.3, 0.2, 0.1]
ULTIMES = {2021: 1000.0, 2022: 2000.0, 2023: 1500.0, 2024: 3000.0}


def test_beta_depuis_facteurs():
    """Beta_k = 1 / produit des f_j (j>=k)."""
    lr = pd.Series({0: 2.0, 1: 1.5, 2: 1.0})
    beta = compute_beta_from_link_ratios(lr)
    assert abs(beta[3] - 1.0) < 1e-9
    assert abs(beta[2] - 1.0) < 1e-9             # 1/1.0
    assert abs(beta[1] - 1 / 1.5) < 1e-9
    assert abs(beta[0] - 1 / (2.0 * 1.5 * 1.0)) < 1e-9


def test_bf_annee_mature_ignore_a_priori():
    """Pour une annee totalement developpee (beta=1), BF = paye (a priori sans effet)."""
    tri = generer_triangle_paiements(ULTIMES, PATTERN, cv_bruit=0.0)
    # a priori volontairement absurde : l'annee mature ne doit pas en dependre
    a_priori = pd.Series({a: 10 * u for a, u in ULTIMES.items()})
    res = bornhuetter_ferguson(tri, a_priori)["resultats"]
    annee_mature = min(ULTIMES)  # 2021, developpee a 100%
    paye = res.loc[annee_mature, "paiement_cumule_actuel"]
    ult = res.loc[annee_mature, "ultime_bf"]
    assert abs(ult - paye) < 1e-6


def test_bf_entre_paye_et_a_priori():
    """Pour une annee immature, l'ultime BF est entre le paye et le paye + a priori."""
    tri = generer_triangle_paiements(ULTIMES, PATTERN, cv_bruit=0.0)
    a_priori = pd.Series({a: u for a, u in ULTIMES.items()})
    res = bornhuetter_ferguson(tri, a_priori)["resultats"]
    annee_recente = max(ULTIMES)  # 2024, immature
    paye = res.loc[annee_recente, "paiement_cumule_actuel"]
    ult = res.loc[annee_recente, "ultime_bf"]
    assert ult >= paye
