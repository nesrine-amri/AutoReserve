# AutoReserve

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.65-FF4B4B?logo=streamlit&logoColor=white)
![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)

> **Automatisation du provisionnement technique en assurance automobile.**
> *Automated technical reserving for motor insurance.*

AutoReserve est une plateforme Python qui automatise la chaîne complète de
**provisionnement technique auto** : de l'unification des données de production au
calcul des provisions (PPNA et sinistres), jusqu'à la **quantification de
l'incertitude**. Les méthodes actuarielles sont implémentées *from scratch*, sans
bibliothèque actuarielle externe, pour garantir la **maîtrise, la traçabilité et
l'auditabilité** des calculs.

> ⚠️ **Confidentialité / Confidentiality.** Les **données réelles de l'assureur
> ne sont pas incluses** dans ce dépôt (elles sont exclues via `.gitignore`). Les
> valeurs de référence dans `autoreserve/config.py` sont des **exemples
> illustratifs**, pas les chiffres réels. *Real insurer data is not included in
> this repository; the reference values in the config are illustrative examples.*

---

## 🇫🇷 Français

### Contexte
Projet individuel réalisé dans le cadre d'un **stage d'ingénieur en actuariat**
(assurance non-vie, branche automobile). L'objectif : tester, dans un cadre
exploratoire, la faisabilité d'une automatisation **fiable, reproductible et
conforme** du calcul des provisions, là où il est traditionnellement réalisé
manuellement sur tableur.

### Fonctionnalités
- **Ingestion & unification** — consolidation de bases de primes et de sinistres
  hétérogènes, fiabilisation (anomalies, doublons *émise/corrigée*,
  contre-passations).
- **PPNA** — calcul réglementaire au **prorata temporis**, contrat par contrat,
  avec validation contre un compte technique de référence.
- **Provisionnement des sinistres** — construction des triangles de développement
  et trois méthodes déterministes : **Chain-Ladder** (validé sur l'exemple de
  référence de Mack 1993), **Bornhuetter-Ferguson** et **coût moyen**.
- **Écrêtement des sinistres graves** — plafonnement (*capping*) sur les paiements
  et analyse de sensibilité au seuil.
- **Consolidation** — *Best Estimate* par segment, confronté aux provisions
  comptables réelles (boni/mali, IBNR).
- **Incertitude** — **bootstrap Over-Dispersed Poisson** (erreur de prédiction,
  CV, VaR 99,5 % au sens de Solvabilité II).
- **Plateforme interactive** (Streamlit) — exploration des résultats, import de
  fichiers Excel, export des synthèses, simulateur de validation.
- **Fiabilité** — suite de **tests automatisés** (pytest) et **simulateur à vérité
  connue** (le Chain-Ladder doit retrouver l'ultime construit).
- **Notebook pédagogique** — déroulé commenté de l'ensemble du pipeline.

### Architecture
```
autoreserve/            # cœur de calcul (package, méthodes from scratch)
├── ingestion/          # chargement + unification des bases
├── actuarial/          # PPNA (prorata temporis), utilitaires de dates
├── sinistres/          # triangles, Chain-Ladder, BF, coût moyen,
│                       #   écrêtement, consolidation, bootstrap ODP
├── reporting/          # graphiques (Plotly), exports Excel, palette
├── simulation.py       # générateur de triangles à vérité connue
└── config.py           # paramètres (valeurs de référence = exemples)

app_pages/              # pages de la plateforme Streamlit
streamlit_app.py        # point d'entrée de l'application
app_data.py             # accès aux données (mise en cache)

tests/                  # suite pytest (basée sur le simulateur)
notebooks/              # notebook pédagogique du pipeline
```

### Installation
```bash
git clone https://github.com/nesrine-amri/AutoReserve.git
cd AutoReserve
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

### Utilisation
```bash
# Lancer la plateforme interactive
streamlit run streamlit_app.py

# Lancer les tests
pytest

# Ouvrir le notebook pédagogique
jupyter notebook notebooks/AutoReserve_pipeline.ipynb
```

### Données
Le dépôt **ne contient pas de données**. L'application attend un dossier `data/`
local (ignoré par git) organisé ainsi :
```
data/raw/         # fichiers sources (primes, sinistres) — non versionnés
data/processed/   # bases unifiées / enrichies générées par le pipeline
data/outputs/     # exports
```
Sans données, la **plateforme reste navigable** (messages informatifs) et la
**suite de tests passe** (elle repose sur le simulateur, pas sur des données
réelles).

### Stack technique
Python 3.14 · pandas · NumPy · Streamlit · Plotly · openpyxl · pytest.

---

## 🇬🇧 English

### Context
Individual project carried out during an **actuarial engineering internship**
(non-life insurance, motor line). Goal: explore the feasibility of a **reliable,
reproducible and compliant** automation of reserving, traditionally done manually
in spreadsheets.

### Features
- **Ingestion & unification** of heterogeneous premium and claims bases, with data
  cleaning (anomalies, *issued/corrected* duplicates, reversals).
- **UPR (PPNA)** — regulatory **pro rata temporis** calculation, contract by
  contract, validated against a reference technical account.
- **Claims reserving** — development triangles and three deterministic methods:
  **Chain-Ladder** (validated on Mack's 1993 reference example),
  **Bornhuetter-Ferguson** and **average cost**.
- **Large-loss capping** on payments, with threshold sensitivity analysis.
- **Consolidation** — per-segment *Best Estimate* confronted with booked reserves
  (surplus/deficit, IBNR).
- **Uncertainty** — **Over-Dispersed Poisson bootstrap** (prediction error, CV,
  99.5 % VaR à la Solvency II).
- **Interactive platform** (Streamlit) — result exploration, Excel import,
  synthesis export, validation simulator.
- **Reliability** — automated **pytest** suite and a **ground-truth simulator**
  (Chain-Ladder must recover the constructed ultimate).
- **Pedagogical notebook** walking through the whole pipeline.

### Installation
```bash
git clone https://github.com/nesrine-amri/AutoReserve.git
cd AutoReserve
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Usage
```bash
streamlit run streamlit_app.py     # interactive platform
pytest                             # test suite
jupyter notebook notebooks/AutoReserve_pipeline.ipynb
```

### Data
The repository **ships no data**. The app expects a local, git-ignored `data/`
folder (`raw/`, `processed/`, `outputs/`). Without data, the **platform still runs**
and the **test suite still passes** (it relies on the simulator, not on real data).

### Tech stack
Python 3.14 · pandas · NumPy · Streamlit · Plotly · openpyxl · pytest.

---

## Auteur / Author
**Nesrine El Amri** — projet de stage actuariel (usage académique).

### Méthodes / References
- T. Mack (1993), *Distribution-free calculation of the standard error of
  chain-ladder reserve estimates*, ASTIN Bulletin.
- P. D. England & R. J. Verrall (2002), *Stochastic claims reserving in general
  insurance*, British Actuarial Journal.
- R. L. Bornhuetter & R. E. Ferguson (1972), *The actuary and IBNR*, PCAS.
