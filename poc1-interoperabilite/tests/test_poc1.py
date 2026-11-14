"""Tests hors ligne du POC 1 : préparation des données (à partir d'archives
simulées au format des sources réelles) et construction du catalogue."""

import importlib.util
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Polygon
from tinydb import TinyDB

RACINE = Path(__file__).resolve().parents[1]


def _module(nom):
    spec = importlib.util.spec_from_file_location(nom, RACINE / "scripts" / f"{nom}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[nom] = m
    spec.loader.exec_module(m)
    return m


def _zip_shp(gdf, dossier: Path, nom_shp: str, nom_zip: str) -> Path:
    d = dossier / nom_shp
    d.mkdir()
    gdf.to_file(d / f"{nom_shp}.shp")
    z = dossier / nom_zip
    with zipfile.ZipFile(z, "w") as f:
        for p in d.iterdir():
            f.write(p, f"{nom_shp}/{p.name}")
    return z


@pytest.fixture
def prep(tmp_path, monkeypatch):
    m = _module("preparer_donnees")
    monkeypatch.setattr(m, "BRUT", tmp_path)
    # Bassins au format HydroBASINS (un dans Madagascar, un en Afrique continentale)
    b = gpd.GeoDataFrame({
        "HYBAS_ID": [1, 2], "NEXT_DOWN": [0, 0], "SUB_AREA": [100.0, 200.0],
        "UP_AREA": [100.0, 200.0], "PFAF_ID": [11, 12]},
        geometry=[Polygon([(47, -19), (48, -19), (48, -18), (47, -18)]),
                  Polygon([(30, -10), (31, -10), (31, -9), (30, -9)])], crs=4326)
    _zip_shp(b, tmp_path, "hybas_af_lev06_v1c", "hybas_af_lev06_v1c.zip")
    # Rivières au format HydroRIVERS
    r = gpd.GeoDataFrame({
        "HYRIV_ID": [1, 2], "ORD_STRA": [5, 2], "UPLAND_SKM": [5000.0, 10.0],
        "DIS_AV_CMS": [120.0, 0.5], "LENGTH_KM": [10.0, 1.0]},
        geometry=[LineString([(47.1, -18.9), (47.9, -18.1)]), LineString([(47.2, -18.8), (47.3, -18.7)])], crs=4326)
    _zip_shp(r, tmp_path, "HydroRIVERS_v10_af_shp", "HydroRIVERS_v10_af_shp.zip")
    # Régions au format COD-AB (zip contenant un zip shapefile)
    reg = gpd.GeoDataFrame({"ADM1_EN": ["Analamanga"], "ADM1_PCODE": ["MG11"], "ADM0_PCODE": ["MG"]},
                           geometry=[Polygon([(47, -19.5), (48, -19.5), (48, -18), (47, -18)])], crs=4326)
    interne = _zip_shp(reg, tmp_path, "mdg_admbnda_adm1", "mdg_adm_shp.zip")
    with zipfile.ZipFile(tmp_path / "cod-ab-mdg.zip", "w") as f:
        f.write(interne, "mdg_adm_shp.zip")
    return m


def test_preparation_decoupe_et_filtre(prep):
    b = prep.bassins()
    assert list(b["hybas_id"]) == [1]                 # bassin hors Madagascar exclu
    r = prep.rivieres(ordre_min=4)
    assert list(r["hyriv_id"]) == [1]                 # petit cours d'eau filtré
    g = prep.regions()
    assert g.iloc[0]["adm1_pcode"] == "MG11"


def test_catalogue(tmp_path):
    m = _module("construire_catalogue")
    sortie = tmp_path / "cat.tinydb"
    n = m.construire(RACINE / "config" / "catalogue_source.yml", sortie)
    db = TinyDB(sortie)
    recs = db.all()
    assert n == len(recs) == 6
    niveaux = {r["id"]: r["properties"]["niveau_integration"] for r in recs}
    assert niveaux["usagers-autorisations"] == 0 and niveaux["cod-ab-mdg-adm1"] == 4
    assert all("_metadata-anytext" in r["properties"] for r in recs)
    db.close()


def test_verifier_securite_contre_serveur_simule():
    """Serveur local imitant le mandataire nginx configuré (en-têtes, lecture seule)."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Mandataire(BaseHTTPRequestHandler):
        def _entetes(self, code):
            self.send_response(code)
            self.send_header("Content-Security-Policy", "default-src 'self'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.end_headers()

        def version_string(self):
            return "nginx"

        def do_GET(self):
            self._entetes(403 if self.path.startswith(("/geoserver/web", "/geoserver/rest")) else 200)

        def do_POST(self):
            self._entetes(403)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Mandataire)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    m = _module("verifier_securite")
    res = m.controler(f"http://127.0.0.1:{srv.server_port}", port_db=1)  # port 1 : fermé
    srv.shutdown()
    assert all(r.ok for r in res), [r for r in res if not r.ok]
    assert len(res) == 11
