"""Methodologie — rappel des methodes actuarielles implementees."""

from __future__ import annotations

import streamlit as st

st.title("Methodologie")
st.caption("Rappel des methodes implementees dans AutoReserve (toutes codees from scratch).")

st.markdown(
    """
### 1. Segmentation
Les sinistres sont traites separement en **CORPOREL** (dommages aux personnes,
queue de developpement longue) et **MATERIEL** (dommages aux biens, developpement
rapide). Les deux ont des dynamiques tres differentes : les melanger biaiserait
les coefficients de developpement.

### 2. PPNA (Provision pour Primes Non Acquises)
Part de prime emise correspondant a la periode de couverture **posterieure** a la
date de cloture. Calculee au prorata temporis sur chaque contrat, elle sert aussi
a derouler la **Prime Acquise** utilisee comme a priori du Bornhuetter-Ferguson.

### 3. Triangles de developpement
Pour chaque segment, on construit le triangle des **paiements cumules** par
(annee de survenance x indice de developpement). La diagonale courante represente
la situation a la date d'arrete ; le coin inferieur droit (le futur) est a estimer.

### 4. Chain-Ladder deterministe
Projette le triangle via les **coefficients de developpement** (link ratios)
`f_k = Sum C[i,k+1] / Sum C[i,k]`. Implementation validee sur l'exemple de
reference **Mack (1993)**. Donne la charge ultime et les reserves (IBNR + IBNER).

### 5. Ecretement des sinistres graves
Quelques sinistres atypiques gonflent les `f_k` et donc l'ultime. On **plafonne
(capping)** le cumul de chaque sinistre a un seuil (quantile des paiements), on
projette le triangle plafonne, et on **reajoute l'excedent paye** des graves.
On raisonne en **paiements** (flux) et jamais en paye+SAP (le SAP est un stock).

### 6. Bornhuetter-Ferguson
Combine une **estimation a priori** (Prime Acquise x Loss Ratio) et le
developpement observe : `Ultime = Paye + A priori x (1 - Beta)`. Plus stable que
le Chain-Ladder sur les annees recentes peu matures. Le loss ratio est calibre
sur les annees a **prime reelle** (et non extrapolee).

### 7. Methode du Cout Moyen (encadrant)
Approche par **cout moyen** : charge / nombre de sinistres, ajuste des sinistres
**tardifs** estimes (declarations futures). Methodologie de l'encadrant de stage.

### 8. Consolidation PSAP / IBNR & controle
Les 4 methodes sont comparees par segment et confrontees au **SAP comptable reel**
(provisions dossier/dossier effectivement constituees), donnant le **boni / mali**
et l'**IBNR estime**. Le Best Estimate retient une methode par segment.

### 9. Bootstrap ODP (incertitude)
Bootstrap **Over-Dispersed Poisson** (England & Verrall) : reechantillonnage des
residus de Pearson (erreur d'estimation) + simulation Gamma (erreur de processus),
pour obtenir la **distribution** de la provision, son erreur de prediction et le
quantile **99,5 %** (niveau Solvabilite II).
"""
)

st.info(
    "Tous les calculs sont **deterministes et tracables** (aucune IA generative). "
    "Les exports Excel reproduisent exactement les chiffres de la plateforme."
)
