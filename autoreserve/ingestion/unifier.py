"""
Unification des 6 bases sources en une seule base consolidee.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Literal

import pandas as pd

from autoreserve.config import (
    PROCESSED_DIR,
    STRATEGIE_VALEUR,
    BASES_SOURCES,
)
from autoreserve.ingestion.loaders import load_all_bases

logger = logging.getLogger(__name__)


# ============================================================
# COLONNES MONTANTS (EMISE / CORRIGEE)
# ============================================================

COLONNES_MONTANTS = ["TOTAL_PRIME_NETTE", "FRAIS", "TOTAL_TAXE"]


def _resolve_value(
    df: pd.DataFrame,
    col_base: str,
    strategy: Literal["corrigee_sinon_emise", "emise", "corrigee"],
) -> pd.Series:
    """
    Resout la valeur finale d'une colonne selon la strategie.
    Fait le fallback ligne par ligne apres conversion numerique.
    """
    col_emise = f"{col_base}_EMISE"
    col_corrigee = f"{col_base}_CORRIGEE"

    has_emise = col_emise in df.columns
    has_corrigee = col_corrigee in df.columns
    has_base = col_base in df.columns

    if has_base and not has_emise and not has_corrigee:
        return pd.to_numeric(df[col_base], errors="coerce")

    def _num(series_name):
        return pd.to_numeric(df[series_name], errors="coerce")

    if strategy == "emise":
        if has_emise:
            return _num(col_emise)
        if has_base:
            return _num(col_base)
        return _num(col_corrigee) if has_corrigee else pd.Series(pd.NA, index=df.index)

    if strategy == "corrigee":
        if has_corrigee:
            return _num(col_corrigee)
        raise ValueError(f"Strategie 'corrigee' demandee mais {col_corrigee} absent")

    if strategy == "corrigee_sinon_emise":
        # Priorite : corrigee > emise > base (fallback ligne a ligne).
        # Le fallback base est indispensable car certaines sources (2024)
        # fournissent deja le canonique resolu, sans suffixe emise/corrigee.
        parts = []
        if has_corrigee:
            parts.append(_num(col_corrigee))
        if has_emise:
            parts.append(_num(col_emise))
        if has_base:
            parts.append(_num(col_base))
        if not parts:
            return pd.Series(pd.NA, index=df.index)
        result = parts[0]
        for p in parts[1:]:
            result = result.combine_first(p)
        return result

    raise ValueError(f"Strategie inconnue : {strategy}")


def _apply_valeur_strategy(
    df: pd.DataFrame,
    strategy: Literal["corrigee_sinon_emise", "emise", "corrigee"],
) -> pd.DataFrame:
    """Cree les colonnes finales TOTAL_PRIME_NETTE, FRAIS, TOTAL_TAXE."""
    df = df.copy()
    for col_base in COLONNES_MONTANTS:
        df[col_base] = _resolve_value(df, col_base, strategy)
        col_emise = f"{col_base}_EMISE"
        col_corrigee = f"{col_base}_CORRIGEE"
        # Tracabilite ligne a ligne, coherente avec la priorite corrigee>emise>base
        source = pd.Series("BASE", index=df.index)
        if col_emise in df.columns:
            source = source.mask(pd.to_numeric(df[col_emise], errors="coerce").notna(), "EMISE")
        if col_corrigee in df.columns:
            source = source.mask(pd.to_numeric(df[col_corrigee], errors="coerce").notna(), "CORRIGEE")
        df[f"{col_base}_SOURCE"] = source
    return df


# ============================================================
# CONVERSION DES TYPES
# ============================================================

COLONNES_DATES = [
    "EFFET_CONTRAT",
    "VALIDITE_DU",
    "VALIDITE_AU",
    "PROCHAIN_TERME",
    "DATE_EXPIRATION",
]


def _to_datetime_safe(series: pd.Series) -> pd.Series:
    """Convertit une serie en datetime en gerant les strings 'NULL'."""
    def _parse(v):
        if pd.isna(v):
            return pd.NaT
        if isinstance(v, str):
            stripped = v.strip()
            if stripped in ("", "NULL", "null", "None"):
                return pd.NaT
        return v

    cleaned = series.apply(_parse)
    return pd.to_datetime(cleaned, errors="coerce", dayfirst=True)


def _to_numeric_safe(series: pd.Series) -> pd.Series:
    """Convertit en numerique en gerant les strings 'NULL' et virgules FR."""
    def _parse(v):
        if pd.isna(v):
            return pd.NA
        if isinstance(v, str):
            stripped = v.strip().replace(" ", "")
            if stripped in ("", "NULL", "null", "None"):
                return pd.NA
            stripped = stripped.replace(",", ".")
            return stripped
        return v

    cleaned = series.apply(_parse)
    return pd.to_numeric(cleaned, errors="coerce")


def _cast_types(df: pd.DataFrame) -> pd.DataFrame:
    """Convertit dates et numeriques dans les bons types."""
    df = df.copy()

    # 1. Dates
    for col in COLONNES_DATES:
        if col in df.columns:
            df[col] = _to_datetime_safe(df[col])

    # 2. Numeriques (montants + toutes variantes)
    cols_numeriques_dispo = [c for c in df.columns if any(
        base in c.upper() for base in ["PRIME_NETTE", "FRAIS", "TAXE"]
    )]
    for col in cols_numeriques_dispo:
        if col.endswith("_SOURCE"):
            continue
        df[col] = _to_numeric_safe(df[col])

    # 3. Metadonnees : ANNEE_EXERCICE en entier
    if "ANNEE_EXERCICE" in df.columns:
        df["ANNEE_EXERCICE"] = pd.to_numeric(
            df["ANNEE_EXERCICE"], errors="coerce"
        ).astype("Int64")

    # 4. Tout le reste en string (compat Parquet)
    colonnes_deja_typees = (
        set(COLONNES_DATES)
        | set(cols_numeriques_dispo)
        | {"ANNEE_EXERCICE"}
    )
    for col in df.columns:
        if col in colonnes_deja_typees:
            continue
        df[col] = df[col].astype("string")

    return df


# ============================================================
# FUSION DES COLONNES DOUBLONNEES
# ============================================================

def _merge_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fusionne les colonnes en doublon (nommees .1, .2 par Pandas) et
    les colonnes qui ne different que par la casse (ex : total_prime_nette
    et TOTAL_PRIME_NETTE).
    """
    df = df.copy()

    # 1. Fusion des colonnes suffixees .1, .2, etc.
    duplicated = {}
    for col in df.columns:
        match = re.match(r"^(.+)\.(\d+)$", col)
        if match:
            base_name = match.group(1)
            duplicated.setdefault(base_name, []).append(col)

    for base_name, dup_cols in duplicated.items():
        if base_name not in df.columns:
            df[base_name] = df[dup_cols[0]]
            for c in dup_cols[1:]:
                df[base_name] = df[base_name].combine_first(df[c])
        else:
            for c in dup_cols:
                df[base_name] = df[base_name].combine_first(df[c])
        df = df.drop(columns=dup_cols)
        logger.info(f"  -> Fusion doublons : {base_name} <- {dup_cols}")

    # 2. Fusion des colonnes qui ne different que par la casse
    seen_lower = {}
    to_merge = {}
    for col in list(df.columns):
        low = col.lower()
        if low in seen_lower:
            original = seen_lower[low]
            to_merge.setdefault(original, []).append(col)
        else:
            seen_lower[low] = col

    for original, dups in to_merge.items():
        for c in dups:
            df[original] = df[original].combine_first(df[c])
        df = df.drop(columns=dups)
        logger.info(f"  -> Fusion casse : {original} <- {dups}")

    return df


