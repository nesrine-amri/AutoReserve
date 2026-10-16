"""
Normalisation des noms de colonnes des 6 bases sources.

Traite :
- Trim des espaces parasites (' num_quittance ' → 'num_quittance')
- Coquilles orthographiques (D-rec → D_rec, Carglass → carglass)
- Doublons dus au format Excel (RC | RC → RC_EMISE | RC_CORRIGEE)
- Suffixe " (Corrigé)" utilisé en 2024 → suffixe unifié "_CORRIGEE"
- Anomalie EMEUTE×3 en Indiv 2022 (la 3ème = VOL_RADIO_CASSETTE)
- Colonnes fantômes "(Aucun nom de colonne)" → à ignorer
"""

from __future__ import annotations

import re
import unicodedata


# ============================================================
# COQUILLES ORTHOGRAPHIQUES CONNUES
# ============================================================

CORRECTIONS_COQUILLES: dict[str, str] = {
    "D-rec": "D_rec",
    "Carglass": "carglass",
    "carglass ": "carglass",
    "incendie ": "incendie",
    " num_quittance ": "num_quittance",
    "num_quittance ": "num_quittance",
    " num_quittance": "num_quittance",
    "EMEUTE_MOUVEMENT_POPULAIRE  (Corrigé)": "EMEUTE_MOUVEMENT_POPULAIRE (Corrigé)",
    "VOL_RADIO_CASSETTE  (Corrigé)": "VOL_RADIO_CASSETTE (Corrigé)",
    "d": "_A_IGNORER_ANNEE_PROD_LIBRE",
    "Annee prod": "_A_IGNORER_ANNEE_PROD_LIBRE",
    "Annee prod ": "_A_IGNORER_ANNEE_PROD_LIBRE",
    "Exercice comptable": "_A_IGNORER_EXERCICE_COMPTABLE",
    "Exercice comptable ": "_A_IGNORER_EXERCICE_COMPTABLE",
}


# ============================================================
# COLONNES À DROP SYSTÉMATIQUEMENT
# ============================================================

COLONNES_A_DROP_TOUJOURS: set[str] = {
    # Assuré
    "Date_Naissance",
    "sexe",
    "rue",
    "ville",
    "CODE_POSTAL",
    "CODE_INTERMEDIAIRE",
    "INTERMEDIAIRE",
    "PERSONNE_PHYSIQUE",
    "PERSONNE_MORALE",
    # Véhicule
    "usage",
    "class",
    "IMMATRICULATION_VEHICULE",
    "NUM_RISQUE",
    "PREMIERE_MISE_CIRCULATION",
    "MARQUE_VEHICULE",
    "VALEUR_CATALOGUE",
    "VALEUR_VENALE",
    "PUISSANCE",
    "Leasing",
    # Capitaux (non utilisés pour PPNA globale)
    "capitale_inc",
    "capitale_vol",
    "capitale_DV",
    "franch_DV",
    "capitale_Dcol",
    "capitale_DCol",
    # Emission (métadonnées quittance)
    "Emission",
    "DATE_EMISSION",
    "DATE_ENCAISSEMENT",
    # Test technique 2023
    "test_code_motif",
    # Colonnes à ignorer marquées lors des corrections
    "_A_IGNORER_ANNEE_PROD_LIBRE",
    "_A_IGNORER_EXERCICE_COMPTABLE",
    # Colonnes d'essais PPNA en 2024 (à ignorer, on recalcule)
    "Durée totale",
    "Durée totale ",
    "Jours Restants",
    "Jours Restants ",
    "Jours Restants  ",
    "PPNA prime nette",
    "PPNA prime nette ",
    "PPNA frais",
    "PPNA frais ",
    "Prime emise reelle",
    "Prime Emise",
    "Prime emise reelle ",
    # Colonnes zone essais en fin de Flotte 2024
    "Numéro de Contrat",
    "Numéro de Contrat ",
    "Date du",
    "Date du ",
    "Date au",
    "Date au ",
    "Prime nette",
    "Prime nette ",
    "frais",
    "frais ",
}


# ============================================================
# GARANTIES (POUR GESTION DES DOUBLONS ÉMISE/CORRIGÉE)
# ============================================================

GARANTIES = [
    "RC",
    "D_rec",
    "incendie",
    "vol",
    "DOMMAGES_AU_VEHICULE",
    "DOMMAGES_ET_COLLISION",
    "BRIS_DE_GLACES",
    "PTA",
    "INDIVIDUELLE_ACCIDENT",
    "CATASTROPHE_NATURELLE",
    "EMEUTE_MOUVEMENT_POPULAIRE",
    "VOL_RADIO_CASSETTE",
    "carglass",
    "Assistanceet_carglass",
]

