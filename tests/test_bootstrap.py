"""Bootstrap ODP : la distribution est-elle centree sur le Best Estimate ?"""

from autoreserve.simulation import generer_triangle_paiements
from autoreserve.sinistres.bootstrap import bootstrap_odp

PATTERN = [0.4, 0.3, 0.2, 0.1]
ULTIMES = {2021: 10_000.0, 2022: 12_000.0, 2023: 15_000.0, 2024: 18_000.0}


def test_moyenne_bootstrap_proche_best_estimate():
    """La moyenne des provisions simulees doit approcher le BE Chain-Ladder."""
    tri = generer_triangle_paiements(ULTIMES, PATTERN, cv_bruit=0.10, seed=1)
    r = bootstrap_odp(tri, n_sim=1000, seed=1)
    ecart_rel = abs(r["mean"] - r["best_estimate_cl"]) / r["best_estimate_cl"]
    assert ecart_rel < 0.15


def test_quantiles_ordonnes():
    """Les quantiles sont croissants et l'incertitude est positive."""
    tri = generer_triangle_paiements(ULTIMES, PATTERN, cv_bruit=0.10, seed=2)
    r = bootstrap_odp(tri, n_sim=1000, seed=2)
    q = r["quantiles"]
    assert q["50%"] <= q["75%"] <= q["95%"] <= q["99.5%"]
    assert r["std"] > 0
    assert r["cv_pct"] > 0
