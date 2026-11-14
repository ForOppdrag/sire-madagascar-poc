"""Modèle Excel de fiche d'inventaire pour la collecte sur le terrain, et import
des fiches remplies dans la base d'inventaire.

Les équipes remplissent le classeur avec les points focaux (listes déroulantes
pour les valeurs contrôlées), puis le classeur est importé en une commande.
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from .inventory import Inventaire, JeuDonnees, Systeme

LISTES = {
    "statut": ["actif", "partiel", "arrete", "inconnu"],
    "acces": ["api", "base", "fichier", "papier", "inconnu"],
    "classification": ["public", "interne", "restreint", "inconnu"],
    "donnees_personnelles": ["oui", "non"],
    "niveau_integration_cible": ["0", "1", "2", "3", "4"],
}
AIDE = {
    "niveau_integration_cible": "0 catalogué · 1 consultable · 2 exposé · 3 répliqué · 4 référence",
    "acces": "Mode d'accès actuel à la donnée",
    "classification": "Sensibilité de la donnée",
    "donnees_personnelles": "Le jeu contient-il des données personnelles ?",
}
FEUILLES = {"institutions": ["code", "nom", "point_focal"],
            "systemes": [f.name for f in fields(Systeme)],
            "jeux_donnees": [f.name for f in fields(JeuDonnees)]}


def creer_modele(chemin: str | Path, nb_lignes: int = 200) -> Path:
    chemin = Path(chemin)
    wb = Workbook()
    wb.remove(wb.active)
    entete = PatternFill("solid", fgColor="0B3C5D")
    for nom, colonnes in FEUILLES.items():
        ws = wb.create_sheet(nom)
        for j, col in enumerate(colonnes, start=1):
            c = ws.cell(row=1, column=j, value=col)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = entete
            c.alignment = Alignment(wrap_text=True, vertical="top")
            ws.cell(row=2, column=j, value=AIDE.get(col, "")).font = Font(italic=True, color="5C7A8A")
            ws.column_dimensions[c.column_letter].width = max(16, len(col) + 4)
            if col in LISTES:
                dv = DataValidation(type="list", formula1='"' + ",".join(LISTES[col]) + '"', allow_blank=True)
                ws.add_data_validation(dv)
                dv.add(f"{c.column_letter}3:{c.column_letter}{nb_lignes + 2}")
        ws.freeze_panes = "A3"
    wb.save(chemin)
    return chemin


def _lire(ws_df: pd.DataFrame) -> list[dict]:
    df = ws_df.iloc[1:]  # la ligne 2 contient l'aide
    df = df.dropna(how="all")
    return [{k: (None if pd.isna(v) else v) for k, v in r.items()} for r in df.to_dict("records")]


def importer(classeur: str | Path, base: str | Path) -> dict:
    """Importe un classeur rempli ; renvoie le nombre d'éléments par feuille."""
    load_workbook(classeur)  # vérifie que le fichier est un classeur valide
    feuilles = pd.read_excel(classeur, sheet_name=None, dtype=str)
    inv = Inventaire(base)
    compte = {}
    n = 0
    for r in _lire(feuilles.get("institutions", pd.DataFrame())):
        if r.get("code"):
            inv.ajouter_institution(r["code"], r.get("nom") or r["code"], r.get("point_focal"))
            n += 1
    compte["institutions"] = n
    n = 0
    for r in _lire(feuilles.get("systemes", pd.DataFrame())):
        if r.get("code") and r.get("nom"):
            inv.ajouter_systeme(Systeme(**{k: r.get(k) for k in FEUILLES["systemes"]
                                           if r.get(k) is not None}))
            n += 1
    compte["systemes"] = n
    n = 0
    for r in _lire(feuilles.get("jeux_donnees", pd.DataFrame())):
        if r.get("code") and r.get("titre"):
            d = {k: r.get(k) for k in FEUILLES["jeux_donnees"] if r.get(k) is not None}
            d["donnees_personnelles"] = str(d.get("donnees_personnelles", "non")).lower() in {"oui", "true", "1"}
            if d.get("niveau_integration_cible") is not None:
                d["niveau_integration_cible"] = int(float(d["niveau_integration_cible"]))
            inv.ajouter_jeu(JeuDonnees(**d))
            n += 1
    compte["jeux_donnees"] = n
    inv.fermer()
    return compte
