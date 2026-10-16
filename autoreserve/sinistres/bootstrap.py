"""
Bootstrap Over-Dispersed Poisson (ODP) du Chain-Ladder — England & Verrall (2002).

Objectif : passer d'une estimation PONCTUELLE des provisions a une DISTRIBUTION,
pour quantifier l'incertitude (erreur de prediction, quantiles, VaR 99,5% ~
niveau Solvabilite II).

Deux sources d'erreur sont combinees :
  - erreur d'ESTIMATION : reechantillonnage (avec remise) des residus de Pearson
    du triangle ajuste, puis re-calage du Chain-Ladder sur chaque pseudo-triangle ;
  - erreur de PROCESSUS : chaque paiement futur est simule selon le processus ODP
    (approximation Gamma de moyenne mu et variance phi*mu).

Entree : triangle de paiements CUMULES (NaN sous la diagonale courante).
Sortie : distribution de la provision (totale), stats et quantiles.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _facteurs_volume(C: np.ndarray, obs: np.ndarray) -> np.ndarray:
    """Coefficients de developpement Chain-Ladder (volume)."""
    K = C.shape[1]
    f = np.ones(K - 1)
    for k in range(K - 1):
        m = obs[:, k + 1] & obs[:, k]
        den = np.where(m, C[:, k], 0.0).sum()
        num = np.where(m, C[:, k + 1], 0.0).sum()
        f[k] = num / den if den > 0 else 1.0
    return f


def bootstrap_odp(
    triangle: pd.DataFrame,
    n_sim: int = 2000,
    seed: int | None = 42,
) -> dict:
    """
    Bootstrap ODP sur un triangle de paiements cumules.

    Returns
    -------
    dict : reserves (array), best_estimate_cl, mean, std, cv_pct,
           se_prediction, quantiles {50,75,95,99.5}, n_sim
    """
    if triangle.empty:
        return {"error": "Triangle vide"}

    annees = list(triangle.index)
    C = triangle.values.astype(float)
    I, K = C.shape
    obs = ~np.isnan(C)

    # --- Chain-Ladder de reference ---
    f = _facteurs_volume(C, obs)
    last_dev = np.array([np.where(obs[i])[0].max() for i in range(I)])
    latest = np.array([C[i, last_dev[i]] for i in range(I)])
    ultimate = np.array([
        latest[i] * (np.prod(f[last_dev[i]:]) if last_dev[i] < K - 1 else 1.0)
        for i in range(I)
    ])
    reserve_cl = float((ultimate - latest).sum())

    # --- Valeurs ajustees (back-fit depuis l'ultime) ---
    beta = np.ones(K)
    for k in range(K - 2, -1, -1):
        beta[k] = beta[k + 1] / f[k] if f[k] != 0 else np.nan
    Chat = np.outer(ultimate, beta)                      # cumule ajuste
    Mhat = np.empty((I, K)); Mhat[:, 0] = Chat[:, 0]
    Mhat[:, 1:] = np.diff(Chat, axis=1)                  # incremental ajuste

    # incrementaux observes
    Q = np.full((I, K), np.nan); Q[:, 0] = C[:, 0]
    Q[:, 1:] = np.diff(C, axis=1)

    # --- Residus de Pearson (cellules observees, ajuste > 0) ---
    cellules = obs & (Mhat > 0) & ~np.isnan(Q)
    r = np.zeros((I, K))
    r[cellules] = (Q[cellules] - Mhat[cellules]) / np.sqrt(Mhat[cellules])
    residus = r[cellules]

    N = int(cellules.sum())
    p = I + K - 1                       # nb de parametres du modele
    dof = max(N - p, 1)
    phi = float((residus ** 2).sum() / dof)          # parametre de dispersion
    residus_adj = residus * np.sqrt(N / dof)

    if phi <= 0 or not np.isfinite(phi):
        phi = 1e-6

    # --- Boucle bootstrap ---
    rng = np.random.default_rng(seed)
    idx = np.where(cellules)
    reserves = np.empty(n_sim)

    for b in range(n_sim):
        # 1) pseudo incrementaux = ajuste + residu reechantillonne * sqrt(ajuste)
        rstar = rng.choice(residus_adj, size=N, replace=True)
        Qstar = Mhat.copy()
        Qstar[idx] = Mhat[idx] + rstar * np.sqrt(Mhat[idx])

        # 2) pseudo cumule + re-calage des facteurs
        Cstar = np.where(obs, np.cumsum(np.where(obs, Qstar, 0.0), axis=1), np.nan)
        fstar = _facteurs_volume(np.nan_to_num(Cstar), obs)

        # 3) projection + erreur de processus (Gamma)
        reserve_b = 0.0
        for i in range(I):
            c_cur = Cstar[i, last_dev[i]]
            for k in range(last_dev[i], K - 1):
                mu = c_cur * (fstar[k] - 1.0)             # increment futur attendu
                if mu > 0:
                    sim = rng.gamma(mu / phi, phi)        # variance = phi*mu
                else:
                    sim = mu
                reserve_b += sim
                c_cur += sim
        reserves[b] = reserve_b

    reserves = reserves[np.isfinite(reserves)]
    moyenne = float(reserves.mean())
    ecart_type = float(reserves.std(ddof=1))

    q = {
        "50%": float(np.percentile(reserves, 50)),
        "75%": float(np.percentile(reserves, 75)),
        "95%": float(np.percentile(reserves, 95)),
        "99.5%": float(np.percentile(reserves, 99.5)),
    }

    logger.info(
        "Bootstrap ODP : BE_CL=%.0f, moyenne=%.0f, SE=%.0f (CV=%.1f%%)",
        reserve_cl, moyenne, ecart_type, 100 * ecart_type / moyenne if moyenne else 0,
    )

    return {
        "reserves": reserves,
        "best_estimate_cl": reserve_cl,
        "mean": moyenne,
        "std": ecart_type,
        "cv_pct": round(100 * ecart_type / moyenne, 2) if moyenne else np.nan,
        "se_prediction": ecart_type,
        "quantiles": q,
        "phi": phi,
        "n_sim": len(reserves),
    }
