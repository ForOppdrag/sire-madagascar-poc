"""Génère des jeux de données FICTIFS pour démontrer le kit de diagnostic.

Les valeurs sont synthétiques et ne représentent aucune donnée réelle d'une
institution malgache. Des défauts typiques y sont volontairement introduits :
inversion lat/lon, doublons, valeurs négatives, dates en texte, systèmes de
coordonnées différents, pas de temps hétérogènes, géométrie invalide.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, Polygon

ICI = Path(__file__).parent / "donnees"
rng = np.random.default_rng(42)


def stations() -> pd.DataFrame:
    df = pd.DataFrame({
        "code_station": [f"ST{i:03d}" for i in range(1, 21)],
        "nom": [f"Station fictive {i}" for i in range(1, 21)],
        "latitude": rng.uniform(-24.5, -13.0, 20).round(5),
        "longitude": rng.uniform(44.0, 49.5, 20).round(5),
        "bassin": rng.choice(["Ikopa", "Betsiboka", "Mangoro", "Onilahy"], 20),
        "date_installation": pd.date_range("1995-01-01", periods=20, freq="400D").strftime("%d/%m/%Y"),
    })
    df.loc[4, ["latitude", "longitude"]] = df.loc[4, ["longitude", "latitude"]].values  # inversion
    df.loc[7, "bassin"] = None
    return pd.concat([df, df.iloc[[2]]], ignore_index=True)  # doublon


def pluie_mensuelle() -> pd.DataFrame:
    dates = pd.date_range("2018-01-01", "2023-12-01", freq="MS")
    lignes = [{"station_id": f"ST{s:03d}", "date": d.strftime("%Y-%m-%d"),
               "pluie_mm": round(max(0, rng.gamma(2, 60)), 1)}
              for s in range(1, 11) for d in dates]
    df = pd.DataFrame(lignes)
    df.loc[15, "pluie_mm"] = -12.0  # valeur impossible
    df.loc[rng.choice(len(df), 40, replace=False), "pluie_mm"] = np.nan
    return df


def debits_journaliers() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    return pd.DataFrame({
        "code_station": np.repeat(["ST001", "ST002", "ST003"], len(dates)),
        "date": np.tile(dates, 3),
        "debit_m3s": rng.lognormal(3, 0.6, 3 * len(dates)).round(2),
    })


def bassins() -> gpd.GeoDataFrame:
    polys = [
        Polygon([(47.0, -19.5), (48.0, -19.5), (48.0, -18.5), (47.0, -18.5)]),
        Polygon([(46.0, -18.0), (47.5, -18.0), (47.5, -16.0), (46.0, -16.0)]),
        Polygon([(48.0, -20.5), (49.0, -19.5), (48.0, -19.5), (49.0, -20.5)]),  # « nœud papillon » invalide
    ]
    g = gpd.GeoDataFrame({"code_bassin": ["B01", "B02", "B03"],
                          "nom": ["Bassin fictif A", "Bassin fictif B", "Bassin fictif C"],
                          "superficie_km2": [12000, 31000, None]},
                         geometry=polys, crs="EPSG:4326")
    return g.to_crs("EPSG:32738")  # UTM 38S : système différent des autres sources


def points_eau() -> gpd.GeoDataFrame:
    pts = [Point(rng.uniform(44.0, 49.5), rng.uniform(-24.5, -13.0)) for _ in range(30)]
    return gpd.GeoDataFrame({"id_point": range(1, 31),
                             "type": rng.choice(["puits", "forage", "source"], 30),
                             "fonctionnel": rng.choice(["oui", "non", None], 30)},
                            geometry=pts, crs="EPSG:4326")


if __name__ == "__main__":
    ICI.mkdir(exist_ok=True)
    stations().to_csv(ICI / "stations_fictives.csv", index=False)
    pluie_mensuelle().to_csv(ICI / "pluie_mensuelle_fictive.csv", index=False, sep=";")
    debits_journaliers().to_excel(ICI / "debits_journaliers_fictifs.xlsx", index=False)
    bassins().to_file(ICI / "bassins_fictifs.gpkg", driver="GPKG")
    points_eau().to_file(ICI / "points_eau_fictifs.geojson", driver="GeoJSON")
    print("Jeux fictifs écrits dans", ICI)
