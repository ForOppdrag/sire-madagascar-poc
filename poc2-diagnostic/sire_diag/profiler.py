"""Profilage automatisé de la qualité d'un jeu de données.

Dimensions mesurées (inspirées des éléments de qualité de l'ISO 19157-1) :
    - complétude  : part de valeurs renseignées
    - unicité     : lignes dupliquées, doublons sur les identifiants candidats
    - validité    : géométries invalides, coordonnées hors de Madagascar,
                    valeurs physiquement impossibles (pluie ou débit négatifs)
    - actualité   : date la plus récente et ancienneté en jours
    - cohérence   : pas de temps dominant, unités devinées d'après les noms de champs
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

# Emprise approximative de Madagascar (WGS 84), îles proches comprises
MADAGASCAR_BBOX = (43.0, -25.8, 50.7, -11.8)  # (lon_min, lat_min, lon_max, lat_max)

FORMATS_GEO = {".shp", ".gpkg", ".geojson", ".json", ".kml", ".gml"}
FORMATS_TAB = {".csv", ".txt", ".tsv", ".xlsx", ".xls", ".parquet"}

# Indices d'unités tirés des noms de colonnes (minuscules, sans accents)
UNITES = [
    (r"(^|_)(m3_?s|m3s|debit)($|_)", "m³/s"),
    (r"(^|_)(mm|pluie|precip|precipitation|rr)($|_)", "mm"),
    (r"(^|_)(km2|superficie_km2)($|_)", "km²"),
    (r"(^|_)(ha|superficie_ha)($|_)", "ha"),
    (r"(^|_)(temp|temperature|t_?c)($|_)", "°C"),
    (r"(^|_)(cote|hauteur|niveau|h_?m)($|_)", "m"),
    (r"(^|_)(lat|latitude)($|_)", "degrés (latitude)"),
    (r"(^|_)(lon|lng|long|longitude)($|_)", "degrés (longitude)"),
    (r"(^|_)(ph)($|_)", "unité pH"),
    (r"(^|_)(conductivite|ec)($|_)", "µS/cm"),
]
NOMS_LAT = {"lat", "latitude", "y", "lat_dd"}
NOMS_LON = {"lon", "lng", "long", "longitude", "x", "lon_dd"}
NONNEGATIFS = re.compile(r"(pluie|precip|debit|m3|mm|superficie|population|volume)")


def _norm(nom: str) -> str:
    tab = str.maketrans("éèêëàâäîïôöùûüç", "eeeeaaaiioouuuc")
    return re.sub(r"[^a-z0-9]+", "_", str(nom).lower().translate(tab)).strip("_")


def deviner_unite(nom_colonne: str) -> str | None:
    n = _norm(nom_colonne)
    for motif, unite in UNITES:
        if re.search(motif, n):
            return unite
    return None


@dataclass
class ProfilColonne:
    nom: str
    type_infere: str
    nb_valeurs: int
    nb_manquants: int
    taux_completude: float
    nb_distincts: int
    identifiant_candidat: bool
    unite_devinee: str | None = None
    minimum: str | None = None
    maximum: str | None = None
    moyenne: float | None = None
    nb_negatifs_suspects: int = 0
    exemples: list[str] = field(default_factory=list)


@dataclass
class Profil:
    source: str
    nb_lignes: int
    nb_colonnes: int
    colonnes: list[ProfilColonne]
    lignes_dupliquees: int
    taux_completude_global: float
    # géographie
    geographique: bool = False
    crs: str | None = None
    types_geometrie: list[str] = field(default_factory=list)
    geometries_invalides: int = 0
    geometries_vides: int = 0
    emprise: list[float] | None = None
    hors_madagascar: int = 0
    # temps
    colonne_temporelle: str | None = None
    date_min: str | None = None
    date_max: str | None = None
    pas_de_temps: str | None = None
    anciennete_jours: int | None = None
    # synthèse
    alertes: list[str] = field(default_factory=list)
    score_qualite: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


# ----------------------------------------------------------------------
def charger(chemin: str | Path, **kwargs) -> pd.DataFrame:
    """Charge un fichier tabulaire ou géographique en DataFrame / GeoDataFrame."""
    p = Path(chemin)
    ext = p.suffix.lower()
    if ext in FORMATS_GEO:
        import geopandas as gpd

        return gpd.read_file(p, **kwargs)
    if ext in {".csv", ".txt"}:
        # séparateur détecté automatiquement (virgule ou point-virgule courants)
        return pd.read_csv(p, sep=None, engine="python", **kwargs)
    if ext == ".tsv":
        return pd.read_csv(p, sep="\t", **kwargs)
    if ext in {".xlsx", ".xls"}:
        return pd.read_excel(p, **kwargs)
    if ext == ".parquet":
        return pd.read_parquet(p, **kwargs)
    raise ValueError(f"Format non pris en charge : {ext}")


def _est_texte(s: pd.Series) -> bool:
    """Vrai pour les colonnes de texte (objet ou chaîne, selon la version de pandas)."""
    return s.dtype == object or pd.api.types.is_string_dtype(s)


def _type_infere(s: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(s):
        return "booléen"
    if pd.api.types.is_integer_dtype(s):
        return "entier"
    if pd.api.types.is_float_dtype(s):
        return "décimal"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "date"
    if _est_texte(s):
        non_nuls = s.dropna().astype(str)
        if non_nuls.empty:
            return "texte"
        if pd.to_numeric(non_nuls.str.replace(",", ".", regex=False), errors="coerce").notna().mean() > 0.95:
            return "nombre stocké en texte"
        if _semble_date(non_nuls):
            return "date stockée en texte"
    return "texte"


def _parse_dates(s: pd.Series) -> pd.Series:
    """Convertit en dates : ISO (AAAA-MM-JJ) d'abord, sinon format jour/mois/année courant à Madagascar."""
    txt = s.astype(str).str.strip()
    if txt[s.notna()].str.match(r"^\d{4}-\d{2}-\d{2}").mean() > 0.9:
        return pd.to_datetime(txt, errors="coerce", format="ISO8601")
    return pd.to_datetime(txt, errors="coerce", dayfirst=True, format="mixed")


