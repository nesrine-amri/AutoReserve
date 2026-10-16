"""Sous-package actuarial : calculs PPNA, Prime Acquise, coherence."""

from autoreserve.actuarial.primes import (
    compute_ppna,
    compute_prime_acquise,
    compute_ppna_portefeuille,
    filter_returned_contracts,
    data_quality_report,
    aggregate_ppna_by_segment,
    aggregate_by_nature_contrat,
)
from autoreserve.actuarial.dates import (
    compute_duree_jours,
    compute_jours_restants,
    compute_prorata,
)

__all__ = [
    "compute_ppna",
    "compute_prime_acquise",
    "compute_ppna_portefeuille",
    "filter_returned_contracts",
    "data_quality_report",
    "aggregate_ppna_by_segment",
    "aggregate_by_nature_contrat",
    "compute_duree_jours",
    "compute_jours_restants",
    "compute_prorata",
]