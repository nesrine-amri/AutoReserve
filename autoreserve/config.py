"""
Configuration centrale du projet AutoReserve.

Contient :
- Chemins vers les données sources et sorties
- Constantes actuarielles (date de clôture, exercices traités)
- Métadonnées des 6 bases sources (fichier, onglet, année, type)
"""

from pathlib import Path
from datetime import date
from typing import Literal, TypedDict

# ============================================================
# CHEMINS DU PROJET
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = DATA_DIR / "outputs"

# S'assurer que les dossiers existent
for _dir in (PROCESSED_DIR, OUTPUTS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


# ============================================================
# CONSTANTES ACTUARIELLES
# ============================================================

# Date de clôture de référence pour le calcul PPNA
# (au 31 décembre de chaque exercice)
CLOTURE_2022 = date(2022, 12, 31)
CLOTURE_2023 = date(2023, 12, 31)
CLOTURE_2024 = date(2024, 12, 31)

CLOTURES = {
    2022: CLOTURE_2022,
    2023: CLOTURE_2023,
    2024: CLOTURE_2024,
}

EXERCICES_TRAITES = [2022, 2023, 2024]

# Plage des triangles de sinistres pour les methodes (CL, ecretement, CM,
# bootstrap). La base sinistres couvre 2015-2024 ; on retient 2020-2024 comme
# periode de travail (triangle 5x5, donnees recentes representatives).
# Le loss ratio BF reste calibre sur les annees a prime reelle (2022-2023).
ANNEE_DEBUT_SINISTRES = 2020


# ============================================================
# MÉTADONNÉES DES 6 BASES SOURCES
# ============================================================

TypeBase = Literal["FLOTTE", "INDIVIDUELLE"]


class BaseSourceMeta(TypedDict):
    """Métadonnées d'une base source Excel."""
    fichier: str          # nom du fichier .xlsx dans data/raw/
    onglet: str           # nom de l'onglet Excel
    annee: int            # exercice de l'année
    type_base: TypeBase   # FLOTTE ou INDIVIDUELLE
    header_row: int       # index Pandas de la ligne d'en-tête (0-based)


# Catalogue exhaustif des 6 bases identifiées lors de la phase d'analyse.
# Ces métadonnées pilotent le chargement dans loaders.py.
BASES_SOURCES: dict[str, BaseSourceMeta] = {
    "indiv_2022": {
        "fichier": "Chiffre d'affaires auto 2022.xlsx",
        "onglet": "Base ind 2022",
        "annee": 2022,
        "type_base": "INDIVIDUELLE",
        "header_row": 0,
    },
    "flotte_2022": {
        "fichier": "Chiffre d'affaires auto 2022.xlsx",
        "onglet": "Base flotte 2022",
        "annee": 2022,
        "type_base": "FLOTTE",
        "header_row": 0,
    },
    "indiv_2023": {
        "fichier": "Chiffre d'affaires auto 2023.xlsx",
        "onglet": "Base ind 2023",
        "annee": 2023,
        "type_base": "INDIVIDUELLE",
        "header_row": 0,
    },
    "flotte_2023": {
        "fichier": "Chiffre d'affaires auto 2023.xlsx",
        "onglet": "Base flotte 2023",
        "annee": 2023,
        "type_base": "FLOTTE",
        "header_row": 0,
    },
    "indiv_2024": {
        "fichier": "Chiffre d'affaires auto 2024.xlsx",
        "onglet": "2.1-Base indi",
        "annee": 2024,
        "type_base": "INDIVIDUELLE",
        "header_row": 0,
    },
    "flotte_2024": {
        "fichier": "Chiffre d'affaires auto 2024.xlsx",
        "onglet": "2.2-Base flotte",
        "annee": 2024,
        "type_base": "FLOTTE",
        "header_row": 0,
    },
}


# ============================================================
# COLONNES ESSENTIELLES POUR LE CALCUL PPNA
# ============================================================

# Colonnes qui DOIVENT être présentes dans chaque base après normalisation.
# Si une manque, le loader lève une exception.
COLONNES_OBLIGATOIRES = [
    "NUM_CONTRAT",
    "VALIDITE_DU",
    "VALIDITE_AU",
    "TOTAL_PRIME_NETTE",
    "FRAIS",
]


# ============================================================
# STRATÉGIE ÉMISE / CORRIGÉE
# ============================================================

# Comment choisir entre valeur émise et valeur corrigée pour PPNA.
# "corrigee_sinon_emise" : utilise la corrigée si disponible, sinon l'émise.
# "emise" : utilise systématiquement l'émise (données brutes).
# "corrigee" : force la corrigée (erreur si absente).
STRATEGIE_VALEUR: Literal["corrigee_sinon_emise", "emise", "corrigee"] = (
    "corrigee_sinon_emise"
)


# ============================================================
# TRAITEMENT DES CONTRE-PASSATIONS (ANNULATIONS)
# ============================================================

# Si True, les lignes a prime NEGATIVE (annulations / contre-passations) sont
# exclues du calcul PPNA -> base "primes emises brutes", alignee sur la
# definition du Compte Technique de reference. Les annulations restent
# tracables dans la base unifiee.
EXCLURE_CONTRE_PASSATIONS: bool = True


# ============================================================
# VALEURS DE REFERENCE DU COMPTE TECHNIQUE — 2024
# ============================================================
#
# NOTE (depot public) : les valeurs ci-dessous sont des EXEMPLES ILLUSTRATIFS,
# et NON les chiffres reels de l'assureur (confidentiels). Pour reproduire les
# resultats, renseignez vos propres valeurs (ou chargez-les depuis un fichier
# local non versionne / des variables d'environnement).
PRIMES_EMISES_2024_CT = 40_000_000   # exemple
PPNA_2024_CT = 18_000_000            # exemple
PRIME_ACQUISE_2024_CT = PRIMES_EMISES_2024_CT - PPNA_2024_CT

# Prime acquise a utiliser pour l'a priori du Bornhuetter-Ferguson :
# on remplace la valeur CALCULEE de 2024 par la valeur officielle de l'encadrant.
# (Les autres annees restent sur nos valeurs calculees.)
PRIME_ACQUISE_ENCADRANT: dict[int, float] = {2024: PRIME_ACQUISE_2024_CT}
