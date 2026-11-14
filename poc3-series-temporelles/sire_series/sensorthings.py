"""Chargement des séries dans un serveur OGC SensorThings API (FROST-Server).

Modèle SensorThings utilisé :
    Thing            = bassin versant (avec sa Location : le polygone du bassin)
    Sensor           = produit CHIRPS v2.0 (estimation satellite + stations)
    ObservedProperty = précipitation mensuelle cumulée
    Datastream       = une série par bassin, unité mm
    Observation      = une valeur mensuelle
Les fonctions de construction des charges utiles sont pures (testables sans serveur).
"""

from __future__ import annotations

import json

import geopandas as gpd
import pandas as pd

CAPTEUR = {
    "name": "CHIRPS v2.0 mensuel",
    "description": "Climate Hazards Group InfraRed Precipitation with Station data, 0,05°",
    "encodingType": "text/html",
    "metadata": "https://www.chc.ucsb.edu/data/chirps",
}
PROPRIETE = {
    "name": "Précipitation mensuelle",
    "definition": "http://www.opengis.net/def/property/OGC/0/Precipitation",
    "description": "Cumul de précipitation sur le mois",
}
UNITE = {"name": "millimètre", "symbol": "mm", "definition": "http://qudt.org/vocab/unit/MilliM"}


def thing(id_bassin, geometrie, proprietes: dict | None = None) -> dict:
    return {
        "name": f"Bassin versant {id_bassin}",
        "description": "Bassin versant HydroBASINS (niveau 6)",
        "properties": {"id_bassin": str(id_bassin), **(proprietes or {})},
        "Locations": [{
            "name": f"Emprise du bassin {id_bassin}",
            "description": "Polygone du bassin versant",
            "encodingType": "application/geo+json",
            "location": json.loads(gpd.GeoSeries([geometrie], crs=4326).to_json())["features"][0]["geometry"],
        }],
    }


def datastream(id_bassin, id_thing: int, id_capteur: int, id_propriete: int) -> dict:
    return {
        "name": f"Pluie mensuelle — bassin {id_bassin}",
        "description": "Moyenne CHIRPS des cellules du bassin, pondérée par la latitude",
        "observationType": "http://www.opengis.net/def/observationType/OGC-OM/2.0/OM_Measurement",
        "unitOfMeasurement": UNITE,
        "Thing": {"@iot.id": id_thing},
        "Sensor": {"@iot.id": id_capteur},
        "ObservedProperty": {"@iot.id": id_propriete},
    }


def observations(serie: pd.DataFrame, valeur_col: str = "pluie_mm") -> list[dict]:
    """Une observation par mois ; le phenomenonTime est l'intervalle du mois."""
    obs = []
    for d, v in zip(serie["date"], serie[valeur_col]):
        if pd.isna(v):
            continue
        fin = d + pd.offsets.MonthBegin(1)
        obs.append({"phenomenonTime": f"{d:%Y-%m-%dT00:00:00Z}/{fin:%Y-%m-%dT00:00:00Z}",
                    "resultTime": f"{fin:%Y-%m-%dT00:00:00Z}", "result": float(v)})
    return obs


class Client:
    """Client minimal SensorThings (création d'entités, envoi d'observations par lots)."""

    def __init__(self, racine: str, auth: tuple[str, str] | None = None):
        import requests

        self.racine = racine.rstrip("/")
        self.s = requests.Session()
        if auth:
            self.s.auth = auth

    def creer(self, entite: str, charge: dict) -> int:
        r = self.s.post(f"{self.racine}/{entite}", json=charge, timeout=60)
        r.raise_for_status()
        # FROST renvoie l'URL de l'entité créée : …/Things(42)
        return int(r.headers["Location"].rsplit("(", 1)[1].rstrip(")"))

    def envoyer_lot(self, id_datastream: int, obs: list[dict], taille: int = 500) -> int:
        """Envoi groupé via l'extension « CreateObservations » (format dataArray)."""
        n = 0
        for i in range(0, len(obs), taille):
            lot = obs[i:i + taille]
            corps = [{
                "Datastream": {"@iot.id": id_datastream},
                "components": ["phenomenonTime", "resultTime", "result"],
                "dataArray": [[o["phenomenonTime"], o["resultTime"], o["result"]] for o in lot],
            }]
            r = self.s.post(f"{self.racine}/CreateObservations", json=corps, timeout=120)
            r.raise_for_status()
            n += len(lot)
        return n
