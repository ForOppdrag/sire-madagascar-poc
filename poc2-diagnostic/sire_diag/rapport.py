"""Rapport de diagnostic HTML autonome (un seul fichier, sans dépendance externe).

Contenu : synthèse des jeux profilés (score, complétude, alertes), matrice de
compatibilité colorée, puis le détail de chaque jeu. Conçu pour être joint
tel quel à un rapport de diagnostic ou capturé pour une annexe.
"""

from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path

from . import compatibility
from .profiler import Profil

COULEURS = {
    "compatible": "#d7f0ea",
    "partiellement compatible": "#fdf0dc",
    "non mutualisable en l'état": "#f9dcd6",
}

CSS = """
body{font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;color:#1F2A33;margin:0;background:#f6fafb}
header{background:#0B3C5D;color:#fff;padding:20px 32px}header h1{margin:0;font-size:1.4rem}
header p{margin:6px 0 0;opacity:.85;font-size:.9rem}main{max-width:1100px;margin:0 auto;padding:24px 32px}
h2{color:#0B3C5D;font-size:1.1rem;margin-top:32px}h3{color:#1C7293;font-size:1rem;margin:24px 0 8px}
.kpis{display:flex;gap:16px;flex-wrap:wrap}.kpi{background:#fff;border:1px solid #dde7ea;border-radius:8px;padding:12px 16px;min-width:150px}
.kpi b{display:block;font-size:1.6rem;color:#0B3C5D}.kpi span{font-size:.8rem;color:#5C7A8A}
table{border-collapse:collapse;width:100%;background:#fff;font-size:.85rem;margin-top:8px}
th,td{border:1px solid #dde7ea;padding:6px 8px;text-align:left;vertical-align:top}th{background:#EAF4F6}
.score{font-weight:600}.bon{color:#0f6b5a}.moyen{color:#8a5a10}.faible{color:#a33a24}
.bar{height:6px;background:#e3ecef;border-radius:3px;overflow:hidden;margin-top:3px}.bar i{display:block;height:100%;background:#2BB3A3}
ul.alertes{margin:4px 0 0;padding-left:18px}.note{font-size:.8rem;color:#5C7A8A;margin-top:24px}
.defil{overflow-x:auto}.matrice th,.matrice td{font-size:.78rem}
.legende span{display:inline-block;padding:2px 8px;border-radius:4px;margin-right:8px;font-size:.8rem}
"""


def _classe(score: float) -> str:
    return "bon" if score >= 85 else "moyen" if score >= 70 else "faible"


def _nom(p: Profil) -> str:
    return Path(p.source).name


def generer(profils: list[Profil], titre: str = "Rapport de diagnostic des données",
            contexte: str = "") -> str:
    nb_alertes = sum(len(p.alertes) for p in profils)
    moyenne = round(sum(p.score_qualite for p in profils) / len(profils), 1) if profils else 0
    geo = sum(p.geographique for p in profils)

    h = [f"<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'>"
         f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>{escape(titre)}</title><style>{CSS}</style></head><body>",
         f"<header><h1>{escape(titre)}</h1><p>{escape(contexte)} — généré le {date.today():%d/%m/%Y} "
         f"par le kit de diagnostic du SIRE</p></header><main>"]

    h.append("<div class='kpis'>"
             f"<div class='kpi'><b>{len(profils)}</b><span>jeux de données profilés</span></div>"
             f"<div class='kpi'><b>{moyenne}</b><span>score de qualité moyen / 100</span></div>"
             f"<div class='kpi'><b>{geo}</b><span>jeux géographiques</span></div>"
             f"<div class='kpi'><b>{nb_alertes}</b><span>alertes à traiter</span></div></div>")

    h.append("<h2>Synthèse par jeu de données</h2><table><tr><th>Jeu</th><th>Objets</th>"
             "<th>Score</th><th>Complétude</th><th>Système de coordonnées</th><th>Période</th><th>Alertes</th></tr>")
    for p in sorted(profils, key=lambda x: x.score_qualite):
        periode = f"{p.date_min} → {p.date_max} ({p.pas_de_temps})" if p.colonne_temporelle else "—"
        h.append(
            f"<tr><td>{escape(_nom(p))}</td><td>{p.nb_lignes}</td>"
            f"<td class='score {_classe(p.score_qualite)}'>{p.score_qualite}</td>"
            f"<td>{p.taux_completude_global:.0%}<div class='bar'><i style='width:{p.taux_completude_global:.0%}'></i></div></td>"
            f"<td>{escape(p.crs or '—')}</td><td>{escape(periode)}</td><td>{len(p.alertes)}</td></tr>")
    h.append("</table>")

    if len(profils) > 1:
        m = compatibility.matrice(profils)
        h.append("<h2>Matrice de compatibilité</h2><p class='legende'>"
                 + "".join(f"<span style='background:{c}'>{escape(v)}</span>" for v, c in COULEURS.items())
                 + "</p><div class='defil'><table class='matrice'><tr><th></th>" + "".join(f"<th>{escape(c)}</th>" for c in m.columns) + "</tr>")
        for idx, ligne in m.iterrows():
            h.append(f"<tr><th>{escape(idx)}</th>" + "".join(
                f"<td style='background:{COULEURS.get(v, '#fff')}'>{escape(v)}</td>" for v in ligne) + "</tr>")
        h.append("</table></div>")
        h.append("<h3>Actions d'harmonisation proposées</h3><table><tr><th>Couple</th><th>Verdict</th><th>Actions</th></tr>")
        for d in compatibility.details(profils):
            if d["actions"]:
                h.append(f"<tr><td>{escape(Path(d['a']).name)} / {escape(Path(d['b']).name)}</td>"
                         f"<td>{escape(d['verdict'])}</td><td><ul class='alertes'>"
                         + "".join(f"<li>{escape(a)}</li>" for a in d["actions"]) + "</ul></td></tr>")
        h.append("</table>")

    h.append("<h2>Détail par jeu de données</h2>")
    for p in profils:
        h.append(f"<h3>{escape(_nom(p))}</h3>")
        if p.alertes:
            h.append("<ul class='alertes'>" + "".join(f"<li>{escape(a)}</li>" for a in p.alertes) + "</ul>")
        h.append("<table><tr><th>Champ</th><th>Type</th><th>Unité devinée</th><th>Complétude</th>"
                 "<th>Distincts</th><th>Min</th><th>Max</th></tr>")
        for c in p.colonnes:
            h.append(f"<tr><td>{escape(c.nom)}{' 🔑' if c.identifiant_candidat else ''}</td>"
                     f"<td>{escape(c.type_infere)}</td><td>{escape(c.unite_devinee or '')}</td>"
                     f"<td>{c.taux_completude:.0%}</td><td>{c.nb_distincts}</td>"
                     f"<td>{escape(c.minimum or '')}</td><td>{escape(c.maximum or '')}</td></tr>")
        h.append("</table>")

    h.append("<p class='note'>Score indicatif : complétude 35 %, unicité 20 %, validité 30 %, actualité 15 % "
             "(dimensions inspirées de l'ISO 19157-1). Les unités et les définitions sont à valider avec "
             "chaque producteur. 🔑 = identifiant candidat.</p></main></body></html>")
    return "".join(h)
