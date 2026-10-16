"""
Loaders des 6 bases sources (Flotte x 3 ans + Individuelle x 3 ans).

Logique metier de traitement des colonnes primes/frais/taxes :

- 2022 : chaque colonne apparait en doublon avec valeurs opposees
         (contre-passation comptable). On garde la valeur POSITIVE.
- 2023 : chaque colonne apparait en doublon avec valeurs identiques.
         On garde la premiere colonne (drop la .1).
- 2024 : suffixe explicite "(Corrige)" pour les valeurs corrigees.
         On utilise UNIQUEMENT les colonnes corrigees pour PPNA.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

from autoreserve.config import BASES_SOURCES, RAW_DIR, COLONNES_OBLIGATOIRES
from autoreserve.ingestion.column_mapping import (
    SCHEMA_UNIFIE_MAPPING,
    apply_coquilles_correction,
    fix_emeute_anomaly_indiv_2022,
    has_corrige_suffix,
    should_drop_column,
    strip_corrige_suffix,
)

logger = logging.getLogger(__name__)


def _read_excel_sheet(fichier: str, onglet: str, header_row: int = 0) -> pd.DataFrame:
    """Lit un onglet Excel depuis data/raw/."""
    fichier_path = RAW_DIR / fichier
    if not fichier_path.exists():
        raise FileNotFoundError(
            f"Fichier source introuvable : {fichier_path}\n"
            f"Placer le fichier dans le dossier data/raw/."
        )

    logger.info(f"Lecture de {fichier} [onglet: {onglet}]")

    df = pd.read_excel(
        fichier_path,
        sheet_name=onglet,
        header=header_row,
        dtype=object,
    )

    df = df.dropna(how="all")
    logger.info(f"  -> {len(df)} lignes lues (avant filtrage totaux)")

    return df


def _normalize_columns(df: pd.DataFrame, base_key: str) -> pd.DataFrame:
    """Applique les normalisations sur les noms de colonnes."""
    cols = list(df.columns)

    # 1. Correction des coquilles
    cols = [apply_coquilles_correction(c) for c in cols]

    # 2. Anomalie EMEUTE x3 (specifique Indiv 2022)
    if base_key == "indiv_2022":
        cols = fix_emeute_anomaly_indiv_2022(cols)

    # 3. Apres correction des coquilles, on peut se retrouver avec
    #    plusieurs colonnes du meme nom (ex: 'D-rec' et 'D_rec' -> 'D_rec' x2).
    #    On suffixe manuellement les doublons post-coquilles en .1, .2, etc.
    #    Ils seront traites ensuite par _handle_duplicate_columns_by_year.
    from collections import Counter
    counts_running: dict[str, int] = {}
    total_counts = Counter(cols)
    disambiguated = []
    for c in cols:
        if total_counts[c] > 1:
            counts_running[c] = counts_running.get(c, 0) + 1
            n = counts_running[c]
            if n == 1:
                disambiguated.append(c)  # 1ere occurrence garde le nom nu
            else:
                disambiguated.append(f"{c}.{n - 1}")  # .1, .2, .3...
        else:
            disambiguated.append(c)
    cols = disambiguated

    # 4. Transformer suffixe (Corrige) en _CORRIGEE (format 2024)
    new_cols = []
    corriges_bases: set[str] = set()

    for c in cols:
        if has_corrige_suffix(c):
            base_name = strip_corrige_suffix(c)
            new_cols.append(f"{base_name}_CORRIGEE")
            corriges_bases.add(base_name)
        else:
            new_cols.append(c)
    cols = new_cols

    cols = [
        f"{c}_EMISE" if c in corriges_bases else c
        for c in cols
    ]

    df = df.copy()
    df.columns = cols

    return df


def _drop_useless_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Supprime les colonnes inutiles pour PPNA."""
    cols_before = len(df.columns)
    cols_to_keep = [c for c in df.columns if not should_drop_column(c)]
    df = df[cols_to_keep]
    logger.info(
        f"  -> {cols_before - len(cols_to_keep)} colonnes droppees "
        f"({cols_before} -> {len(cols_to_keep)})"
    )
    return df


# Colonnes de montants pour lesquelles le doublon 2022/2023 oppose
# emise (1ere colonne) et corrigee (2eme colonne).
MONTANTS_DOUBLON = {"TOTAL_PRIME_NETTE", "FRAIS", "TOTAL_TAXE"}


def _handle_duplicate_columns_by_year(df: pd.DataFrame, annee: int) -> pd.DataFrame:
    """
    Traite les colonnes dupliquees selon la regle metier propre a chaque annee.

    - Montants (prime/frais/taxe) en 2022 et 2023 : le doublon est la paire
      EMISE (1ere colonne) / CORRIGEE (.1, 2eme colonne). On les expose en
      <base>_EMISE / <base>_CORRIGEE pour que la strategie emise/corrigee
      retienne la valeur CORRIGEE (contrats dont la prime a ete corrigee apres
      emission : annulations, contre-passations, ristournes).
    - Autres colonnes dupliquees : simple doublon, on garde la premiere.
    """
    df = df.copy()
    cols_to_drop = []
    rename_map: dict[str, str] = {}

    for col in list(df.columns):
        match = re.match(r"^(.+)\.(\d+)$", col)
        if not match:
            continue

        base_name = match.group(1)
        base_upper = base_name.upper()

        # --- Montants : exposer EMISE / CORRIGEE (la .1 = corrigee) ---
        if base_upper in MONTANTS_DOUBLON:
            if base_name in df.columns:
                rename_map[base_name] = f"{base_upper}_EMISE"
            rename_map[col] = f"{base_upper}_CORRIGEE"
            continue

        # --- Autres doublons : on garde la premiere, on drop la .1 ---
        if base_name not in df.columns:
            rename_map[col] = base_name  # pas de base : on promeut la .1
        else:
            cols_to_drop.append(col)

    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)
    if rename_map:
        df = df.rename(columns=rename_map)
        montants_exposes = sorted({v for v in rename_map.values()
                                   if v.endswith(("_EMISE", "_CORRIGEE"))})
        if montants_exposes:
            logger.info(f"  -> Annee {annee} : montants exposes emise/corrigee "
                        f"({len(montants_exposes)} colonnes) : {montants_exposes}")

    return df