AGREGATS = [
    "TOTAL_TAXE",
    "FRAIS",
    "TOTAL_PRIME_NETTE",
    "total_prime_nette",
]


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def _strip_accents(text: str) -> str:
    """Retire les accents d'une chaîne (Corrigé → Corrige)."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def is_unnamed_column(col_name: str) -> bool:
    """Détecte les colonnes 'Unnamed: X' (Pandas) ou '(Aucun nom de colonne)'."""
    if not isinstance(col_name, str):
        return True
    stripped = col_name.strip()
    if stripped == "":
        return True
    if stripped.startswith("Unnamed:"):
        return True
    if "Aucun nom de colonne" in stripped:
        return True
    return False


def has_corrige_suffix(col_name: str) -> bool:
    """Vérifie si une colonne porte le suffixe '(Corrigé)' (format 2024)."""
    if not isinstance(col_name, str):
        return False
    normalized = _strip_accents(col_name).lower()
    return "(corrige)" in normalized


def strip_corrige_suffix(col_name: str) -> str:
    """Retire le suffixe '(Corrigé)' pour retrouver le nom de base."""
    pattern = re.compile(r"\s*\(corrig[eé]\)\s*$", re.IGNORECASE)
    return pattern.sub("", col_name).strip()


def apply_coquilles_correction(col_name: str) -> str:
    """Applique la correction des coquilles connues + trim des espaces."""
    if not isinstance(col_name, str):
        return col_name
    if col_name in CORRECTIONS_COQUILLES:
        return CORRECTIONS_COQUILLES[col_name]
    return col_name.strip()


def should_drop_column(col_name: str) -> bool:
    """Détermine si une colonne doit être supprimée systématiquement."""
    if is_unnamed_column(col_name):
        return True
    normalized = col_name.strip() if isinstance(col_name, str) else col_name
    return normalized in COLONNES_A_DROP_TOUJOURS


# ============================================================
# GESTION DES DOUBLONS POSITION-BASED (2022/2023)
# ============================================================

def disambiguate_duplicate_columns(columns: list[str]) -> list[str]:
    """
    Renomme les doublons en suffixant _EMISE / _CORRIGEE selon la position.
    En 2022/2023, la 1ère occurrence = émise, la 2ème = corrigée.
    """
    result = []
    seen_count: dict[str, int] = {}
    total_count: dict[str, int] = {}

    for col in columns:
        total_count[col] = total_count.get(col, 0) + 1

    for col in columns:
        if total_count[col] > 1:
            seen_count[col] = seen_count.get(col, 0) + 1
            if seen_count[col] == 1:
                result.append(f"{col}_EMISE")
            elif seen_count[col] == 2:
                result.append(f"{col}_CORRIGEE")
            else:
                result.append(f"{col}_EXTRA_{seen_count[col]}")
        else:
            result.append(col)

    return result


def fix_emeute_anomaly_indiv_2022(columns: list[str]) -> list[str]:
    """
    Corrige l'anomalie 'EMEUTE_MOUVEMENT_POPULAIRE × 3' en Indiv 2022.
    La 3ème occurrence est en réalité VOL_RADIO_CASSETTE mal étiqueté.
    """
    result = list(columns)
    emeute_indices = [
        i for i, col in enumerate(result)
        if col == "EMEUTE_MOUVEMENT_POPULAIRE"
    ]

    if len(emeute_indices) < 3:
        return result

    third_emeute_idx = emeute_indices[2]

    if third_emeute_idx > 0 and result[third_emeute_idx - 1] == "VOL_RADIO_CASSETTE":
        result[third_emeute_idx] = "VOL_RADIO_CASSETTE"

    return result


# ============================================================
# MAPPING VERS SCHÉMA UNIFIÉ FINAL
# ============================================================

SCHEMA_UNIFIE_MAPPING: dict[str, str] = {
    # Identifiants
    "NUM_CONTRAT": "NUM_CONTRAT",
    "num_quittance": "NUM_QUITTANCE",
    # Dates
    "EFFET_CONTRAT": "EFFET_CONTRAT",
    "VALIDITE_DU": "VALIDITE_DU",
    "VALIDITE_AU": "VALIDITE_AU",
    "PROCHAIN_TERME": "PROCHAIN_TERME",
    "DATE_EXPIRATION": "DATE_EXPIRATION",
    # Nature contrat
    "CODE_NATURE_CONTRAT": "CODE_NATURE_CONTRAT",
    "ANNEE_EXERCICE_PROD": "ANNEE_EXERCICE_PROD",
    # Primes (variantes minuscules/majuscules unifiées)
    "TOTAL_PRIME_NETTE": "TOTAL_PRIME_NETTE",
    "total_prime_nette": "TOTAL_PRIME_NETTE",
    "TOTAL_PRIME_NETTE_EMISE": "TOTAL_PRIME_NETTE_EMISE",
    "total_prime_nette_EMISE": "TOTAL_PRIME_NETTE_EMISE",
    "TOTAL_PRIME_NETTE_CORRIGEE": "TOTAL_PRIME_NETTE_CORRIGEE",
    "total_prime_nette_CORRIGEE": "TOTAL_PRIME_NETTE_CORRIGEE",
    "FRAIS": "FRAIS",
    "FRAIS_EMISE": "FRAIS_EMISE",
    "FRAIS_CORRIGEE": "FRAIS_CORRIGEE",
    "TOTAL_TAXE": "TOTAL_TAXE",
    "TOTAL_TAXE_EMISE": "TOTAL_TAXE_EMISE",
    "TOTAL_TAXE_CORRIGEE": "TOTAL_TAXE_CORRIGEE",
    # Statuts
    "code_motif_retour": "CODE_MOTIF_RETOUR",
    "CODE_VALIDATION_RETOUR": "CODE_VALIDATION_RETOUR",
    "retour_annee": "RETOUR_ANNEE",
    "valid_retour_annee": "VALID_RETOUR_ANNEE",
    "retour_2022": "RETOUR_ANNEE",
    "validation_2022": "VALID_RETOUR_ANNEE",
}