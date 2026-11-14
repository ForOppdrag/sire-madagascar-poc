"""Tests hors ligne du POC 3 (données synthétiques au format CHIRPS / IRI)."""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from lxml import etree
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sire_series import agregation, chirps, qualite, sensorthings, waterml  # noqa: E402


@pytest.fixture
def ds_iri():
    """Jeu imitant l'extrait NetCDF de l'IRI : axes X, Y, T en mois depuis 1960."""
    t = np.arange(780, 792) + 0.5          # janv. à déc. 2025 (780 = 65 ans x 12)
    y = np.round(np.arange(-20.0, -17.0, 0.5), 2)[::-1]   # ordre décroissant comme l'IRI
    x = np.round(np.arange(46.0, 49.0, 0.5), 2)
    v = np.ones((len(t), len(y), len(x))) * np.arange(1, 13)[:, None, None]
    v[:, :, x >= 47.5] *= 10                 # l'est 10 fois plus arrosé
    v[0, 0, 0] = -9999.0                     # valeur manquante codée
    return xr.Dataset({"precipitation": (("T", "Y", "X"), v)}, coords={"T": t, "Y": y, "X": x})


@pytest.fixture
def bassins():
    return gpd.GeoDataFrame({"hybas_id": [101, 202, 303]}, geometry=[
        Polygon([(45.9, -20.1), (47.4, -20.1), (47.4, -17.1), (45.9, -17.1)]),   # ouest
        Polygon([(47.6, -20.1), (49.1, -20.1), (49.1, -17.1), (47.6, -17.1)]),   # est
        Polygon([(46.01, -18.99), (46.02, -18.99), (46.02, -18.98), (46.01, -18.98)]),  # minuscule
    ], crs=4326)


def test_url_ingrid():
    u = chirps.url_extrait("2015-01", "2024-12")
    assert u.startswith(chirps.BASE)
    assert "T/(Jan%202015)/(Dec%202024)/RANGEEDGES/data.nc" in u
    assert "X/43.0/50.7/RANGEEDGES/Y/-25.8/-11.8/RANGEEDGES" in u


def test_normalisation(ds_iri):
    da = chirps.normaliser(ds_iri)
    assert set(da.dims) == {"time", "lat", "lon"}
    assert pd.Timestamp(da.time.values[0]) == pd.Timestamp("2025-01-01")
    assert float(da.lat[0]) < float(da.lat[-1])            # trié du sud au nord
    assert int(da.isnull().sum()) == 1                      # -9999 -> manquant


def test_agregation(ds_iri, bassins):
    da = chirps.normaliser(ds_iri)
    s = agregation.pluie_par_bassin(da, bassins)
    assert set(s["hybas_id"]) == {101, 202, 303}
    juin = s[s["date"] == "2025-06-01"].set_index("hybas_id")["pluie_mm"]
    assert juin[101] == pytest.approx(6.0)
    assert juin[202] == pytest.approx(60.0)
    assert s[s.hybas_id == 303]["nb_cellules"].iloc[0] == 1   # repli sur la cellule la plus proche


def test_waterml(ds_iri, bassins):
    s = agregation.pluie_par_bassin(chirps.normaliser(ds_iri), bassins)
    xml = waterml.collection(s, centroides={101: (46.6, -18.6)})
    racine = etree.fromstring(xml)
    ns = waterml.NS
    assert racine.tag == f"{{{ns['wml2']}}}Collection"
    assert len(racine.findall(".//wml2:MeasurementTimeseries", ns)) == 3
    assert len(racine.findall(".//wml2:MeasurementTVP", ns)) == 36
    assert racine.find(".//wml2:uom", ns).get("code") == "mm"
    assert racine.find(".//gml:pos", ns).text == "-18.60000 46.60000"
    # identifiants gml:id uniques (exigence GML)
    ids = racine.xpath("//@gml:id", namespaces=ns)
    assert len(ids) == len(set(ids))


def test_charges_sensorthings(bassins):
    t = sensorthings.thing(101, bassins.geometry[0])
    assert t["Locations"][0]["location"]["type"] == "Polygon"
    d = sensorthings.datastream(101, 1, 2, 3)
    assert d["unitOfMeasurement"]["symbol"] == "mm" and d["Thing"] == {"@iot.id": 1}
    serie = pd.DataFrame({"date": pd.to_datetime(["2025-01-01", "2025-02-01"]), "pluie_mm": [12.5, np.nan]})
    obs = sensorthings.observations(serie)
    assert obs == [{"phenomenonTime": "2025-01-01T00:00:00Z/2025-02-01T00:00:00Z",
                    "resultTime": "2025-02-01T00:00:00Z", "result": 12.5}]


def test_controle_qualite():
    dates = pd.date_range("2015-01-01", "2024-12-01", freq="MS")
    rng = np.random.default_rng(0)
    base = np.asarray(100 + 80 * np.sin(2 * np.pi * (np.asarray(dates.month) - 1) / 12))
    v = base + rng.normal(0, 10, len(dates))
    v[50] = base[50] + 400            # valeur aberrante
    v[-3:] = base[-3:] - 60           # trois derniers mois très secs
    serie = pd.DataFrame({"hybas_id": 1, "date": dates, "pluie_mm": v})
    serie = serie.drop(index=[20, 21])  # deux mois manquants
    q = qualite.controler(serie)
    assert int(q["lacune"].sum()) == 2
    assert bool(q.loc[q["date"] == dates[50], "suspect"].iloc[0])
    s = qualite.synthese(q)
    assert s.loc[0, "dernier_ips3"] <= -1.5
    assert "sécheresse" in s.loc[0, "classe_actuelle"]
    html = qualite.rapport_html(q)
    assert "<svg" in html and "IPS-3" in html


def test_classes_ips():
    assert qualite.classe_ips(-2.3) == "sécheresse extrême"
    assert qualite.classe_ips(-1.2) == "sécheresse modérée"
    assert qualite.classe_ips(0.2) == "normal"
