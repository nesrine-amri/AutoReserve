"""
Graphiques Plotly de la plateforme AutoReserve.

Regles dataviz appliquees : une seule echelle par graphe, teintes categorielles
en ordre fixe (jamais cyclees), statut reserve au boni/mali, legende presente
des >= 2 series, axes/grilles recessifs, montants en M DT pour la lisibilite.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from autoreserve.reporting import palette as P

MDT = 1_000_000  # conversion DT -> millions de DT


def _layout(fig: go.Figure, titre: str, y_titre: str = "Montant (M DT)") -> go.Figure:
    """Applique l'habillage commun (fond, encre, grille, legende)."""
    fig.update_layout(
        title=dict(text=titre, font=dict(size=17, color=P.INK_PRIMARY),
                   x=0.01, xanchor="left", y=0.97, yanchor="top"),
        paper_bgcolor=P.SURFACE,
        plot_bgcolor=P.SURFACE,
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif',
                  size=13, color=P.INK_SECONDARY),
        margin=dict(l=60, r=24, t=96, b=48),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
                    font=dict(color=P.INK_SECONDARY)),
        hoverlabel=dict(bgcolor="white", font_size=13),
    )
    fig.update_xaxes(showgrid=False, linecolor=P.BASELINE, tickcolor=P.MUTED,
                     tickfont=dict(color=P.MUTED))
    fig.update_yaxes(title=dict(text=y_titre, font=dict(color=P.MUTED, size=12)),
                     gridcolor=P.GRID, zerolinecolor=P.BASELINE,
                     tickfont=dict(color=P.MUTED), tickformat=",.0f")
    return fig


def fig_reserves_par_methode(comparatif_tab: pd.DataFrame, segment: str) -> go.Figure:
    """
    Barres des reserves par methode (ordre fixe) + ligne de reference = SAP
    comptable reel. Une echelle, le benchmark n'est pas une 'serie'.
    """
    methodes = [m for m in P.COULEUR_METHODE if m in comparatif_tab.index]
    vals = [comparatif_tab.loc[m, "reserves"] / MDT for m in methodes]
    couleurs = [P.COULEUR_METHODE[m] for m in methodes]
    sap = float(comparatif_tab["sap_comptable"].iloc[0]) / MDT

    labels = [m.replace("Chain-Ladder", "CL").replace("Bornhuetter-Ferguson", "BF")
              .replace("Methode CM", "CM") for m in methodes]

    fig = go.Figure()
    fig.add_bar(
        x=labels, y=vals, marker_color=couleurs, width=0.6,
        text=[f"{v:,.1f}" for v in vals], textposition="outside",
        textfont=dict(color=P.INK_PRIMARY),
        hovertemplate="%{x}<br>Reserves : %{y:,.1f} M DT<extra></extra>",
        name="Reserves estimees",
    )
    # ligne de reference SAP reel
    fig.add_hline(y=sap, line=dict(color=P.COULEUR_SAP_REEL, width=2, dash="dash"),
                  annotation_text=f"SAP comptable reel : {sap:,.1f} M DT",
                  annotation_position="top left",
                  annotation_font=dict(color=P.COULEUR_SAP_REEL, size=12))
    fig = _layout(fig, f"Reserves par methode — {segment}")
    fig.update_layout(showlegend=False)
    return fig


def fig_boni_mali(synthese: pd.DataFrame) -> go.Figure:
    """
    Barres divergentes du boni(+)/mali(-) par segment : vert = sur-provision
    (boni), rouge = sous-provision (mali). Statut + signe, jamais couleur seule.
    """
    segs = list(synthese.index)
    vals = [synthese.loc[s, "boni_mali"] / MDT for s in segs]
    couleurs = [P.STATUS["good"] if v >= 0 else P.STATUS["critical"] for v in vals]

    fig = go.Figure()
    fig.add_bar(
        x=segs, y=vals, marker_color=couleurs, width=0.5,
        text=[f"{'+' if v >= 0 else ''}{v:,.1f}" for v in vals],
        textposition="outside", textfont=dict(color=P.INK_PRIMARY),
        hovertemplate="%{x}<br>Boni/Mali : %{y:+,.1f} M DT<extra></extra>",
    )
    fig.add_hline(y=0, line=dict(color=P.BASELINE, width=1))
    fig = _layout(fig, "Boni (+) / Mali (-) comptable par segment",
                  y_titre="Boni (+) / Mali (-) (M DT)")
    fig.update_layout(showlegend=False)
    return fig


