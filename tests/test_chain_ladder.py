"""Chain-Ladder : retrouve-t-il l'ultime connu par construction ?"""

import numpy as np

from autoreserve.simulation import generer_triangle_paiements, pattern_vers_facteurs
from autoreserve.sinistres.chain_ladder import chain_ladder_full, compute_link_ratios

PATTERN = [0.4, 0.3, 0.2, 0.1]            # 4 periodes de developpement
ULTIMES = {2021: 1000.0, 2022: 2000.0, 2023: 1500.0, 2024: 3000.0}


def test_chain_ladder_recupere_ultime_exact():
    """Sans bruit, le CL volume doit retrouver la somme des ultimes a l'euro pres."""
    tri = generer_triangle_paiements(ULTIMES, PATTERN, cv_bruit=0.0)
    res = chain_ladder_full(tri)
    assert abs(res["total_ultime"] - sum(ULTIMES.values())) < 1e-6


def test_chain_ladder_ultime_par_annee():
    """Chaque ultime annuel est retrouve exactement."""
    tri = generer_triangle_paiements(ULTIMES, PATTERN, cv_bruit=0.0)
    res = chain_ladder_full(tri)["resultats"]
    for annee, u in ULTIMES.items():
        assert abs(res.loc[annee, "charge_ultime"] - u) < 1e-6


def test_link_ratios_coherents_avec_pattern():
    """Les facteurs f_k estimes = facteurs theoriques du pattern."""
    tri = generer_triangle_paiements(ULTIMES, PATTERN, cv_bruit=0.0)
    lr = compute_link_ratios(tri)
    attendus = pattern_vers_facteurs(PATTERN)
    obtenus = [float(lr.iloc[k]) for k in range(len(attendus))]
    assert np.allclose(obtenus, attendus, rtol=1e-6)


def test_reserves_coherentes():
    """Reserves = ultime - paye, et positives sur ce jeu."""
    tri = generer_triangle_paiements(ULTIMES, PATTERN, cv_bruit=0.0)
    res = chain_ladder_full(tri)
    assert abs(res["total_reserves"] - (res["total_ultime"] - res["total_paye"])) < 1e-6
    assert res["total_reserves"] > 0
