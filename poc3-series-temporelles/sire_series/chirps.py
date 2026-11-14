"""Lecture de CHIRPS v2.0 mensuel directement sur l'IRI Data Library.

La donnée est consultée à la source (niveau d'intégration 1 ou 2) : seul
l'extrait utile (emprise de Madagascar, période demandée) est transféré, grâce
au langage de requête Ingrid de l'IRI Data Library.

Remarque : l'axe temporel est exprimé en « months since 1960-01-01 », unité
que la convention CF ne décode pas automatiquement ; il est converti ici.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd
import xarray as xr

BASE = "https://iridl.ldeo.columbia.edu/SOURCES/.UCSB/.CHIRPS/.v2p0/.monthly/.global/.precipitation"
EMPRISE_MDG = (43.0, -25.8, 50.7, -11.8)
MOIS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _mois_ingrid(date: str) -> str:
    """'2024-03' -> '(Mar 2024)'."""
    a, m = date.split("-")[:2]
    return f"({MOIS[int(m) - 1]} {a})"


def url_extrait(debut: str, fin: str, emprise=EMPRISE_MDG) -> str:
    """URL Ingrid d'un extrait NetCDF (emprise et période)."""
    x0, y0, x1, y1 = emprise
    requete = (f"{BASE}/X/{x0}/{x1}/RANGEEDGES/Y/{y0}/{y1}/RANGEEDGES/"
               f"T/{_mois_ingrid(debut)}/{_mois_ingrid(fin)}/RANGEEDGES/data.nc")
    return quote(requete, safe=":/()._-")


def convertir_temps(ds: xr.Dataset) -> xr.Dataset:
    """Convertit l'axe T (mois depuis 1960-01) en dates de début de mois."""
    t = "T" if "T" in ds.coords else "time"
    valeurs = np.floor(ds[t].values.astype(float)).astype(int)
    dates = pd.to_datetime([f"{1960 + v // 12}-{v % 12 + 1:02d}-01" for v in valeurs])
    ds = ds.assign_coords({t: dates})
    return ds.rename({t: "time"}) if t != "time" else ds


def normaliser(ds: xr.Dataset) -> xr.DataArray:
    """Renvoie la pluie (mm/mois) avec des dimensions nommées time, lat, lon."""
    noms = {"X": "lon", "Y": "lat", "longitude": "lon", "latitude": "lat"}
    ds = ds.rename({k: v for k, v in noms.items() if k in ds.dims or k in ds.coords})
    if not np.issubdtype(ds["time" if "time" in ds.coords else "T"].dtype, np.datetime64):
        ds = convertir_temps(ds)
    var = "precipitation" if "precipitation" in ds else list(ds.data_vars)[0]
    da = ds[var].where(ds[var] >= 0)  # valeurs manquantes codées -9999
    da.attrs.update(units="mm/mois", source="CHIRPS v2.0 (UCSB CHC) via IRI Data Library")
    return da.sortby("lat")


def telecharger(debut: str, fin: str, cible: str | Path) -> Path:
    """Télécharge l'extrait NetCDF (quelques dizaines de Mo pour 10 ans sur Madagascar)."""
    import requests

    cible = Path(cible)
    cible.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url_extrait(debut, fin), stream=True, timeout=300) as r:
        r.raise_for_status()
        with cible.open("wb") as f:
            for bloc in r.iter_content(1 << 20):
                f.write(bloc)
    return cible


def ouvrir(chemin: str | Path) -> xr.DataArray:
    return normaliser(xr.open_dataset(chemin, decode_times=False))
