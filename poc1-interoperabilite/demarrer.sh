#!/usr/bin/env bash
# Démarrage complet du POC 1 : données, services, chargement, publication.
# Prérequis : Docker (avec docker compose), Python 3.10+ avec les paquets de requirements.txt
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { cp .env.exemple .env; echo "Fichier .env créé : changez les mots de passe puis relancez."; exit 1; }

echo "1/5  Préparation des données publiques (HydroSHEDS, COD-AB)…"
python3 scripts/preparer_donnees.py "$@" || echo "   (certaines couches manquent : voir les messages ci-dessus)"

echo "2/5  Points d'eau fictifs du producteur simulé et catalogue…"
mkdir -p data
if [ ! -f data/points_eau_fictifs.geojson ]; then
  python3 ../poc2-diagnostic/exemples/generer_exemples.py
  cp ../poc2-diagnostic/exemples/donnees/points_eau_fictifs.geojson data/
fi
python3 scripts/construire_catalogue.py

echo "3/5  Démarrage des services…"
docker compose up -d

echo "4/5  Chargement du GeoPackage dans PostGIS…"
docker compose run --rm gdal ogr2ogr -f PostgreSQL "PG:" /data/sire.gpkg \
  -lco GEOMETRY_NAME=geom -lco FID=fid -nlt PROMOTE_TO_MULTI -overwrite

echo "5/5  Publication des couches dans GeoServer (attente du démarrage)…"
for i in $(seq 1 60); do
  curl -sf -o /dev/null http://localhost:8080/geoserver/web/ && break; sleep 5
done
python3 scripts/publier_geoserver.py

echo
echo "Démonstrateur prêt : http://localhost:8000"
echo "Administration GeoServer (poste local uniquement) : http://localhost:8080/geoserver"
