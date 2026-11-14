"""Amorce de la base d'inventaire avec les systèmes cités dans les TDR.

Les champs techniques sont laissés « à compléter » : ils seront renseignés
pendant le diagnostic, avec les points focaux de chaque institution.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sire_diag.inventory import Inventaire, JeuDonnees, Systeme  # noqa: E402

A_COMPLETER = "à compléter au diagnostic"

inv = Inventaire(Path(__file__).parent / "inventaire_sire.sqlite")
inv.ajouter_institution("MEAH", "Ministère de l'Eau, de l'Assainissement et de l'Hygiène")
inv.ajouter_institution("ANDEA", "Autorité Nationale de l'Eau et de l'Assainissement")
inv.ajouter_institution("DGM", "Météo Madagascar")

inv.ajouter_systeme(Systeme(code="SEAM", nom="SE&AM", institution="MEAH",
                            fonctions="Système sectoriel du MEAH (cité dans les TDR)",
                            technologies=A_COMPLETER, hebergement=A_COMPLETER, api=A_COMPLETER))
inv.ajouter_systeme(Systeme(code="MAPROOM", nom="Maproom", institution="DGM",
                            fonctions="Produits climatiques en ligne (cité dans les TDR)",
                            technologies=A_COMPLETER, hebergement=A_COMPLETER, api=A_COMPLETER))

inv.ajouter_jeu(JeuDonnees(code="SEAM-01", titre=A_COMPLETER, systeme="SEAM", producteur="MEAH"))
inv.ajouter_jeu(JeuDonnees(code="MAPROOM-01", titre="Pluviométrie (produits climatiques)",
                           systeme="MAPROOM", producteur="DGM", acces="api",
                           niveau_integration_cible=1,
                           commentaire="Consultation à la source envisagée ; à confirmer au diagnostic"))
print(inv.synthese())
inv.fermer()