def fig_sensibilite_graves(sens_tab: pd.DataFrame, segment: str) -> go.Figure:
    """
    Ultime brut (reference) vs ultime ecrete selon le seuil de gravite.
    Une echelle (M DT), x = seuil de gravite.
    """
    seuils = (sens_tab["seuil"] / MDT).tolist()
    brut = (sens_tab["ultime_brut"] / MDT).tolist()
    ecrete = (sens_tab["ultime_ecrete"] / MDT).tolist()

    fig = go.Figure()
    fig.add_scatter(
        x=seuils, y=brut, mode="lines", name="Ultime brut (reference)",
        line=dict(color=P.MUTED, width=2, dash="dash"),
        hovertemplate="Seuil %{x:,.2f} M<br>Ultime brut : %{y:,.1f} M DT<extra></extra>",
    )
    fig.add_scatter(
        x=seuils, y=ecrete, mode="lines+markers", name="Ultime ecrete",
        line=dict(color=P.COULEUR_METHODE["Chain-Ladder ecrete"], width=2.5),
        marker=dict(size=8),
        hovertemplate="Seuil %{x:,.2f} M<br>Ultime ecrete : %{y:,.1f} M DT<extra></extra>",
    )
    fig = _layout(fig, f"Sensibilite de l'ultime au seuil d'ecretement — {segment}")
    fig.update_xaxes(title=dict(text="Seuil de gravite (M DT)",
                                font=dict(color=P.MUTED, size=12)), tickformat=",.2f")
    return fig


def fig_simulation_recuperation(
    annees: list[int], vrais: list[float], estimes: list[float]
) -> go.Figure:
    """
    Simulateur : ultime VRAI (connu par construction) vs ultime estime par le
    Chain-Ladder, par annee de survenance. Barres groupees, une echelle.
    """
    vrais_m = [v / MDT for v in vrais]
    est_m = [e / MDT for e in estimes]
    x = [str(a) for a in annees]

    fig = go.Figure()
    fig.add_bar(x=x, y=vrais_m, name="Ultime vrai (connu)",
                marker_color=P.MUTED,
                hovertemplate="%{x} — vrai : %{y:,.2f} M<extra></extra>")
    fig.add_bar(x=x, y=est_m, name="Ultime estime (Chain-Ladder)",
                marker_color=P.CATEGORICAL[0],
                hovertemplate="%{x} — estime : %{y:,.2f} M<extra></extra>")
    fig = _layout(fig, "Simulateur — l'estimation retrouve-t-elle la verite ?")
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08)
    fig.update_xaxes(title=dict(text="Annee de survenance",
                                font=dict(color=P.MUTED, size=12)))
    return fig


def fig_validation_ppna(val: dict) -> go.Figure:
    """
    Rapprochement 2024 : Primes emises, Prime acquise et PPNA — notre calcul
    vs le Compte Technique de l'encadrant (barres groupees).
    """
    labels = ["Primes emises", "Prime acquise", "PPNA"]
    calc = [val["primes_calc"] / MDT, val["pa_calc"] / MDT, val["ppna_calc"] / MDT]
    cible = [val["primes_cible"] / MDT, val["pa_cible"] / MDT, val["ppna_cible"] / MDT]

    fig = go.Figure()
    fig.add_bar(x=labels, y=calc, name="Résultat", marker_color=P.CATEGORICAL[0],
                text=[f"{v:,.1f}" for v in calc], textposition="outside",
                textfont=dict(color=P.INK_PRIMARY),
                hovertemplate="%{x} — résultat : %{y:,.1f} M DT<extra></extra>")
    fig.add_bar(x=labels, y=cible, name="Compte Technique",
                marker_color=P.MUTED,
                text=[f"{v:,.1f}" for v in cible], textposition="outside",
                textfont=dict(color=P.INK_SECONDARY),
                hovertemplate="%{x} — cible : %{y:,.1f} M DT<extra></extra>")
    fig = _layout(fig, "Rapprochement 2024 vs Compte Technique de l'encadrant")
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08)
    return fig


