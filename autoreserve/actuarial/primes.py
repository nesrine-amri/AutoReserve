"""
Calcul PPNA et Prime Acquise - Version 2.

Ameliorations vs V1 :
- Separation claire PPNA reglementaire (prime nette seule)
  vs PPNA complementaire (frais differes)
- Gestion optionnelle des retours (contrats avec CODE_MOTIF_RETOUR)
- Ventilation par nature de contrat (F/R/S/T)
- Rapport de qualite des donnees

CONVENTION ACTUARIELLE :
- PPNA REGLEMENTAIRE = PPNA sur PRIME NETTE uniquement
  (conforme CGA Tunisie, IFRS 17, Solvabilite II)
- Les frais d'acquisition ont un traitement separe.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Union

import pandas as pd

from autoreserve.actuarial.dates import (
    DateLike,
    compute_duree_jours,
    compute_jours_restants,
    compute_prorata,
    _to_datetime,
)

logger = logging.getLogger(__name__)


def compute_ppna(
    df: pd.DataFrame,
    date_cloture: DateLike,
    col_prime: str = "TOTAL_PRIME_NETTE",
    col_frais: str = "FRAIS",
    col_du: str = "VALIDITE_DU",
    col_au: str = "VALIDITE_AU",
    add_intermediate_cols: bool = True,
) -> pd.DataFrame:
    """
    Calcule la PPNA pour chaque contrat, avec separation reglementaire/frais.
    """
    df = df.copy()
    cloture = _to_datetime(date_cloture)

    logger.info(f"Calcul PPNA au {cloture.date()}")

    duree = compute_duree_jours(df[col_du], df[col_au])
    jours_restants = compute_jours_restants(
        validite_au=df[col_au],
        date_cloture=cloture,
        validite_du=df[col_du],
    )
    prorata = compute_prorata(jours_restants, duree)

    prime_nette = pd.to_numeric(df[col_prime], errors="coerce")
    frais = pd.to_numeric(df[col_frais], errors="coerce")

    ppna_reglementaire = prime_nette * prorata
    ppna_frais = frais * prorata
    ppna_totale_info = ppna_reglementaire.fillna(0) + ppna_frais.fillna(0)

    du = pd.to_datetime(df[col_du], errors="coerce")
    au = pd.to_datetime(df[col_au], errors="coerce")
    statut = pd.Series("EN_COURS", index=df.index, dtype="object")
    statut[au <= cloture] = "ETEINT"
    statut[du > cloture] = "NON_COMMENCE"
    statut[du.isna() | au.isna()] = "INVALIDE"

    if add_intermediate_cols:
        df["DUREE_TOTALE_JOURS"] = duree
        df["JOURS_RESTANTS"] = jours_restants
        df["PRORATA_NON_ACQUIS"] = prorata

    df["PPNA_REGLEMENTAIRE"] = ppna_reglementaire
    df["PPNA_FRAIS_DIFFERES"] = ppna_frais
    df["PPNA_TOTALE_INFO"] = ppna_totale_info
    df["STATUT_CONTRAT_CLOTURE"] = statut

    n_eteint = (statut == "ETEINT").sum()
    n_en_cours = (statut == "EN_COURS").sum()
    n_non_commence = (statut == "NON_COMMENCE").sum()
    n_invalide = (statut == "INVALIDE").sum()

    logger.info(
        f"  Statuts : ETEINT={n_eteint:,} | EN_COURS={n_en_cours:,} | "
        f"NON_COMMENCE={n_non_commence:,} | INVALIDE={n_invalide:,}"
    )
    logger.info(f"  PPNA REGLEMENTAIRE (norme CGA) : {ppna_reglementaire.sum():,.2f}")
    logger.info(f"  PPNA frais differes            : {ppna_frais.sum():,.2f}")

    return df


def compute_prime_acquise(
    df: pd.DataFrame,
    col_prime: str = "TOTAL_PRIME_NETTE",
    col_frais: str = "FRAIS",
    col_prorata: str = "PRORATA_NON_ACQUIS",
) -> pd.DataFrame:
    """Calcule Prime Acquise = Prime Emise * (1 - prorata non acquis)."""
    df = df.copy()

    if col_prorata not in df.columns:
        raise ValueError(
            f"Colonne '{col_prorata}' absente. Appeler compute_ppna() d'abord."
        )

    prime_nette = pd.to_numeric(df[col_prime], errors="coerce")
    frais = pd.to_numeric(df[col_frais], errors="coerce")
    prorata = pd.to_numeric(df[col_prorata], errors="coerce")

    part_acquise = 1 - prorata

    df["PRIME_ACQUISE_NETTE"] = prime_nette * part_acquise
    df["FRAIS_ACQUIS"] = frais * part_acquise
    df["PRIME_ACQUISE_TOTALE"] = (
        df["PRIME_ACQUISE_NETTE"].fillna(0) + df["FRAIS_ACQUIS"].fillna(0)
    )

    logger.info(f"  Prime Acquise nette : {df['PRIME_ACQUISE_NETTE'].sum():,.2f}")

    return df


def filter_returned_contracts(
    df: pd.DataFrame,
    col_motif: str = "CODE_MOTIF_RETOUR",
    return_stats: bool = False,
):
    """Filtre les contrats avec motif de retour non vide."""
    if col_motif not in df.columns:
        logger.warning(f"Colonne '{col_motif}' absente : aucun filtrage applique")
        if return_stats:
            return df, {"n_before": len(df), "n_after": len(df), "n_excluded": 0}
        return df

    n_before = len(df)

    has_motif = (
        df[col_motif].notna()
        & (df[col_motif].astype(str).str.strip() != "")
        & (df[col_motif].astype(str).str.strip() != "<NA>")
        & (df[col_motif].astype(str).str.strip().str.lower() != "nan")
    )

    df_filtered = df[~has_motif].copy()
    n_excluded = has_motif.sum()
    n_after = len(df_filtered)

    logger.info(
        f"  Filtrage retours : {n_excluded:,} contrats exclus "
        f"({n_before:,} -> {n_after:,})"
    )

    if return_stats:
        stats = {
            "n_before": n_before,
            "n_after": n_after,
            "n_excluded": n_excluded,
            "pct_excluded": 100 * n_excluded / n_before if n_before else 0,
        }
        return df_filtered, stats

    return df_filtered


def data_quality_report(df: pd.DataFrame) -> dict:
    """Genere un rapport de qualite des donnees."""
    report = {"n_total": len(df), "issues": {}}

    if "VALIDITE_DU" in df.columns:
        n = pd.to_datetime(df["VALIDITE_DU"], errors="coerce").isna().sum()
        report["issues"]["dates_du_manquantes"] = int(n)

    if "VALIDITE_AU" in df.columns:
        n = pd.to_datetime(df["VALIDITE_AU"], errors="coerce").isna().sum()
        report["issues"]["dates_au_manquantes"] = int(n)

    if "TOTAL_PRIME_NETTE" in df.columns:
        v = pd.to_numeric(df["TOTAL_PRIME_NETTE"], errors="coerce")
        report["issues"]["primes_manquantes"] = int(v.isna().sum())
        report["issues"]["primes_negatives"] = int((v < 0).sum())
        report["issues"]["primes_a_zero"] = int((v == 0).sum())

    if "VALIDITE_DU" in df.columns and "VALIDITE_AU" in df.columns:
        du = pd.to_datetime(df["VALIDITE_DU"], errors="coerce")
        au = pd.to_datetime(df["VALIDITE_AU"], errors="coerce")
        n = ((au < du) & du.notna() & au.notna()).sum()
        report["issues"]["duree_invalide"] = int(n)

    if "CODE_MOTIF_RETOUR" in df.columns:
        has_motif = (
            df["CODE_MOTIF_RETOUR"].notna()
            & (df["CODE_MOTIF_RETOUR"].astype(str).str.strip() != "")
            & (df["CODE_MOTIF_RETOUR"].astype(str).str.strip().str.lower() != "nan")
        )
        report["issues"]["contrats_avec_motif_retour"] = int(has_motif.sum())

    total_issues = sum(v for k, v in report["issues"].items()
                       if k not in ("primes_a_zero",))
    report["quality_score"] = round(100 * (1 - total_issues / len(df)), 2) if len(df) else 0

    return report


def compute_ppna_portefeuille(
    df: pd.DataFrame,
    date_cloture: DateLike,
    col_prime: str = "TOTAL_PRIME_NETTE",
    col_frais: str = "FRAIS",
    col_du: str = "VALIDITE_DU",
    col_au: str = "VALIDITE_AU",
    exclude_returns: bool = False,
    exclure_contre_passations: bool = False,
) -> pd.DataFrame:
    """
    Applique PPNA + Prime Acquise en une seule etape.

    exclure_contre_passations : si True, retire les lignes a prime NEGATIVE
        (annulations / contre-passations). La base devient "primes emises
        brutes", alignee sur la definition du Compte Technique de l'encadrant.
    """
    if exclude_returns:
        df = filter_returned_contracts(df)

    if exclure_contre_passations:
        prime = pd.to_numeric(df[col_prime], errors="coerce")
        n_avant = len(df)
        df = df[~(prime < 0)].copy()
        logger.info(
            f"  Contre-passations exclues : {n_avant - len(df):,} lignes "
            f"a prime negative retirees ({n_avant:,} -> {len(df):,})"
        )

    df = compute_ppna(
        df,
        date_cloture=date_cloture,
        col_prime=col_prime,
        col_frais=col_frais,
        col_du=col_du,
        col_au=col_au,
    )
    df = compute_prime_acquise(
        df,
        col_prime=col_prime,
        col_frais=col_frais,
    )
    return df


def aggregate_ppna_by_segment(
    df: pd.DataFrame,
    groupby_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Aggrege les resultats PPNA par segment."""
    if groupby_cols is None:
        groupby_cols = ["ANNEE_EXERCICE", "TYPE_BASE"]

    cols_manquantes = [c for c in groupby_cols if c not in df.columns]
    if cols_manquantes:
        raise ValueError(f"Colonnes de groupement absentes : {cols_manquantes}")

    df = df.copy()
    for c in ["TOTAL_PRIME_NETTE", "FRAIS"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    agg = df.groupby(groupby_cols).agg(
        nb_polices=("NUM_CONTRAT", "count"),
        prime_emise_nette=("TOTAL_PRIME_NETTE", "sum"),
        frais_emis=("FRAIS", "sum"),
        ppna_reglementaire=("PPNA_REGLEMENTAIRE", "sum"),
        ppna_frais_differes=("PPNA_FRAIS_DIFFERES", "sum"),
        ppna_totale_info=("PPNA_TOTALE_INFO", "sum"),
        prime_acquise_nette=("PRIME_ACQUISE_NETTE", "sum"),
    )

    agg["taux_non_acquis_pct"] = (
        100 * agg["ppna_reglementaire"] / agg["prime_emise_nette"]
    ).round(2)

    return agg


def aggregate_by_nature_contrat(df: pd.DataFrame) -> pd.DataFrame:
    """Ventilation par CODE_NATURE_CONTRAT (F, R, S, T...)."""
    if "CODE_NATURE_CONTRAT" not in df.columns:
        raise ValueError("Colonne CODE_NATURE_CONTRAT absente")

    df = df.copy()
    df["TOTAL_PRIME_NETTE"] = pd.to_numeric(df["TOTAL_PRIME_NETTE"], errors="coerce")

    agg = df.groupby(["ANNEE_EXERCICE", "CODE_NATURE_CONTRAT"]).agg(
        nb_polices=("NUM_CONTRAT", "count"),
        prime_emise_nette=("TOTAL_PRIME_NETTE", "sum"),
        ppna_reglementaire=("PPNA_REGLEMENTAIRE", "sum"),
    )

    agg["taux_non_acquis_pct"] = (
        100 * agg["ppna_reglementaire"] / agg["prime_emise_nette"]
    ).round(2)

    return agg