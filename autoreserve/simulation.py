"""
Simulateur de donnees actuarielles a VERITE CONNUE.

Principe : on fabrique des donnees dont on connait exactement la reponse
(ultime, PPNA, graves), on fait tourner les methodes, et on verifie qu'elles
retrouvent la verite. Sert a la fois aux tests (validation) et a la page
Simulateur de la plateforme (demonstration interactive).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def generer_triangle_paiements(
    ultimes: dict[int, float],
    pattern: list[float],
    annee_observation: int | None = None,
    cv_bruit: float = 0.0,
    seed: int | None = 0,
) -> pd.DataFrame:
    """
    Triangle de paiements CUMULES a partir d'ultimes et d'un schema de
    developpement connus. Avec cv_bruit=0, le Chain-Ladder volume retrouve les
    ultimes EXACTEMENT.

    ultimes  : {annee_survenance: ultime vrai}
    pattern  : proportions INCREMENTALES de l'ultime (somme = 1).
    cv_bruit : coefficient de variation du bruit multiplicatif (0 = exact).
    """
    rng = np.random.default_rng(seed)
    pattern = np.asarray(pattern, dtype=float)
    assert abs(pattern.sum() - 1.0) < 1e-9, "pattern doit sommer a 1"

    annees = sorted(ultimes)
    K = len(pattern)
    if annee_observation is None:
        annee_observation = max(annees)

    incr = np.zeros((len(annees), K))
    for i, a in enumerate(annees):
        base = ultimes[a] * pattern
        if cv_bruit > 0:
            base = base * rng.normal(1.0, cv_bruit, size=K).clip(min=0)
        incr[i] = base

    cumul = np.cumsum(incr, axis=1)
    tri = pd.DataFrame(cumul, index=annees, columns=list(range(K)))

    for i, a in enumerate(annees):
        dev_max = annee_observation - a
        for k in range(K):
            if k > dev_max:
                tri.iloc[i, k] = np.nan

    tri.index.name = "ANNEE_SURVENANCE"
    tri.columns.name = "INDICE_DEV"
    return tri


def pattern_vers_facteurs(pattern: list[float]) -> list[float]:
    """Facteurs de developpement theoriques f_k attendus pour un pattern donne."""
    beta = np.cumsum(pattern)
    return [float(beta[k + 1] / beta[k]) for k in range(len(pattern) - 1)]


def ultimes_croissance(
    annees: list[int], ultime_base: float, croissance_pct: float
) -> dict[int, float]:
    """Ultimes suivant une croissance geometrique annuelle (pour la demo)."""
    g = 1 + croissance_pct / 100.0
    return {a: ultime_base * (g ** i) for i, a in enumerate(sorted(annees))}


def generer_contrats_ppna(specs: list[dict]) -> pd.DataFrame:
    """Base de contrats pour tester la PPNA (dates + prime connues)."""
    rows = []
    for i, s in enumerate(specs):
        rows.append({
            "NUM_CONTRAT": s.get("NUM_CONTRAT", f"C{i:04d}"),
            "VALIDITE_DU": pd.Timestamp(s["VALIDITE_DU"]),
            "VALIDITE_AU": pd.Timestamp(s["VALIDITE_AU"]),
            "TOTAL_PRIME_NETTE": float(s.get("prime", 0.0)),
            "FRAIS": float(s.get("frais", 0.0)),
        })
    return pd.DataFrame(rows)


def generer_base_sinistres(
    ultimes_corp: dict[int, float],
    ultimes_mat: dict[int, float],
    pattern: list[float],
    annee_observation: int | None = None,
) -> pd.DataFrame:
    """Base sinistres (format loader) a partir d'ultimes connus. SAP = 0."""
    pattern = np.asarray(pattern, dtype=float)
    K = len(pattern)
    rows = []
    nsin = 0
    for nature, ultimes in [("CORPOREL", ultimes_corp), ("MATERIEL", ultimes_mat)]:
        for a, u in ultimes.items():
            incr = u * pattern
            for k in range(K):
                nsin += 1
                rows.append({
                    "NUM_SINISTRE": f"S{nsin:06d}",
                    "ANNEE_SURVENANCE": a,
                    "ANNEE_DEVELOPPEMENT": a + k,
                    "INDICE_DEV": k,
                    "NATURE_SINISTRE": nature,
                    "SINISTRE_PAYE": float(incr[k]),
                    "SAP": 0.0,
                })
    df = pd.DataFrame(rows)
    for c in ["ANNEE_SURVENANCE", "ANNEE_DEVELOPPEMENT", "INDICE_DEV"]:
        df[c] = df[c].astype("Int64")
    return df
