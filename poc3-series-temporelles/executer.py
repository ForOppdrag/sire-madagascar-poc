"""Chaîne complète du POC 3.

1. Lecture de CHIRPS mensuel à la source (IRI Data Library), extrait Madagascar
2. Agrégation de la pluie par bassin versant (HydroBASINS, issus du POC 1)
3. Contrôle qualité (lacunes, valeurs suspectes, IPS-3 simplifié) et rapport HTML
4. Export CSV et OGC WaterML 2.0
5. (option) Chargement dans un serveur OGC SensorThings API

Exemples :
    python executer.py --debut 2015-01 --fin 2024-12
    python executer.py --netcdf sorties/chirps_mdg.nc --sensorthings http://localhost:8081/FROST-Server/v1.1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd

from sire_series import agregation, chirps, qualite, sensorthings, waterml

ICI = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(description="POC 3 — séries temporelles normalisées")
    ap.add_argument("--debut", default="2015-01")
    ap.add_argument("--fin", default="2024-12")
    ap.add_argument("--netcdf", type=Path, help="extrait CHIRPS déjà téléchargé (sinon téléchargement)")
    ap.add_argument("--bassins", type=Path, default=ICI.parent / "poc1-interoperabilite" / "data" / "sire.gpkg")
    ap.add_argument("--couche", default="bassins")
    ap.add_argument("--id", default="hybas_id")
    ap.add_argument("--sortie", type=Path, default=ICI / "sorties")
    ap.add_argument("--sensorthings", help="URL racine SensorThings, ex. http://localhost:8081/FROST-Server/v1.1")
    a = ap.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=True)

    nc = a.netcdf or a.sortie / f"chirps_mdg_{a.debut}_{a.fin}.nc"
    if not nc.exists():
        print(f"Téléchargement de l'extrait CHIRPS :\n  {chirps.url_extrait(a.debut, a.fin)}")
        chirps.telecharger(a.debut, a.fin, nc)
    pluie = chirps.ouvrir(nc)
    print(f"CHIRPS : {pluie.sizes['time']} mois, grille {pluie.sizes['lat']} x {pluie.sizes['lon']}")

    bassins = gpd.read_file(a.bassins, layer=a.couche).to_crs(4326)
    series = agregation.pluie_par_bassin(pluie, bassins, a.id)
    csv = a.sortie / "pluie_mensuelle_par_bassin.csv"
    series.to_csv(csv, index=False)
    print(f"{series[a.id].nunique()} bassins, {len(series)} valeurs -> {csv.name}")

    q = qualite.controler(series, a.id)
    q.to_csv(a.sortie / "controle_qualite_par_bassin.csv", index=False)
    (a.sortie / "controle_qualite.html").write_text(qualite.rapport_html(q, a.id), encoding="utf-8")
    s = qualite.synthese(q, a.id)
    print(f"Contrôle qualité : {int(s['lacunes'].sum())} lacune(s), {int(s['valeurs_suspectes'].sum())} valeur(s) "
          f"suspecte(s), {int((s['dernier_ips3'] <= -1).sum())} bassin(s) en sécheresse au dernier mois")

    centres = bassins.set_index(a.id).geometry.representative_point()
    xml = waterml.collection(series, a.id, centroides={k: (p.x, p.y) for k, p in centres.items()})
    (a.sortie / "pluie_mensuelle_par_bassin.waterml2.xml").write_bytes(xml)
    print("Export WaterML 2.0 écrit")

    if a.sensorthings:
        st = sensorthings.Client(a.sensorthings)
        id_capteur = st.creer("Sensors", sensorthings.CAPTEUR)
        id_prop = st.creer("ObservedProperties", sensorthings.PROPRIETE)
        total = 0
        for _, b in bassins.iterrows():
            k = b[a.id]
            serie = series[series[a.id] == k]
            if serie.empty:
                continue
            id_thing = st.creer("Things", sensorthings.thing(k, b.geometry))
            id_ds = st.creer("Datastreams", sensorthings.datastream(k, id_thing, id_capteur, id_prop))
            total += st.envoyer_lot(id_ds, sensorthings.observations(serie))
        print(f"SensorThings : {total} observations chargées")
        print(f"  ex. {a.sensorthings}/Datastreams?$top=1&$expand=Observations($top=12;$orderby=phenomenonTime desc)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
