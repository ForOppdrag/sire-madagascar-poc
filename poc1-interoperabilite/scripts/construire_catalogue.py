"""Construit la base TinyDB du catalogue (OGC API - Records) à partir de
config/catalogue_source.yml.

Usage : python scripts/construire_catalogue.py [--sortie data/catalogue.tinydb]
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import yaml
from tinydb import TinyDB

ICI = Path(__file__).resolve().parents[1]
NIVEAUX = {0: "Catalogué", 1: "Consultable", 2: "Exposé", 3: "Répliqué et harmonisé", 4: "Référence"}


def enregistrement(j: dict) -> dict:
    x0, y0, x1, y1 = j["bbox"]
    maintenant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    liens = []
    if j.get("service"):
        s = j["service"]
        liens.append({"rel": "item", "type": s["type"], "title": s.get("couche", s["type"]), "href": s["href"]})
    proprietes = {
        "type": "dataset",
        "title": j["titre"],
        "description": " ".join(j["description"].split()),
        "keywords": j.get("mots_cles", []),
        "language": "fr",
        "recordCreated": maintenant,
        "recordUpdated": maintenant,
        "license": j.get("licence"),
        "contacts": [{"name": j["producteur"], "roles": ["producer"]}],
        "niveau_integration": j["niveau"],
        "niveau_integration_libelle": NIVEAUX[j["niveau"]],
    }
    proprietes["_metadata-anytext"] = " ".join(
        [proprietes["title"], proprietes["description"], *proprietes["keywords"]])
    return {
        "id": j["id"],
        "type": "Feature",
        "conformsTo": ["http://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core"],
        "geometry": {"type": "Polygon",
                     "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]},
        "properties": proprietes,
        "links": liens,
    }


def construire(source: Path, sortie: Path) -> int:
    jeux = yaml.safe_load(source.read_text(encoding="utf-8"))["jeux"]
    sortie.parent.mkdir(parents=True, exist_ok=True)
    if sortie.exists():
        sortie.unlink()
    db = TinyDB(sortie)
    for j in jeux:
        db.insert(enregistrement(j))
    db.close()
    return len(jeux)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=ICI / "config" / "catalogue_source.yml", type=Path)
    ap.add_argument("--sortie", default=ICI / "data" / "catalogue.tinydb", type=Path)
    a = ap.parse_args()
    n = construire(a.source, a.sortie)
    print(f"{n} fiches écrites dans {a.sortie}")
