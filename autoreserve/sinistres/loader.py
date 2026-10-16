"""
Chargement et normalisation de la base sinistres auto.

Structure attendue (colonnes) :
- Numero sinistre
- Annee Survenance
- Annee Developpement (annee calendaire)
- Garantie
- NATURE_SINISTRE (CORPOREL / MATERIEL)
- usage
- Sinistres Payees
- Provisions pour SAP
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

from autoreserve.config import RAW_DIR

logger = logging.getLogger(__name__)


FICHIER_SINISTRES = "Base Sinistre auto 2015-2024.xlsx"

COLONNES_MAPPING = {
    "Numéro sinistre": "NUM_SINISTRE",
    "Numero sinistre": "NUM_SINISTRE",
    "Année Survenance": "ANNEE_SURVENANCE",
    "Année\nSurvenance": "ANNEE_SURVENANCE",
    "Annee Survenance": "ANNEE_SURVENANCE",
    "Année Developpement": "ANNEE_DEVELOPPEMENT",
    "Année\nDeveloppement": "ANNEE_DEVELOPPEMENT",
    "Annee Developpement": "ANNEE_DEVELOPPEMENT",
    "Année Développement": "ANNEE_DEVELOPPEMENT",
    "Garantie": "GARANTIE",
    "NATURE_SINISTRE": "NATURE_SINISTRE",
    "usage": "USAGE",
    "Usage": "USAGE",
    "Sinistres Payées": "SINISTRE_PAYE",
    "Sinistres Payees": "SINISTRE_PAYE",
    "Sinistres Payés": "SINISTRE_PAYE",
    "Provisions pour SAP": "SAP",
    "Provisions\npour SAP": "SAP",
    "Provision SAP": "SAP",
}

COLONNES_OBLIGATOIRES = [
    "NUM_SINISTRE",
    "ANNEE_SURVENANCE",
    "ANNEE_DEVELOPPEMENT",
    "NATURE_SINISTRE",
    "SINISTRE_PAYE",
    "SAP",
]


def _normalize_col_name(col: str) -> str:
    if not isinstance(col, str):
        return col
    cleaned = re.sub(r"\s+", " ", col.strip())
    if cleaned in COLONNES_MAPPING:
        return COLONNES_MAPPING[cleaned]
    for k, v in COLONNES_MAPPING.items():
        if re.sub(r"\s+", " ", k.strip()).lower() == cleaned.lower():
            return v
    return cleaned


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_normalize_col_name(c) for c in df.columns]
    return df


def _to_numeric_safe(series: pd.Series) -> pd.Series:
    def _parse(v):
        if pd.isna(v):
            return pd.NA
        if isinstance(v, str):
            stripped = v.strip().replace(" ", "").replace("\xa0", "")
            if stripped in ("", "NULL", "null", "None", "-"):
                return pd.NA
            stripped = stripped.replace(",", ".")
            return stripped
        return v

    cleaned = series.apply(_parse)
    return pd.to_numeric(cleaned, errors="coerce")


def _normalize_nature(series: pd.Series) -> pd.Series:
    def _clean(v):
        if pd.isna(v):
            return pd.NA
        s = str(v).strip().upper()
        s = s.replace("É", "E").replace("È", "E").replace("Ê", "E")
        if s in ("CORPOREL", "CORPORELS", "CORP"):
            return "CORPOREL"
        if s in ("MATERIEL", "MATERIELS", "MAT"):
            return "MATERIEL"
        return s

    return series.apply(_clean).astype("string")


def _add_dev_index(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    surv = pd.to_numeric(df["ANNEE_SURVENANCE"], errors="coerce")
    dev = pd.to_numeric(df["ANNEE_DEVELOPPEMENT"], errors="coerce")
    df["INDICE_DEV"] = (dev - surv).astype("Int64")
    return df


def load_sinistres(
    fichier: str | None = None,
    annee_debut: int | None = None,
    annee_fin: int | None = None,
    natures_incluses: list[str] | None = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Charge et normalise la base sinistres.

    Parameters
    ----------
    fichier : nom du fichier Excel dans data/raw/
    annee_debut : filtre ANNEE_SURVENANCE >= annee_debut
    annee_fin : filtre ANNEE_SURVENANCE <= annee_fin
    natures_incluses : liste des natures a garder (ex: ["CORPOREL"])
    """
    if fichier is None:
        fichier = FICHIER_SINISTRES

    fichier_path = RAW_DIR / fichier
    if not fichier_path.exists():
        raise FileNotFoundError(
            f"Fichier sinistres introuvable : {fichier_path}\n"
            f"Placer le fichier dans data/raw/"
        )

    if verbose:
        logger.info(f"Lecture de {fichier}")

    df = pd.read_excel(fichier_path, dtype=object)
    df = df.dropna(how="all")
    if verbose:
        logger.info(f"  -> {len(df):,} lignes lues (avant traitement)")

    df = _normalize_columns(df)

    manquantes = [c for c in COLONNES_OBLIGATOIRES if c not in df.columns]
    if manquantes:
        raise ValueError(
            f"Colonnes obligatoires manquantes : {manquantes}\n"
            f"Colonnes disponibles : {list(df.columns)}"
        )

    df["ANNEE_SURVENANCE"] = pd.to_numeric(df["ANNEE_SURVENANCE"], errors="coerce").astype("Int64")
    df["ANNEE_DEVELOPPEMENT"] = pd.to_numeric(df["ANNEE_DEVELOPPEMENT"], errors="coerce").astype("Int64")
    df["SINISTRE_PAYE"] = _to_numeric_safe(df["SINISTRE_PAYE"])
    df["SAP"] = _to_numeric_safe(df["SAP"])
    df["NATURE_SINISTRE"] = _normalize_nature(df["NATURE_SINISTRE"])
    df["NUM_SINISTRE"] = df["NUM_SINISTRE"].astype("string")

    for c in ["GARANTIE", "USAGE"]:
        if c in df.columns:
            df[c] = df[c].astype("string")

    df = _add_dev_index(df)

    n_before = len(df)
    df = df[df["ANNEE_SURVENANCE"].notna()].copy()
    n_dropped = n_before - len(df)
    if n_dropped > 0 and verbose:
        logger.info(f"  -> {n_dropped:,} lignes ANNEE_SURVENANCE manquante droppees")

    if annee_debut is not None:
        n_before = len(df)
        df = df[df["ANNEE_SURVENANCE"] >= annee_debut].copy()
        if verbose:
            logger.info(f"  -> Filtre annee >= {annee_debut} : {n_before:,} -> {len(df):,}")

    if annee_fin is not None:
        n_before = len(df)
        df = df[df["ANNEE_SURVENANCE"] <= annee_fin].copy()
        if verbose:
            logger.info(f"  -> Filtre annee <= {annee_fin} : {n_before:,} -> {len(df):,}")

    if natures_incluses is not None:
        natures_upper = [n.upper() for n in natures_incluses]
        n_before = len(df)
        df = df[df["NATURE_SINISTRE"].isin(natures_upper)].copy()
        if verbose:
            logger.info(f"  -> Filtre natures {natures_upper} : {n_before:,} -> {len(df):,}")

    ordre = [
        "NUM_SINISTRE",
        "ANNEE_SURVENANCE",
        "ANNEE_DEVELOPPEMENT",
        "INDICE_DEV",
        "NATURE_SINISTRE",
        "GARANTIE",
        "USAGE",
        "SINISTRE_PAYE",
        "SAP",
    ]
    cols_present = [c for c in ordre if c in df.columns]
    cols_autres = [c for c in df.columns if c not in ordre]
    df = df[cols_present + cols_autres]

    if verbose:
        logger.info(f"  OK Base sinistres chargee : {len(df):,} lignes, {len(df.columns)} colonnes")

    return df


