"""Ecretement : un sinistre grave est-il bien detecte et son effet ecrete ?"""

import pandas as pd

from autoreserve.simulation import generer_base_sinistres
from autoreserve.sinistres.ecretement import (
    determiner_seuil,
    chain_ladder_ecrete,
    paiement_total_par_sinistre,
)

PATTERN = [0.5, 0.3, 0.2]
ULTIMES = {2022: 1000.0, 2023: 1000.0, 2024: 1000.0}


def _base_avec_grave(montant_grave: float) -> pd.DataFrame:
    df = generer_base_sinistres(ULTIMES, ULTIMES, PATTERN)
    grave = pd.DataFrame([{
        "NUM_SINISTRE": "GRAVE_01", "ANNEE_SURVENANCE": 2022,
        "ANNEE_DEVELOPPEMENT": 2022, "INDICE_DEV": 0,
        "NATURE_SINISTRE": "CORPOREL", "SINISTRE_PAYE": montant_grave, "SAP": 0.0,
    }])
    for c in ["ANNEE_SURVENANCE", "ANNEE_DEVELOPPEMENT", "INDICE_DEV"]:
        grave[c] = grave[c].astype("Int64")
    return pd.concat([df, grave], ignore_index=True)


def test_grave_detecte():
    """Un sinistre tres au-dessus du seuil est compte comme grave."""
    df = _base_avec_grave(50_000.0)
    corp = df[df["NATURE_SINISTRE"] == "CORPOREL"]
    seuil = determiner_seuil(corp, quantile=0.90)
    charges = paiement_total_par_sinistre(corp)
    assert (charges >= seuil).sum() >= 1
    assert charges.max() == 50_000.0


def test_ecretement_reduit_ou_egale_ultime():
    """L'ultime ecrete ne depasse jamais l'ultime brut (le grave est plafonne)."""
    df = _base_avec_grave(50_000.0)
    res = chain_ladder_ecrete(df, nature="CORPOREL", quantile=0.90)
    assert res["ultime_ecrete"] <= res["cl_brut"]["total_ultime"] + 1e-6
    assert res["info_graves"]["n_graves"] >= 1


def test_sans_grave_ecretement_neutre_ou_proche():
    """Sans sinistre atypique, l'ecart d'ecretement reste modere."""
    df = generer_base_sinistres(ULTIMES, ULTIMES, PATTERN)
    res = chain_ladder_ecrete(df, nature="CORPOREL", quantile=0.99)
    brut = res["cl_brut"]["total_ultime"]
    assert abs(res["ultime_ecrete"] - brut) / brut < 0.30
