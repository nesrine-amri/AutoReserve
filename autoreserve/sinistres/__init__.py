"""Sous-package sinistres : chargement, triangles, provisionnement."""

from autoreserve.sinistres.loader import (
    load_sinistres,
    data_quality_report_sinistres,
)
from autoreserve.sinistres.ecretement import (
    paiement_total_par_sinistre,
    determiner_seuil,
    chain_ladder_ecrete,
    sensibilite_seuil,
)
from autoreserve.sinistres.bootstrap import bootstrap_odp
from autoreserve.sinistres.consolidation import (
    sap_comptable_courant,
    comparatif_segment,
    consolider_best_estimate,
    preparer_prime_acquise_serie,
    premium_reel_par_annee,
    annees_prime_fiables,
    loss_ratio_segment,
)

__all__ = [
    "load_sinistres",
    "data_quality_report_sinistres",
    "paiement_total_par_sinistre",
    "determiner_seuil",
    "chain_ladder_ecrete",
    "sensibilite_seuil",
    "sap_comptable_courant",
    "comparatif_segment",
    "consolider_best_estimate",
    "preparer_prime_acquise_serie",
    "premium_reel_par_annee",
    "annees_prime_fiables",
    "loss_ratio_segment",
    "bootstrap_odp",
]