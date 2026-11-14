"""Interface en ligne de commande du kit de diagnostic.

Exemples :
    sire-diag profiler donnees/stations.csv donnees/pluie.xlsx -o rapports/
    sire-diag matrice donnees/*.csv -o rapports/
    sire-diag metadonnees donnees/stations.csv --titre "Stations hydrométriques" --organisation MEAH
    sire-diag inventaire inventaire.sqlite --exporter rapports/inventaire
    sire-diag rapport donnees/* -o rapports/rapport_diagnostic.html
    sire-diag modele-inventaire -o fiche_inventaire.xlsx
    sire-diag importer-inventaire fiche_inventaire_remplie.xlsx inventaire.sqlite
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import compatibility, dictionary, metadata, modele_inventaire, rapport
from .inventory import Inventaire
from .profiler import profiler


def _cmd_profiler(a: argparse.Namespace) -> int:
    for f in a.fichiers:
        p = profiler(f)
        sorties = dictionary.ecrire(p, a.sortie)
        print(f"{Path(f).name:40s} score {p.score_qualite:5.1f}/100  "
              f"{len(p.alertes)} alerte(s)  -> {', '.join(s.name for s in sorties)}")
    return 0


def _cmd_matrice(a: argparse.Namespace) -> int:
    profils = [profiler(f) for f in a.fichiers]
    out = Path(a.sortie)
    out.mkdir(parents=True, exist_ok=True)
    m = compatibility.matrice(profils)
    m.to_csv(out / "matrice_compatibilite.csv", encoding="utf-8")
    (out / "compatibilite_details.json").write_text(
        json.dumps(compatibility.details(profils), ensure_ascii=False, indent=2), encoding="utf-8")
    print(m.to_string())
    return 0


def _cmd_metadonnees(a: argparse.Namespace) -> int:
    p = profiler(a.fichier)
    xml = metadata.fiche_iso19139(p, a.titre, a.organisation, a.resume or "", a.mots_cles)
    cible = Path(a.sortie) if a.sortie else Path(a.fichier).with_suffix(".iso19139.xml")
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(xml, encoding="utf-8")
    print(cible)
    return 0


def _cmd_inventaire(a: argparse.Namespace) -> int:
    inv = Inventaire(a.base)
    print(json.dumps(inv.synthese(), ensure_ascii=False, indent=2))
    if a.exporter:
        for p in inv.exporter_csv(a.exporter):
            print(p)
    inv.fermer()
    return 0


def _cmd_rapport(a: argparse.Namespace) -> int:
    profils = [profiler(f) for f in a.fichiers]
    cible = Path(a.sortie)
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(rapport.generer(profils, a.titre, a.contexte), encoding="utf-8")
    print(cible)
    return 0


def _cmd_modele(a: argparse.Namespace) -> int:
    print(modele_inventaire.creer_modele(a.sortie))
    return 0


def _cmd_importer(a: argparse.Namespace) -> int:
    print(json.dumps(modele_inventaire.importer(a.classeur, a.base), ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sire-diag", description="Kit de diagnostic des données du SIRE")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("profiler", help="Profil de qualité et dictionnaire de données")
    p.add_argument("fichiers", nargs="+")
    p.add_argument("-o", "--sortie", default="rapports")
    p.set_defaults(func=_cmd_profiler)

    m = sp.add_parser("matrice", help="Matrice de compatibilité entre jeux de données")
    m.add_argument("fichiers", nargs="+")
    m.add_argument("-o", "--sortie", default="rapports")
    m.set_defaults(func=_cmd_matrice)

    md = sp.add_parser("metadonnees", help="Fiche ISO 19139 pour le catalogue")
    md.add_argument("fichier")
    md.add_argument("--titre", required=True)
    md.add_argument("--organisation", required=True)
    md.add_argument("--resume")
    md.add_argument("--mots-cles", nargs="*")
    md.add_argument("-o", "--sortie")
    md.set_defaults(func=_cmd_metadonnees)

    i = sp.add_parser("inventaire", help="Synthèse et export de la base d'inventaire")
    i.add_argument("base")
    i.add_argument("--exporter")
    i.set_defaults(func=_cmd_inventaire)

    r = sp.add_parser("rapport", help="Rapport de diagnostic HTML autonome")
    r.add_argument("fichiers", nargs="+")
    r.add_argument("-o", "--sortie", default="rapports/rapport_diagnostic.html")
    r.add_argument("--titre", default="Rapport de diagnostic des données")
    r.add_argument("--contexte", default="SIRE Madagascar")
    r.set_defaults(func=_cmd_rapport)

    mo = sp.add_parser("modele-inventaire", help="Classeur Excel de collecte pour l'inventaire")
    mo.add_argument("-o", "--sortie", default="fiche_inventaire.xlsx")
    mo.set_defaults(func=_cmd_modele)

    im = sp.add_parser("importer-inventaire", help="Importer un classeur d'inventaire rempli")
    im.add_argument("classeur")
    im.add_argument("base")
    im.set_defaults(func=_cmd_importer)

    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