def _keep_only_corrigees_2024(df: pd.DataFrame) -> pd.DataFrame:
    """
    En 2024, on utilise UNIQUEMENT les colonnes corrigees.
    On drop les _EMISE et on renomme les _CORRIGEE vers les noms canoniques.
    """
    df = df.copy()
    cols_to_drop = []
    rename_map = {}

    for col in list(df.columns):
        if col.endswith("_EMISE"):
            cols_to_drop.append(col)
        elif col.endswith("_CORRIGEE"):
            base_name = col[: -len("_CORRIGEE")]
            rename_map[col] = base_name

    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)
        logger.info(f"  -> Annee 2024 : {len(cols_to_drop)} colonnes _EMISE droppees (on garde uniquement les corrigees)")

    if rename_map:
        df = df.rename(columns=rename_map)
        logger.info(f"  -> Annee 2024 : {len(rename_map)} colonnes _CORRIGEE renommees vers noms canoniques")

    return df


def _apply_unified_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Renomme les colonnes vers le schema unifie canonique."""
    rename_map = {
        c: SCHEMA_UNIFIE_MAPPING[c]
        for c in df.columns
        if c in SCHEMA_UNIFIE_MAPPING
    }
    return df.rename(columns=rename_map)


def _add_metadata(df: pd.DataFrame, base_key: str) -> pd.DataFrame:
    """Ajoute les colonnes de tracabilite."""
    meta = BASES_SOURCES[base_key]
    df = df.copy()
    df["ANNEE_EXERCICE"] = meta["annee"]
    df["TYPE_BASE"] = meta["type_base"]
    df["SOURCE_ONGLET"] = meta["onglet"]
    df["SOURCE_FICHIER"] = meta["fichier"]
    return df


def _check_required_columns(df: pd.DataFrame, base_key: str) -> None:
    """
    Verifie que les colonnes obligatoires sont presentes.
    Pour les montants, la forme emise/corrigee (<col>_EMISE / <col>_CORRIGEE)
    satisfait l'exigence : le canonique sera resolu a l'unification.
    """
    def _present(col: str) -> bool:
        return col in df.columns or f"{col}_EMISE" in df.columns or f"{col}_CORRIGEE" in df.columns

    manquantes = [c for c in COLONNES_OBLIGATOIRES if not _present(c)]
    if manquantes:
        raise ValueError(
            f"Base {base_key} : colonnes obligatoires manquantes apres "
            f"normalisation : {manquantes}\n"
            f"Colonnes disponibles : {list(df.columns)}"
        )


def _filter_total_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Retire les lignes de totaux Excel."""
    if "NUM_CONTRAT" not in df.columns:
        return df

    n_before = len(df)
    mask_valid = df["NUM_CONTRAT"].notna() & (
        df["NUM_CONTRAT"].astype(str).str.strip() != ""
    )
    df = df[mask_valid].copy()
    n_removed = n_before - len(df)
    if n_removed > 0:
        logger.info(f"  -> {n_removed} ligne(s) de totaux/vides filtree(s)")
    return df


def load_base(base_key: str) -> pd.DataFrame:
    """Charge et normalise une base par sa cle."""
    if base_key not in BASES_SOURCES:
        raise KeyError(
            f"Base inconnue : '{base_key}'. "
            f"Bases disponibles : {list(BASES_SOURCES.keys())}"
        )

    meta = BASES_SOURCES[base_key]
    annee = meta["annee"]

    logger.info(f"=== Chargement de {base_key} ===")

    df = _read_excel_sheet(
        fichier=meta["fichier"],
        onglet=meta["onglet"],
        header_row=meta["header_row"],
    )

    df = _normalize_columns(df, base_key)
    df = _drop_useless_columns(df)

    # Traitement metier des doublons selon l'annee
    if annee in (2022, 2023):
        df = _handle_duplicate_columns_by_year(df, annee)

    if annee == 2024:
        df = _keep_only_corrigees_2024(df)

    df = _apply_unified_schema(df)
    df = _add_metadata(df, base_key)
    df = _filter_total_rows(df)
    _check_required_columns(df, base_key)

    logger.info(f"  OK {base_key} chargee : {len(df)} lignes, {len(df.columns)} colonnes")

    return df


def load_all_bases() -> dict[str, pd.DataFrame]:
    """Charge les 6 bases et renvoie un dictionnaire."""
    bases = {}
    for base_key in BASES_SOURCES:
        try:
            bases[base_key] = load_base(base_key)
        except FileNotFoundError as e:
            logger.warning(f"[!] {base_key} : fichier absent -> base ignoree")
            logger.warning(str(e))
    return bases