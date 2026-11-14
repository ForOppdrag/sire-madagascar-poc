"""Agrégation de la pluie maillée par bassin versant.

Méthode : chaque cellule CHIRPS (0,05°) est rattachée au bassin qui contient
son centre ; la pluie du bassin est la moyenne des cellules, pondérée par le
cosinus de la latitude (surface réelle des cellules). Un bassin trop petit pour
contenir un centre de cellule reçoit la valeur de la cellule la plus proche de
son centroïde.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr


def rattacher_cellules(da: xr.DataArray, bassins: gpd.GeoDataFrame, id_col: str) -> pd.DataFrame:
    lon, lat = np.meshgrid(da["lon"].values, da["lat"].values)
    centres = gpd.GeoDataFrame(
        {"i_lat": np.repeat(np.arange(da.sizes["lat"]), da.sizes["lon"]),
         "i_lon": np.tile(np.arange(da.sizes["lon"]), da.sizes["lat"])},
        geometry=gpd.points_from_xy(lon.ravel(), lat.ravel()), crs=4326)
    b = bassins.to_crs(4326)[[id_col, "geometry"]]
    lien = gpd.sjoin(centres, b, predicate="within", how="inner")[["i_lat", "i_lon", id_col]]

    manquants = set(b[id_col]) - set(lien[id_col])
    if manquants:
        petits = b[b[id_col].isin(manquants)].copy()
        c = petits.geometry.representative_point()
        lignes = [{"i_lat": int(np.abs(da["lat"].values - p.y).argmin()),
                   "i_lon": int(np.abs(da["lon"].values - p.x).argmin()), id_col: k}
                  for k, p in zip(petits[id_col], c)]
        lien = pd.concat([lien, pd.DataFrame(lignes)], ignore_index=True)
    return lien


def pluie_par_bassin(da: xr.DataArray, bassins: gpd.GeoDataFrame, id_col: str = "hybas_id") -> pd.DataFrame:
    """Table longue : id du bassin, date, pluie moyenne (mm/mois), nb de cellules."""
    lien = rattacher_cellules(da, bassins, id_col)
    valeurs = da.transpose("time", "lat", "lon").values          # (t, y, x)
    poids_lat = np.cos(np.deg2rad(da["lat"].values))
    sorties = []
    for k, grp in lien.groupby(id_col):
        iy, ix = grp["i_lat"].to_numpy(), grp["i_lon"].to_numpy()
        v = valeurs[:, iy, ix]                                    # (t, n)
        w = np.broadcast_to(poids_lat[iy], v.shape)
        masque = ~np.isnan(v)
        moy = np.where(masque.any(1), (np.nan_to_num(v) * w * masque).sum(1)
                       / np.maximum((w * masque).sum(1), 1e-12), np.nan)
        sorties.append(pd.DataFrame({id_col: k, "date": pd.to_datetime(da["time"].values),
                                     "pluie_mm": np.round(moy, 2), "nb_cellules": len(grp)}))
    return pd.concat(sorties, ignore_index=True).sort_values([id_col, "date"]).reset_index(drop=True)
