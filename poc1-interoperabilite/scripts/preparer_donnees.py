"""Télécharge et prépare les données publiques du démonstrateur.

Sources :
  - HydroBASINS v1c, niveau 6, Afrique (WWF / HydroSHEDS)   -> couche « bassins »
  - HydroRIVERS v1.0, Afrique (WWF / HydroSHEDS)             -> couche « rivieres »
  - COD-AB Madagascar, niveau 1 (HDX, jeu « cod-ab-mdg »)     -> couche « regions »

Le résultat est un GeoPackage unique, data/sire.gpkg, découpé sur Madagascar.

Si un téléchargement échoue (adresse modifiée, réseau), téléchargez le fichier
à la main depuis la page indiquée et placez le zip dans data/brut/, puis
relancez : le script réutilise les fichiers déjà présents.

Usage : python scripts/preparer_donnees.py [--ordre-min 4] [--sans-rivieres]
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import box

ICI = Path(__file__).resolve().parents[1]
BRUT = ICI / "data" / "brut"
SORTIE = ICI / "data" / "sire.gpkg"
EMPRISE_MDG = box(43.0, -25.8, 50.7, -11.8)

SOURCES = {
    "bassins": {
        "fichier": "hybas_af_lev06_v1c.zip",
        "url": "https://data.hydrosheds.org/file/HydroBASINS/standard/hybas_af_lev06_v1c.zip",
        "page": "https://www.hydrosheds.org/products/hydrobasins",
    },
    "rivieres": {
        "fichier": "HydroRIVERS_v10_af_shp.zip",
        "url": "https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_af_shp.zip",
        "page": "https://www.hydrosheds.org/products/hydrorivers",
    },
}
HDX_API = "https://data.humdata.org/api/3/action/package_show?id=cod-ab-mdg"


def telecharger(url: str, cible: Path) -> Path:
    if cible.exists() and cible.stat().st_size > 0:
        print(f"  déjà présent : {cible.name}")
        return cible
    print(f"  téléchargement : {url}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with cible.open("wb") as f:
            for bloc in r.iter_content(1 << 20):
                f.write(bloc)
    return cible


def lire_zip(chemin: Path, motif: str = ".shp") -> gpd.GeoDataFrame:
    with zipfile.ZipFile(chemin) as z:
        noms = [n for n in z.namelist() if n.lower().endswith(motif)]
    if not noms:
        raise FileNotFoundError(f"Aucun fichier {motif} dans {chemin.name}")
    return gpd.read_file(f"zip://{chemin}!{noms[0]}", bbox=EMPRISE_MDG.bounds)


def bassins() -> gpd.GeoDataFrame:
    s = SOURCES["bassins"]
    z = telecharger(s["url"], BRUT / s["fichier"])
    g = lire_zip(z)
    g = g[g.intersects(EMPRISE_MDG)].copy()
    g = g.rename(columns=str.lower)[["hybas_id", "next_down", "sub_area", "up_area", "pfaf_id", "geometry"]]
    g["source"] = "HydroBASINS v1c (WWF/HydroSHEDS)"
    return g


def rivieres(ordre_min: int) -> gpd.GeoDataFrame:
    s = SOURCES["rivieres"]
    z = telecharger(s["url"], BRUT / s["fichier"])
    g = lire_zip(z).rename(columns=str.lower)
    g = g[(g["ord_stra"] >= ordre_min) & g.intersects(EMPRISE_MDG)].copy()
    g = g[["hyriv_id", "ord_stra", "upland_skm", "dis_av_cms", "length_km", "geometry"]]
    g["source"] = "HydroRIVERS v1.0 (WWF/HydroSHEDS)"
    return g


def regions() -> gpd.GeoDataFrame:
    cible = BRUT / "cod-ab-mdg.zip"
    if not cible.exists():
        meta = requests.get(HDX_API, timeout=60).json()["result"]["resources"]
        candidats = [r for r in meta if "shp" in (r.get("format", "") + r.get("name", "")).lower()]
        if not candidats:
            raise RuntimeError("Ressource shapefile introuvable sur HDX (cod-ab-mdg)")
        telecharger(candidats[0]["url"], cible)
    with zipfile.ZipFile(cible) as z:
        noms = [n for n in z.namelist() if n.lower().endswith(".shp") and "adm1" in n.lower()]
        interne = [n for n in z.namelist() if n.lower().endswith(".zip") and "shp" in n.lower()]
    if not noms and interne:  # certains jeux HDX contiennent un zip dans le zip
        with zipfile.ZipFile(cible) as z:
            donnees = z.read(interne[0])
        cible2 = BRUT / "cod-ab-mdg-shp.zip"
        cible2.write_bytes(donnees)
        cible = cible2
        with zipfile.ZipFile(cible) as z:
            noms = [n for n in z.namelist() if n.lower().endswith(".shp") and "adm1" in n.lower()]
    if not noms:
        raise FileNotFoundError("Couche de niveau 1 (adm1) introuvable dans le jeu COD-AB")
    g = gpd.read_file(f"zip://{cible}!{noms[0]}").to_crs(4326)
    g.columns = [c.lower() for c in g.columns]
    garder = [c for c in g.columns if c.startswith(("adm1_", "adm0_"))] + ["geometry"]
    g = g[garder].copy()
    g["source"] = "COD-AB Madagascar (BNGRC/OCHA, HDX)"
    return g


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ordre-min", type=int, default=4, help="ordre de Strahler minimal des rivières")
    ap.add_argument("--sans-rivieres", action="store_true", help="ignorer HydroRIVERS (fichier volumineux)")
    a = ap.parse_args()
    BRUT.mkdir(parents=True, exist_ok=True)
    if SORTIE.exists():
        SORTIE.unlink()

    etapes = [("bassins", bassins), ("regions", regions)]
    if not a.sans_rivieres:
        etapes.insert(1, ("rivieres", lambda: rivieres(a.ordre_min)))
    erreurs = 0
    for nom, f in etapes:
        print(f"[{nom}]")
        try:
            g = f()
            g.to_file(SORTIE, layer=nom, driver="GPKG")
            print(f"  {len(g)} objets écrits dans {SORTIE.name}:{nom}")
        except Exception as e:  # on continue avec les autres couches
            erreurs += 1
            page = SOURCES.get(nom, {}).get("page", "https://data.humdata.org/dataset/cod-ab-mdg")
            print(f"  ÉCHEC : {e}\n  -> téléchargez le zip depuis {page} et placez-le dans {BRUT}", file=sys.stderr)
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
