"""Export OGC WaterML 2.0 Part 1 — Timeseries (OGC 10-126r4).

Produit un document wml2:Collection contenant une observation par bassin,
dont le résultat est une wml2:MeasurementTimeseries (paires temps-valeur),
avec l'unité, le pas de temps (P1M) et l'interpolation (cumul sur la période
précédente, « PrecTotal »).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from lxml import etree

NS = {
    "wml2": "http://www.opengis.net/waterml/2.0",
    "gml": "http://www.opengis.net/gml/3.2",
    "om": "http://www.opengis.net/om/2.0",
    "sa": "http://www.opengis.net/sampling/2.0",
    "sams": "http://www.opengis.net/samplingSpatial/2.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}
SCHEMA = "http://www.opengis.net/waterml/2.0 http://schemas.opengis.net/waterml/2.0/waterml2.xsd"
INTERP_CUMUL = "http://www.opengis.net/def/waterml/2.0/interpolationType/PrecTotal"


def _q(prefixe: str, nom: str) -> str:
    return f"{{{NS[prefixe]}}}{nom}"


def _sub(parent, prefixe, nom, texte=None, **attrs):
    e = etree.SubElement(parent, _q(*((prefixe, nom))))
    for k, v in attrs.items():
        p, n = k.split("__") if "__" in k else (None, k)
        e.set(_q(p, n) if p else n, str(v))
    if texte is not None:
        e.text = str(texte)
    return e


def collection(series: pd.DataFrame, id_col: str = "hybas_id", valeur_col: str = "pluie_mm",
               centroides: dict | None = None, unite: str = "mm",
               propriete: str = "Précipitation mensuelle cumulée",
               source: str = "CHIRPS v2.0 via IRI Data Library, agrégé par bassin (POC SIRE)") -> bytes:
    """Construit le document WaterML 2.0 et le renvoie en octets UTF-8."""
    racine = etree.Element(_q("wml2", "Collection"), nsmap=NS)
    racine.set(_q("xsi", "schemaLocation"), SCHEMA)
    racine.set(_q("gml", "id"), "sire.collection")

    meta = _sub(racine, "wml2", "metadata")
    doc = _sub(meta, "wml2", "DocumentMetadata")
    doc.set(_q("gml", "id"), "sire.doc")
    _sub(doc, "wml2", "generationDate", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    _sub(doc, "wml2", "generationSystem", source)

    for k, grp in series.groupby(id_col):
        grp = grp.sort_values("date")
        membre = _sub(racine, "wml2", "observationMember")
        obs = _sub(membre, "om", "OM_Observation")
        obs.set(_q("gml", "id"), f"obs.{k}")

        debut, fin = grp["date"].min(), grp["date"].max() + pd.offsets.MonthEnd(0)
        tp = _sub(_sub(obs, "om", "phenomenonTime"), "gml", "TimePeriod")
        tp.set(_q("gml", "id"), f"tp.{k}")
        _sub(tp, "gml", "beginPosition", debut.date().isoformat())
        _sub(tp, "gml", "endPosition", fin.date().isoformat())
        ti = _sub(_sub(obs, "om", "resultTime"), "gml", "TimeInstant")
        ti.set(_q("gml", "id"), f"rt.{k}")
        _sub(ti, "gml", "timePosition", fin.date().isoformat())

        _sub(obs, "om", "procedure", xlink__href="https://www.chc.ucsb.edu/data/chirps", xlink__title=source)
        _sub(obs, "om", "observedProperty", xlink__href="http://www.opengis.net/def/property/OGC/0/Precipitation",
             xlink__title=propriete)

        # Entité d'échantillonnage : le bassin versant (représenté par son centroïde)
        foi = _sub(obs, "om", "featureOfInterest")
        mp = _sub(foi, "wml2", "MonitoringPoint")
        mp.set(_q("gml", "id"), f"mp.{k}")
        _sub(mp, "gml", "name", f"Bassin versant {k}")
        _sub(mp, "sa", "sampledFeature", xlink__href=f"urn:sire:bassin:{k}")
        if centroides and k in centroides:
            forme = _sub(mp, "sams", "shape")
            pt = _sub(forme, "gml", "Point", srsName="urn:ogc:def:crs:EPSG::4326")
            pt.set(_q("gml", "id"), f"pt.{k}")
            lon, lat = centroides[k]
            _sub(pt, "gml", "pos", f"{lat:.5f} {lon:.5f}")

        res = _sub(obs, "om", "result")
        ts = _sub(res, "wml2", "MeasurementTimeseries")
        ts.set(_q("gml", "id"), f"ts.{k}")
        md = _sub(_sub(ts, "wml2", "metadata"), "wml2", "MeasurementTimeseriesMetadata")
        _sub(md, "wml2", "temporalExtent", xlink__href=f"#tp.{k}")
        _sub(md, "wml2", "spacing", "P1M")
        dpm = _sub(_sub(ts, "wml2", "defaultPointMetadata"), "wml2", "DefaultTVPMeasurementMetadata")
        _sub(dpm, "wml2", "uom", code=unite)
        _sub(dpm, "wml2", "interpolationType", xlink__href=INTERP_CUMUL, xlink__title="Cumul sur la période précédente")

        for d, v in zip(grp["date"], grp[valeur_col]):
            tvp = _sub(_sub(ts, "wml2", "point"), "wml2", "MeasurementTVP")
            _sub(tvp, "wml2", "time", (d + pd.offsets.MonthEnd(0)).date().isoformat())
            val = _sub(tvp, "wml2", "value", None if pd.isna(v) else f"{v:.2f}")
            if pd.isna(v):
                val.set(_q("xsi", "nil"), "true")
    return etree.tostring(racine, xml_declaration=True, encoding="UTF-8", pretty_print=True)
