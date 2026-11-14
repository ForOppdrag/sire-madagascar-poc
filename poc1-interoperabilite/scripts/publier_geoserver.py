"""Publie les couches PostGIS du SIRE dans GeoServer via son API REST.

Crée l'espace de travail « sire », l'entrepôt PostGIS, publie les couches
bassins / rivieres / regions avec un style SLD, puis vérifie le GetCapabilities.

Usage : python scripts/publier_geoserver.py [--url http://localhost:8080/geoserver]
Variables : GEOSERVER_ADMIN_USER, GEOSERVER_ADMIN_PASSWORD, POSTGRES_* (voir .env)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests

ICI = Path(__file__).resolve().parents[1]
ESPACE = "sire"
ENTREPOT = "sire_postgis"
COUCHES = {
    "bassins": ("Bassins versants (HydroBASINS niveau 6)", "sire_bassins"),
    "rivieres": ("Réseau hydrographique (HydroRIVERS)", "sire_rivieres"),
    "regions": ("Régions administratives (COD-AB)", "sire_regions"),
}


def charger_env() -> None:
    f = ICI / ".env"
    if f.exists():
        for ligne in f.read_text(encoding="utf-8").splitlines():
            if "=" in ligne and not ligne.lstrip().startswith("#"):
                k, v = ligne.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


class GeoServer:
    def __init__(self, url: str, user: str, mdp: str):
        self.rest = url.rstrip("/") + "/rest"
        self.url = url.rstrip("/")
        self.s = requests.Session()
        self.s.auth = (user, mdp)
        self.s.headers["Accept"] = "application/json"

    def existe(self, chemin: str) -> bool:
        return self.s.get(f"{self.rest}/{chemin}").status_code == 200

    def poster(self, chemin: str, json=None, data=None, entete=None) -> None:
        r = self.s.post(f"{self.rest}/{chemin}", json=json, data=data, headers=entete or {})
        if r.status_code not in (200, 201):
            raise RuntimeError(f"POST {chemin} -> {r.status_code} {r.text[:300]}")

    def mettre(self, chemin: str, json=None, data=None, entete=None) -> None:
        r = self.s.put(f"{self.rest}/{chemin}", json=json, data=data, headers=entete or {})
        if r.status_code not in (200, 201):
            raise RuntimeError(f"PUT {chemin} -> {r.status_code} {r.text[:300]}")


def main() -> int:
    charger_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("GEOSERVER_URL", "http://localhost:8080/geoserver"))
    a = ap.parse_args()
    gs = GeoServer(a.url, os.environ.get("GEOSERVER_ADMIN_USER", "admin"),
                   os.environ.get("GEOSERVER_ADMIN_PASSWORD", "geoserver"))

    if not gs.existe(f"workspaces/{ESPACE}"):
        gs.poster("workspaces", json={"workspace": {"name": ESPACE}})
        print(f"espace de travail « {ESPACE} » créé")

    if not gs.existe(f"workspaces/{ESPACE}/datastores/{ENTREPOT}"):
        params = {
            "host": "postgis",  # nom du service dans docker-compose
            "port": "5432",
            "database": os.environ.get("POSTGRES_DB", "sire"),
            "user": os.environ.get("POSTGRES_USER", "sire"),
            "passwd": os.environ.get("POSTGRES_PASSWORD", "sire"),
            "schema": "public",
            "dbtype": "postgis",
            "Expose primary keys": "true",
        }
        gs.poster(f"workspaces/{ESPACE}/datastores", json={"dataStore": {
            "name": ENTREPOT,
            "connectionParameters": {"entry": [{"@key": k, "$": v} for k, v in params.items()]},
        }})
        print(f"entrepôt PostGIS « {ENTREPOT} » créé")

    for nom, (titre, style) in COUCHES.items():
        sld = (ICI / "styles" / f"{style}.sld").read_text(encoding="utf-8")
        if not gs.existe(f"workspaces/{ESPACE}/styles/{style}"):
            gs.poster(f"workspaces/{ESPACE}/styles?name={style}", data=sld.encode("utf-8"),
                      entete={"Content-Type": "application/vnd.ogc.sld+xml"})
        if not gs.existe(f"workspaces/{ESPACE}/datastores/{ENTREPOT}/featuretypes/{nom}"):
            try:
                gs.poster(f"workspaces/{ESPACE}/datastores/{ENTREPOT}/featuretypes", json={"featureType": {
                    "name": nom, "nativeName": nom, "title": titre, "srs": "EPSG:4326",
                    "keywords": {"string": ["SIRE", "eau", "Madagascar"]},
                }})
            except RuntimeError as e:
                print(f"  couche « {nom} » non publiée (table absente ?) : {e}", file=sys.stderr)
                continue
        gs.mettre(f"layers/{ESPACE}:{nom}", json={"layer": {"defaultStyle": {"name": f"{ESPACE}:{style}"}}})
        print(f"couche « {ESPACE}:{nom} » publiée avec le style {style}")

    cap = requests.get(f"{gs.url}/{ESPACE}/wms", params={"service": "WMS", "request": "GetCapabilities"}, timeout=30)
    print(f"GetCapabilities WMS : HTTP {cap.status_code}, "
          f"{sum(f'<Name>{n}</Name>' in cap.text for n in COUCHES)} couche(s) annoncée(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