def fig_bootstrap_distribution(resultat: dict, segment: str) -> go.Figure:
    """
    Distribution bootstrap ODP de la provision + reperes : Best Estimate (CL),
    quantile 95% et quantile 99,5% (niveau Solvabilite II).
    """
    reserves = resultat["reserves"] / MDT
    be = resultat["best_estimate_cl"] / MDT
    q95 = resultat["quantiles"]["95%"] / MDT
    q995 = resultat["quantiles"]["99.5%"] / MDT

    fig = go.Figure()
    fig.add_histogram(
        x=reserves, nbinsx=50, marker_color=P.CATEGORICAL[0], opacity=0.85,
        name="Provisions simulees",
        hovertemplate="Provision : %{x:,.1f} M DT<br>Freq : %{y}<extra></extra>",
    )
    fig.add_vline(x=be, line=dict(color=P.INK_PRIMARY, width=2, dash="dash"),
                  annotation_text=f"Best Estimate : {be:,.1f} M",
                  annotation_position="top",
                  annotation_font=dict(color=P.INK_PRIMARY, size=12))
    fig.add_vline(x=q95, line=dict(color=P.STATUS["serious"], width=2),
                  annotation_text=f"95% : {q95:,.1f} M", annotation_position="top right",
                  annotation_font=dict(color=P.STATUS["serious"], size=12))
    fig.add_vline(x=q995, line=dict(color=P.STATUS["critical"], width=2),
                  annotation_text=f"99,5% : {q995:,.1f} M", annotation_position="bottom right",
                  annotation_font=dict(color=P.STATUS["critical"], size=12))
    fig = _layout(fig, f"Distribution bootstrap des provisions — {segment}",
                  y_titre="Frequence")
    fig.update_xaxes(title=dict(text="Provision (M DT)", font=dict(color=P.MUTED, size=12)))
    fig.update_layout(showlegend=False, bargap=0.02)
    return fig


def fig_triangle_developpement(triangle: pd.DataFrame, segment: str) -> go.Figure:
    """
    Courbes de developpement cumule par annee de survenance.
    Nombreuses series -> rampe sequentielle bleue (ancien = clair, recent = fonce),
    l'annee porte l'ordre, pas des teintes categorielles cyclees.
    """
    annees = list(triangle.index)
    # couleurs franches et distinctes (pas un degrade) pour bien separer les annees
    distinctes = ["#2a78d6", "#eb6834", "#1baf7a", "#8e44ad", "#e34948",
                  "#008300", "#e87ba4", "#0d366b"]

    fig = go.Figure()
    for i, annee in enumerate(annees):
        couleur = distinctes[i % len(distinctes)]
        ligne = triangle.loc[annee].dropna() / MDT
        fig.add_scatter(
            x=list(ligne.index), y=ligne.values, mode="lines+markers",
            name=str(int(annee)), line=dict(color=couleur, width=2.4),
            marker=dict(size=7, color=couleur),
            hovertemplate=f"{int(annee)} — dev %{{x}}<br>%{{y:,.1f}} M DT<extra></extra>",
        )
    fig = _layout(fig, f"Developpement cumule des paiements — {segment}")
    fig.update_xaxes(title=dict(text="Indice de developpement",
                                font=dict(color=P.MUTED, size=12)), dtick=1)
    fig.update_yaxes(dtick=1)  # graduations entieres (evite les doublons 0,0,1,1,...)
    fig.update_layout(legend=dict(title=dict(text="Survenance", font=dict(size=11))))
    return fig
