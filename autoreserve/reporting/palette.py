"""
Palette de la plateforme AutoReserve (mode clair).

Palette categorielle validee CVD-safe (dataviz) : les teintes sont assignees
dans un ORDRE FIXE, jamais cyclees. Les couleurs de statut (boni/mali) sont
reservees et ne servent jamais de "serie de plus".
"""

# --- Surfaces & encre ---
SURFACE = "#fcfcfb"      # fond des graphes
PAGE = "#f9f9f7"         # fond de page
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"        # axes / labels
GRID = "#e1e0d9"         # hairline
BASELINE = "#c3c2b7"

# --- Palette categorielle (ordre fixe) ---
CATEGORICAL = [
    "#2a78d6",  # 1 bleu
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 jaune
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 vert
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 rouge
]

# --- Statut (reserve, jamais themise) ---
STATUS = {
    "good": "#0ca30c",      # boni
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",  # mali
}

# --- Affectation fixe des methodes a un slot categoriel ---
COULEUR_METHODE = {
    "Chain-Ladder brut": CATEGORICAL[0],      # bleu
    "Chain-Ladder ecrete": CATEGORICAL[2],    # aqua (methode retenue, mise en avant)
    "Bornhuetter-Ferguson": CATEGORICAL[1],   # orange
    "Methode CM": CATEGORICAL[3],             # jaune
}

# SAP comptable reel = benchmark, rendu en reference neutre (jamais une "serie")
COULEUR_SAP_REEL = INK_SECONDARY

# Teinte par segment (pour les vues ou le segment est la dimension couleur)
COULEUR_SEGMENT = {
    "CORPOREL": CATEGORICAL[0],   # bleu
    "MATERIEL": CATEGORICAL[1],   # orange
}