def _semble_date(s: pd.Series) -> bool:
    echantillon = s.head(200)
    # forme attendue : chiffres séparés par - / . (ex. 2024-01-31, 31/01/2024)
    if echantillon.str.match(r"^\s*\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}").mean() < 0.9:
        return False
    return _parse_dates(echantillon).notna().mean() > 0.9


def _detecter_temps(df: pd.DataFrame) -> tuple[str | None, pd.Series | None]:
    candidats = [c for c in df.columns if c != "geometry"]
    # priorité aux colonnes déjà typées date, puis aux noms évocateurs
    for c in candidats:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            return c, df[c]
    for c in candidats:
        if re.search(r"(date|jour|time|periode|mois|annee|dt)", _norm(c)) and _est_texte(df[c]):
            parse = _parse_dates(df[c])
            if parse.notna().mean() > 0.8:
                return c, parse
    return None, None


def _pas_de_temps(dates: pd.Series) -> str | None:
    d = dates.dropna().drop_duplicates().sort_values()
    if len(d) < 3:
        return None
    ecart = d.diff().dropna().dt.days.median()
    for seuil, libelle in ((1, "journalier"), (7, "hebdomadaire"), (31, "mensuel"),
                           (92, "trimestriel"), (366, "annuel")):
        if ecart <= seuil:
            return libelle
    return f"irrégulier (~{int(ecart)} jours)"