# ============================================================
# CONSOLIDATION
# ============================================================

def build_unified_base(
    strategy: Literal["corrigee_sinon_emise", "emise", "corrigee"] | None = None,
    save_parquet: bool = True,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Construit la base unifiee a partir des 6 sources."""
    if strategy is None:
        strategy = STRATEGIE_VALEUR

    logger.info("=" * 60)
    logger.info("Construction de la base unifiee")
    logger.info(f"Strategie de valeur : {strategy}")
    logger.info("=" * 60)

    # 1. Charger les 6 bases
    bases = load_all_bases()

    if not bases:
        raise RuntimeError(
            "Aucune base n'a pu etre chargee. "
            f"Verifier que les fichiers sont bien dans {BASES_SOURCES}"
        )

    logger.info(f"\n{len(bases)}/{len(BASES_SOURCES)} bases chargees avec succes")

    # 2. Concatener
    df_unified = pd.concat(list(bases.values()), ignore_index=True, sort=False)
    logger.info(
        f"\nBase unifiee brute : {len(df_unified)} lignes, "
        f"{len(df_unified.columns)} colonnes"
    )

    # 3. Fusion des doublons post-concat (avant d'appliquer la strategie)
    df_unified = _merge_duplicate_columns(df_unified)

    # 4. Appliquer la strategie emise/corrigee
    df_unified = _apply_valeur_strategy(df_unified, strategy)

    # 5. Cast des types
    df_unified = _cast_types(df_unified)

    # 6. Ordonner les colonnes
    df_unified = _order_columns(df_unified)

    # 7. Sauvegarde
    if save_parquet:
        if output_path is None:
            output_path = PROCESSED_DIR / "base_unifiee.parquet"
        df_unified.to_parquet(output_path, index=False)
        logger.info(f"\nOK Base unifiee sauvegardee : {output_path}")

    # 8. Resume
    _log_summary(df_unified)

    return df_unified


def _order_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ordonne les colonnes dans un ordre logique."""
    ordre_prioritaire = [
        "ANNEE_EXERCICE",
        "TYPE_BASE",
        "SOURCE_FICHIER",
        "SOURCE_ONGLET",
        "NUM_CONTRAT",
        "NUM_QUITTANCE",
        "EFFET_CONTRAT",
        "VALIDITE_DU",
        "VALIDITE_AU",
        "PROCHAIN_TERME",
        "DATE_EXPIRATION",
        "CODE_NATURE_CONTRAT",
        "ANNEE_EXERCICE_PROD",
        "TOTAL_PRIME_NETTE",
        "FRAIS",
        "TOTAL_TAXE",
        "TOTAL_PRIME_NETTE_SOURCE",
        "FRAIS_SOURCE",
        "TOTAL_TAXE_SOURCE",
        "TOTAL_PRIME_NETTE_EMISE",
        "TOTAL_PRIME_NETTE_CORRIGEE",
        "FRAIS_EMISE",
        "FRAIS_CORRIGEE",
        "TOTAL_TAXE_EMISE",
        "TOTAL_TAXE_CORRIGEE",
        "CODE_MOTIF_RETOUR",
        "CODE_VALIDATION_RETOUR",
        "RETOUR_ANNEE",
        "VALID_RETOUR_ANNEE",
    ]

    cols_present = [c for c in ordre_prioritaire if c in df.columns]
    cols_autres = [c for c in df.columns if c not in ordre_prioritaire]
    return df[cols_present + sorted(cols_autres)]


def _log_summary(df: pd.DataFrame) -> None:
    """Affiche un resume du contenu de la base unifiee."""
    logger.info("\n" + "=" * 60)
    logger.info("RESUME DE LA BASE UNIFIEE")
    logger.info("=" * 60)
    logger.info(f"Lignes totales     : {len(df):,}")
    logger.info(f"Colonnes           : {len(df.columns)}")
    logger.info("\nRepartition par exercice x type :")

    if "ANNEE_EXERCICE" in df.columns and "TYPE_BASE" in df.columns:
        pivot = df.groupby(["ANNEE_EXERCICE", "TYPE_BASE"]).size().unstack(fill_value=0)
        for line in str(pivot).split("\n"):
            logger.info(f"  {line}")

    if "TOTAL_PRIME_NETTE" in df.columns:
        total = pd.to_numeric(df["TOTAL_PRIME_NETTE"], errors="coerce").sum()
        logger.info(f"\nSomme TOTAL_PRIME_NETTE : {total:,.2f}")