def data_quality_report_sinistres(df: pd.DataFrame) -> dict:
    """Rapport de qualite specifique aux sinistres."""
    report = {"n_total": len(df), "issues": {}}

    if "NATURE_SINISTRE" in df.columns:
        nature_counts = df["NATURE_SINISTRE"].value_counts(dropna=False).to_dict()
        report["repartition_nature"] = {str(k): int(v) for k, v in nature_counts.items()}
        report["issues"]["nature_manquante"] = int(df["NATURE_SINISTRE"].isna().sum())

    if "ANNEE_SURVENANCE" in df.columns:
        surv = df["ANNEE_SURVENANCE"].dropna()
        if len(surv) > 0:
            report["annee_survenance_min"] = int(surv.min())
            report["annee_survenance_max"] = int(surv.max())

    if "INDICE_DEV" in df.columns:
        idx = df["INDICE_DEV"].dropna()
        if len(idx) > 0:
            report["indice_dev_min"] = int(idx.min())
            report["indice_dev_max"] = int(idx.max())
            report["issues"]["indice_dev_negatif"] = int((idx < 0).sum())

    for col in ["SINISTRE_PAYE", "SAP"]:
        if col in df.columns:
            v = pd.to_numeric(df[col], errors="coerce")
            report["issues"][f"{col.lower()}_manquant"] = int(v.isna().sum())
            report["issues"][f"{col.lower()}_negatif"] = int((v < 0).sum())

       # NOTE : "Doublons" sur (NUM_SINISTRE, ANNEE_DEV) = plusieurs garanties
    # activees pour un meme sinistre. C'est la structure normale de la base.
    if "NUM_SINISTRE" in df.columns and "ANNEE_DEVELOPPEMENT" in df.columns:
        n_dup = df.duplicated(subset=["NUM_SINISTRE", "ANNEE_DEVELOPPEMENT"]).sum()
        report["lignes_multi_garanties"] = int(n_dup)

    total_issues = sum(v for v in report["issues"].values())
    report["quality_score"] = round(100 * (1 - total_issues / len(df)), 2) if len(df) else 0

    return report