"""
Utilitaires de calcul temporel pour les provisions actuarielles.

Fonctions cles :
- compute_duree_jours     : nombre de jours entre 2 dates (inclusif)
- compute_jours_restants  : jours restants apres une date de cloture
- compute_prorata         : coefficient prorata temporis pour PPNA

Convention de calcul actuarielle standard :
- Duree totale du contrat = (VALIDITE_AU - VALIDITE_DU) + 1 jour
  (les 2 bornes sont inclusives : un contrat du 01/01 au 31/12 fait 365 jours)
- Jours restants apres cloture = (VALIDITE_AU - date_cloture) jours
  (la date de cloture est deja "consommee", donc non incluse)
- Prorata = jours_restants / duree_totale
"""

from __future__ import annotations

from datetime import date
from typing import Union

import numpy as np
import pandas as pd


DateLike = Union[date, pd.Timestamp, str]


def _to_datetime(d: DateLike) -> pd.Timestamp:
    """Convertit une date scalaire en Timestamp Pandas."""
    return pd.Timestamp(d)


def compute_duree_jours(
    validite_du: pd.Series,
    validite_au: pd.Series,
) -> pd.Series:
    """
    Calcule la duree totale du contrat en jours.

    Convention : les 2 bornes sont inclusives.
    Un contrat du 01/01/2024 au 31/12/2024 fait 366 jours (annee bissextile).
    Un contrat du 01/01/2024 au 31/12/2023 fait 0 jours (invalide).

    Parameters
    ----------
    validite_du : pd.Series de dates de debut de validite
    validite_au : pd.Series de dates de fin de validite

    Returns
    -------
    pd.Series : duree en jours (Int64, peut contenir <NA>)

    Exemples
    --------
    >>> du = pd.Series([pd.Timestamp("2024-01-01")])
    >>> au = pd.Series([pd.Timestamp("2024-12-31")])
    >>> compute_duree_jours(du, au).iloc[0]
    366
    """
    du = pd.to_datetime(validite_du, errors="coerce")
    au = pd.to_datetime(validite_au, errors="coerce")
    duree = (au - du).dt.days + 1
    # Convertir en Int64 nullable pour gerer proprement les NaN
    return duree.astype("Int64")


def compute_jours_restants(
    validite_au: pd.Series,
    date_cloture: DateLike,
    validite_du: pd.Series | None = None,
) -> pd.Series:
    """
    Calcule les jours restants apres la date de cloture.

    Trois cas actuariels :
    1. VALIDITE_AU <= date_cloture   : contrat eteint  -> 0 jours restants
    2. VALIDITE_DU > date_cloture    : contrat non commence -> duree totale
                                        (toute la prime est non-acquise)
    3. VALIDITE_DU <= cloture < VALIDITE_AU : contrat en cours -> prorata

    Parameters
    ----------
    validite_au : pd.Series des dates de fin de validite
    date_cloture : date de reference (typiquement 31/12/N)
    validite_du : pd.Series des dates de debut (optionnel, pour cas 2)
                  Si non fournie, cas 2 est ignore.

    Returns
    -------
    pd.Series : jours restants apres cloture (Int64 >= 0)
    """
    cloture = _to_datetime(date_cloture)
    au = pd.to_datetime(validite_au, errors="coerce")

    # Cas general : jours entre cloture et fin de validite
    jours = (au - cloture).dt.days

    # Cap a 0 : si validite_au <= cloture, le contrat est eteint
    jours = jours.clip(lower=0)

    # Cas 2 : contrat non commence a la date de cloture
    if validite_du is not None:
        du = pd.to_datetime(validite_du, errors="coerce")
        duree_totale = (au - du).dt.days + 1
        # Si validite_du > cloture, le contrat n'a pas commence
        # -> jours restants = duree totale (toute la prime est non-acquise)
        mask_non_commence = du > cloture
        jours = jours.where(~mask_non_commence, duree_totale)

    return jours.astype("Int64")


def compute_prorata(
    jours_restants: pd.Series,
    duree_totale: pd.Series,
) -> pd.Series:
    """
    Calcule le coefficient prorata temporis.

    prorata = jours_restants / duree_totale

    Regles de securite :
    - Si duree_totale == 0 ou negative -> prorata = 0 (contrat invalide)
    - Si duree_totale est NaN -> prorata = NaN
    - Prorata clampe entre 0 et 1 (impossible d'avoir plus que 100% non-acquis)

    Parameters
    ----------
    jours_restants : jours restants apres cloture
    duree_totale : duree totale du contrat en jours

    Returns
    -------
    pd.Series : coefficient entre 0.0 et 1.0
    """
    jr = pd.to_numeric(jours_restants, errors="coerce")
    dt_ = pd.to_numeric(duree_totale, errors="coerce")

    # Eviter division par zero
    with np.errstate(divide="ignore", invalid="ignore"):
        prorata = jr / dt_

    # Nettoyer : inf, valeurs negatives, > 1
    prorata = prorata.replace([np.inf, -np.inf], np.nan)
    prorata = prorata.clip(lower=0, upper=1)

    return prorata
