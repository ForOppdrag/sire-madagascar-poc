"""Contrôle de sécurité de base du démonstrateur une fois lancé.

Vérifie, depuis le poste, les mesures annoncées dans le README (repères OWASP) :
  - en-têtes de sécurité présents sur la page (CSP, nosniff, anti-cadre, referrer)
  - services en lecture seule : une écriture (POST) est refusée
  - interface d'administration et API REST de GeoServer non exposées
  - base de données non accessible depuis l'hôte
  - pas de version de logiciel divulguée dans l'en-tête Server

Usage : python scripts/verifier_securite.py [--url http://localhost:8000]
Code de retour 0 si tous les contrôles passent, 1 sinon.
"""

from __future__ import annotations

import argparse
import re
import socket
import sys
from dataclasses import dataclass

import requests

EN_TETES = {
    "Content-Security-Policy": None,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": None,
}


@dataclass
class Resultat:
    controle: str
    ok: bool
    detail: str = ""


def controler(url: str, hote_db: str = "127.0.0.1", port_db: int = 5432) -> list[Resultat]:
    url = url.rstrip("/")
    s = requests.Session()
    res: list[Resultat] = []

    r = s.get(url + "/", timeout=15)
    for nom, attendu in EN_TETES.items():
        v = r.headers.get(nom)
        ok = v is not None and (attendu is None or v.lower() == attendu.lower())
        res.append(Resultat(f"En-tête {nom}", ok, v or "absent"))

    serveur = r.headers.get("Server", "")
    res.append(Resultat("Version du serveur non divulguée", not re.search(r"\d", serveur), serveur or "absent"))

    for chemin in ("/geoserver/web/", "/geoserver/rest/workspaces"):
        c = s.get(url + chemin, timeout=15, allow_redirects=False)
        res.append(Resultat(f"Accès refusé à {chemin}", c.status_code in (401, 403, 404), f"HTTP {c.status_code}"))

    for chemin in ("/geoserver/sire/wfs", "/catalogue/collections/jeux_donnees/items",
                   "/producteur/collections/points_eau/items"):
        c = s.post(url + chemin, json={"test": "écriture"}, timeout=15)
        res.append(Resultat(f"Écriture refusée sur {chemin}", c.status_code in (403, 405), f"HTTP {c.status_code}"))

    with socket.socket() as so:
        so.settimeout(2)
        ouvert = so.connect_ex((hote_db, port_db)) == 0
    res.append(Resultat(f"Base non accessible sur {hote_db}:{port_db}", not ouvert, "port ouvert" if ouvert else "port fermé"))
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    a = ap.parse_args()
    res = controler(a.url)
    for r in res:
        print(f"{'OK   ' if r.ok else 'ÉCHEC'}  {r.controle:55s} {r.detail}")
    echecs = sum(not r.ok for r in res)
    print(f"\n{len(res) - echecs}/{len(res)} contrôles réussis")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