def profiler(source: str | Path | pd.DataFrame, nom: str | None = None,
             aujourd_hui: date | None = None) -> Profil:
    """Profile un fichier ou un DataFrame et retourne un objet Profil."""
    df = charger(source) if not isinstance(source, pd.DataFrame) else source
    nom = nom or (str(source) if not isinstance(source, pd.DataFrame) else "dataframe")
    aujourd_hui = aujourd_hui or date.today()
    alertes: list[str] = []

    est_geo = "geometry" in df.columns and hasattr(df, "crs")
    attributs = df.drop(columns="geometry") if est_geo else df
    n = len(df)

    colonnes: list[ProfilColonne] = []
    for c in attributs.columns:
        s = attributs[c]
        vides = (s.astype(str).str.strip() == "") & s.notna() if _est_texte(s) else pd.Series(False, index=s.index)
        manquants = int(s.isna().sum() + vides.sum())
        distincts = int(s.nunique(dropna=True))
        t = _type_infere(s)
        pc = ProfilColonne(
            nom=str(c), type_infere=t, nb_valeurs=n - manquants, nb_manquants=manquants,
            taux_completude=round(1 - manquants / n, 4) if n else 0.0, nb_distincts=distincts,
            # identifiant candidat : quasi unique (>= 95 %), sans valeur manquante
            identifiant_candidat=bool(n and manquants == 0 and distincts > 1 and distincts / n >= 0.95
                                      and t in {"entier", "texte"}),
            unite_devinee=deviner_unite(str(c)),
            exemples=[str(v) for v in s.dropna().unique()[:3]],
        )
        num = s if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s) else (
            pd.to_numeric(s.astype(str).str.replace(",", ".", regex=False), errors="coerce")
            if t == "nombre stocké en texte" else None)
        if num is not None and num.notna().any():
            pc.minimum, pc.maximum = str(num.min()), str(num.max())
            pc.moyenne = round(float(num.mean()), 4)
            if NONNEGATIFS.search(_norm(c)):
                pc.nb_negatifs_suspects = int((num < 0).sum())
                if pc.nb_negatifs_suspects:
                    alertes.append(f"« {c} » : {pc.nb_negatifs_suspects} valeur(s) négative(s) physiquement impossible(s)")
        if t.endswith("stocké en texte") or t == "date stockée en texte":
            alertes.append(f"« {c} » : {t}, conversion nécessaire avant intégration")
        if pc.taux_completude < 0.8:
            alertes.append(f"« {c} » : complétude faible ({pc.taux_completude:.0%})")
        colonnes.append(pc)

    dupliquees = int(attributs.duplicated().sum())
    if dupliquees:
        alertes.append(f"{dupliquees} ligne(s) entièrement dupliquée(s)")
    completude = round(float(np.mean([c.taux_completude for c in colonnes])) if colonnes else 0.0, 4)

    profil = Profil(source=nom, nb_lignes=n, nb_colonnes=len(attributs.columns), colonnes=colonnes,
                    lignes_dupliquees=dupliquees, taux_completude_global=completude)

    # --- géographie ---------------------------------------------------
    lon = lat = None
    if est_geo:
        profil.geographique = True
        profil.crs = df.crs.to_string() if df.crs else None
        if not df.crs:
            alertes.append("Système de coordonnées non déclaré")
        geom = df.geometry
        profil.types_geometrie = sorted(set(geom.dropna().geom_type))
        profil.geometries_vides = int((geom.isna() | geom.is_empty).sum())
        profil.geometries_invalides = int((~geom.dropna().is_valid).sum())
        if profil.geometries_invalides:
            alertes.append(f"{profil.geometries_invalides} géométrie(s) invalide(s)")
        g84 = df.to_crs(4326).geometry if df.crs else geom
        profil.emprise = [round(v, 5) for v in g84.total_bounds]
        centres = g84.representative_point()
        lon, lat = centres.x, centres.y
    else:
        nl = {_norm(c): c for c in df.columns}
        clat = next((nl[k] for k in nl if k in NOMS_LAT), None)
        clon = next((nl[k] for k in nl if k in NOMS_LON), None)
        if clat and clon:
            profil.geographique = True
            profil.crs = "EPSG:4326 (supposé, colonnes lat/lon)"
            lat = pd.to_numeric(df[clat], errors="coerce")
            lon = pd.to_numeric(df[clon], errors="coerce")
            if lat.notna().any():
                profil.emprise = [round(float(v), 5) for v in (lon.min(), lat.min(), lon.max(), lat.max())]
    if lon is not None:
        x0, y0, x1, y1 = MADAGASCAR_BBOX
        hors = ~((lon >= x0) & (lon <= x1) & (lat >= y0) & (lat <= y1))
        hors &= lon.notna() & lat.notna()
        profil.hors_madagascar = int(hors.sum())
        if profil.hors_madagascar:
            alertes.append(f"{profil.hors_madagascar} objet(s) hors de l'emprise de Madagascar "
                           "(inversion lat/lon ou système de coordonnées erroné ?)")

    # --- temps --------------------------------------------------------
    ct, dates = _detecter_temps(attributs)
    if ct is not None:
        profil.colonne_temporelle = str(ct)
        dmin, dmax = dates.min(), dates.max()
        profil.date_min = dmin.date().isoformat() if pd.notna(dmin) else None
        profil.date_max = dmax.date().isoformat() if pd.notna(dmax) else None
        profil.pas_de_temps = _pas_de_temps(dates)
        if pd.notna(dmax):
            profil.anciennete_jours = (aujourd_hui - dmax.date()).days
            if profil.anciennete_jours > 365:
                alertes.append(f"Données anciennes : dernière valeur il y a {profil.anciennete_jours} jours")

    # --- score synthétique (0-100), indicatif -------------------------
    unicite = 1 - dupliquees / n if n else 0
    validite = 1.0
    if profil.geographique and n:
        validite -= (profil.geometries_invalides + profil.hors_madagascar) / n
    negatifs = sum(c.nb_negatifs_suspects for c in colonnes)
    if n:
        validite -= negatifs / n
    actualite = 1.0 if profil.anciennete_jours is None else max(0.0, 1 - profil.anciennete_jours / 1825)
    profil.score_qualite = round(100 * (0.35 * completude + 0.2 * unicite
                                        + 0.3 * max(validite, 0) + 0.15 * actualite), 1)
    profil.alertes = alertes
    return profil
