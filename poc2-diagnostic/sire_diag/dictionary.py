"""Génération du dictionnaire de données et du rapport de qualité.

Le dictionnaire produit est un premier jet automatique : les colonnes
« définition » et « unité validée » sont à compléter avec le producteur.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .profiler import Profil


def vers_tableau(p: Profil) -> pd.DataFrame:
    lignes = []
    for c in p.colonnes:
        lignes.append({
            "champ": c.nom,
            "type": c.type_infere,
            "unité devinée": c.unite_devinee or "",
            "unité validée": "",
            "définition": "",
            "complétude": f"{c.taux_completude:.0%}",
            "valeurs distinctes": c.nb_distincts,
            "min": c.minimum or "",
            "max": c.maximum or "",
            "identifiant candidat": "oui" if c.identifiant_candidat else "",
            "exemples": " | ".join(c.exemples),
        })
    return pd.DataFrame(lignes)


def _md_table(df: pd.DataFrame) -> str:
    entete = "| " + " | ".join(df.columns) + " |"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |"
    corps = ["| " + " | ".join(str(v).replace("|", "/") for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([entete, sep, *corps])


def vers_markdown(p: Profil) -> str:
    lignes = [f"# Dictionnaire et profil de qualité — {Path(p.source).name}", ""]
    lignes += [
        f"- **Lignes** : {p.nb_lignes} · **Champs** : {p.nb_colonnes}",
        f"- **Score de qualité indicatif** : {p.score_qualite} / 100",
        f"- **Complétude globale** : {p.taux_completude_global:.0%}",
        f"- **Lignes dupliquées** : {p.lignes_dupliquees}",
    ]
    if p.geographique:
        lignes += [
            f"- **Système de coordonnées** : {p.crs or 'non déclaré'}",
            f"- **Emprise (WGS 84)** : {p.emprise}",
            f"- **Objets hors Madagascar** : {p.hors_madagascar}",
        ]
        if p.types_geometrie:
            lignes.append(f"- **Géométries** : {', '.join(p.types_geometrie)} "
                     f"({p.geometries_invalides} invalide(s), {p.geometries_vides} vide(s))")
    if p.colonne_temporelle:
        lignes.append(f"- **Temps** : champ « {p.colonne_temporelle} », du {p.date_min} au {p.date_max}, "
                 f"pas {p.pas_de_temps or 'indéterminé'}, dernière valeur il y a {p.anciennete_jours} jours")
    lignes += ["", "## Alertes", ""]
    lignes += [f"- {a}" for a in p.alertes] or ["- Aucune alerte"]
    lignes += ["", "## Dictionnaire de données", "", _md_table(vers_tableau(p)), "",
          "_Premier jet généré automatiquement : définitions et unités à valider avec le producteur._", ""]
    return "\n".join(lignes)


def ecrire(p: Profil, dossier: str | Path, formats: tuple[str, ...] = ("md", "json", "xlsx")) -> list[Path]:
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    base = dossier / Path(p.source).stem
    sorties = []
    if "md" in formats:
        f = base.with_suffix(".dictionnaire.md")
        f.write_text(vers_markdown(p), encoding="utf-8")
        sorties.append(f)
    if "json" in formats:
        f = base.with_suffix(".profil.json")
        f.write_text(json.dumps(p.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        sorties.append(f)
    if "xlsx" in formats:
        f = base.with_suffix(".dictionnaire.xlsx")
        with pd.ExcelWriter(f) as w:
            vers_tableau(p).to_excel(w, sheet_name="dictionnaire", index=False)
            pd.DataFrame({"alerte": p.alertes or ["Aucune alerte"]}).to_excel(w, sheet_name="alertes", index=False)
        sorties.append(f)
    return sorties
