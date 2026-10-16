"""PPNA : le prorata temporis est-il exact selon les dates de validite ?"""

from datetime import date

from autoreserve.simulation import generer_contrats_ppna
from autoreserve.actuarial.primes import compute_ppna, compute_ppna_portefeuille

CLOTURE = date(2024, 12, 31)


def test_prorata_contrat_a_cheval():
    """Contrat 01/07/2024 -> 30/06/2025 : PPNA = prime * 181/365."""
    df = generer_contrats_ppna([
        {"VALIDITE_DU": "2024-07-01", "VALIDITE_AU": "2025-06-30", "prime": 1000.0}
    ])
    r = compute_ppna(df, CLOTURE)
    attendu = 1000.0 * 181 / 365  # duree=365, jours restants=181
    assert abs(r["PPNA_REGLEMENTAIRE"].iloc[0] - attendu) < 1e-6


def test_contrat_eteint_ppna_nulle():
    """Contrat termine avant la cloture -> PPNA = 0 (prime acquise)."""
    df = generer_contrats_ppna([
        {"VALIDITE_DU": "2023-06-01", "VALIDITE_AU": "2024-05-31", "prime": 1000.0}
    ])
    r = compute_ppna(df, CLOTURE)
    assert r["PPNA_REGLEMENTAIRE"].iloc[0] == 0


def test_contrat_non_commence_ppna_totale():
    """Contrat demarrant apres la cloture -> PPNA = prime entiere."""
    df = generer_contrats_ppna([
        {"VALIDITE_DU": "2025-03-01", "VALIDITE_AU": "2026-02-28", "prime": 1000.0}
    ])
    r = compute_ppna(df, CLOTURE)
    assert abs(r["PPNA_REGLEMENTAIRE"].iloc[0] - 1000.0) < 1e-6


def test_identite_comptable_ppna_plus_acquise():
    """PPNA + Prime Acquise = Prime emise (identite exacte)."""
    df = generer_contrats_ppna([
        {"VALIDITE_DU": "2024-07-01", "VALIDITE_AU": "2025-06-30", "prime": 1000.0},
        {"VALIDITE_DU": "2024-01-01", "VALIDITE_AU": "2024-12-31", "prime": 500.0},
        {"VALIDITE_DU": "2024-10-01", "VALIDITE_AU": "2025-09-30", "prime": 800.0},
    ])
    r = compute_ppna_portefeuille(df, CLOTURE)
    prime = df["TOTAL_PRIME_NETTE"].sum()
    total = r["PPNA_REGLEMENTAIRE"].sum() + r["PRIME_ACQUISE_NETTE"].sum()
    assert abs(total - prime) < 1e-6
