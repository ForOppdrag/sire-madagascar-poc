"""Tests du kit de diagnostic (pytest)."""

import sys
from datetime import date
from pathlib import Path

import pytest
from lxml import etree

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "exemples"))

import generer_exemples as gen  # noqa: E402
from sire_diag import compatibility, dictionary, metadata  # noqa: E402
from sire_diag.inventory import Inventaire, JeuDonnees, Systeme  # noqa: E402
from sire_diag.profiler import deviner_unite, profiler  # noqa: E402

AUJ = date(2026, 11, 14)


@pytest.fixture(scope="module")
def donnees(tmp_path_factory):
    d = tmp_path_factory.mktemp("donnees")
    gen.stations().to_csv(d / "stations.csv", index=False)
    gen.pluie_mensuelle().to_csv(d / "pluie.csv", index=False, sep=";")
    gen.debits_journaliers().to_excel(d / "debits.xlsx", index=False)
    gen.bassins().to_file(d / "bassins.gpkg", driver="GPKG")
    gen.points_eau().to_file(d / "points.geojson", driver="GeoJSON")
    return d


def test_unites():
    assert deviner_unite("pluie_mm") == "mm"
    assert deviner_unite("Débit_m3s") == "m³/s"
    assert deviner_unite("nom") is None


def test_stations_detecte_defauts(donnees):
    p = profiler(donnees / "stations.csv", aujourd_hui=AUJ)
    assert p.nb_lignes == 21
    assert p.lignes_dupliquees == 1
    assert p.geographique and p.hors_madagascar == 1          # lat/lon inversées
    bassin = next(c for c in p.colonnes if c.nom == "bassin")
    assert bassin.nb_manquants == 1
    assert any("date stockée en texte" in a for a in p.alertes)
    assert 0 < p.score_qualite < 100


def test_pluie_temps_et_negatifs(donnees):
    p = profiler(donnees / "pluie.csv", aujourd_hui=AUJ)
    assert p.colonne_temporelle == "date"
    assert p.pas_de_temps == "mensuel"
    assert p.date_max == "2023-12-01"
    assert p.anciennete_jours > 365
    pluie = next(c for c in p.colonnes if c.nom == "pluie_mm")
    assert pluie.nb_negatifs_suspects == 1 and pluie.unite_devinee == "mm"


def test_debits_journaliers(donnees):
    p = profiler(donnees / "debits.xlsx", aujourd_hui=AUJ)
    assert p.pas_de_temps == "journalier"


def test_geo_crs_et_invalide(donnees):
    p = profiler(donnees / "bassins.gpkg", aujourd_hui=AUJ)
    assert "32738" in p.crs
    assert p.geometries_invalides == 1
    assert p.emprise[0] == pytest.approx(46.0, abs=0.01)     # emprise rendue en WGS 84


def test_compatibilite(donnees):
    st = profiler(donnees / "stations.csv", aujourd_hui=AUJ)
    pl = profiler(donnees / "pluie.csv", aujourd_hui=AUJ)
    db = profiler(donnees / "debits.xlsx", aujourd_hui=AUJ)
    bs = profiler(donnees / "bassins.gpkg", aujourd_hui=AUJ)
    pt = profiler(donnees / "points.geojson", aujourd_hui=AUJ)

    r = compatibility.comparer(st, db)
    assert r.cle_jointure == "code_station"
    r2 = compatibility.comparer(pl, db)
    assert r2.meme_pas_de_temps is False and r2.periodes_recouvrantes is False
    assert r2.verdict == "non mutualisable en l'état"
    r3 = compatibility.comparer(bs, pt)
    assert r3.meme_crs is False and r3.verdict == "partiellement compatible"

    r4 = compatibility.comparer(pl, st)
    assert r4.cle_jointure == "station_id ↔ code_station" and r4.verdict == "partiellement compatible"

    m = compatibility.matrice([st, pl, db, bs, pt])
    assert m.shape == (5, 5)


def test_dictionnaire_et_metadonnees(donnees, tmp_path):
    p = profiler(donnees / "stations.csv", aujourd_hui=AUJ)
    sorties = dictionary.ecrire(p, tmp_path)
    assert {s.suffix for s in sorties} == {".md", ".json", ".xlsx"}
    assert "Dictionnaire de données" in sorties[0].read_text(encoding="utf-8")
    xml = metadata.fiche_iso19139(p, "Stations fictives", "Organisation fictive")
    racine = etree.fromstring(xml.encode("utf-8"))
    ns = {"gmd": "http://www.isotc211.org/2005/gmd", "gco": "http://www.isotc211.org/2005/gco"}
    assert racine.find(".//gmd:title/gco:CharacterString", ns).text == "Stations fictives"
    assert racine.find(".//gmd:westBoundLongitude/gco:Decimal", ns) is not None


def test_inventaire(tmp_path):
    inv = Inventaire(tmp_path / "inv.sqlite")
    inv.ajouter_institution("MEAH", "Ministère (exemple)")
    inv.ajouter_systeme(Systeme(code="SEAM", nom="SE&AM", institution="MEAH", statut="actif"))
    inv.ajouter_jeu(JeuDonnees(code="J1", titre="Points d'eau", systeme="SEAM", producteur="MEAH",
                               acces="api", niveau_integration_cible=2))
    inv.ajouter_jeu(JeuDonnees(code="J2", titre="Usagers", producteur="MEAH", acces="fichier",
                               donnees_personnelles=True, niveau_integration_cible=0))
    s = inv.synthese()
    assert s["nb_jeux"] == 2 and s["jeux_avec_donnees_personnelles"] == 1
    assert s["repartition_niveau_cible"] == {"Exposé": 1, "Catalogué": 1}
    assert len(inv.exporter_csv(tmp_path / "export")) == 2
    inv.fermer()
