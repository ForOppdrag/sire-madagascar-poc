"""Contrôle qualité des séries mensuelles et indicateur de sécheresse simplifié.

Pour chaque bassin :
  - lacunes      : mois manquants dans la période couverte
  - anomalie z   : écart robuste à la climatologie du mois calendaire
                   (médiane et écart absolu médian × 1,4826), insensible aux
                   valeurs aberrantes qu'il doit justement détecter
  - suspect      : |z| > 3,5, valeur à vérifier avant diffusion
  - IPS-3        : indice de précipitation standardisé sur 3 mois, calculé ici par
                   standardisation des cumuls glissants (approximation normale).
                   L'IPS de référence (McKee et al., 1993 ; OMM, 2012) ajuste une loi
                   gamma : ce calcul simplifié sert à la démonstration, pas à l'alerte.
Classes de sécheresse (seuils de McKee) : modérée ≤ -1, sévère ≤ -1,5, extrême ≤ -2.
"""

from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd

SEUIL_SUSPECT = 3.5  # z modifié, seuil d'Iglewicz et Hoaglin (1993)


def classe_ips(v: float) -> str:
    if pd.isna(v):
        return ""
    if v <= -2:
        return "sécheresse extrême"
    if v <= -1.5:
        return "sécheresse sévère"
    if v <= -1:
        return "sécheresse modérée"
    if v >= 1.5:
        return "très humide"
    return "normal"


def _par_bassin(g: pd.DataFrame, valeur: str) -> pd.DataFrame:
    g = g.sort_values("date").set_index("date")
    complet = pd.date_range(g.index.min(), g.index.max(), freq="MS")
    g = g.reindex(complet)
    g.index.name = "date"
    g["lacune"] = g[valeur].isna()
    mois = g.index.month
    med = g.groupby(mois)[valeur].transform("median").to_numpy()
    mad = (g[valeur] - med).abs().groupby(mois).transform("median").to_numpy() * 1.4826
    moy, et = med, mad
    with np.errstate(invalid="ignore", divide="ignore"):
        g["anomalie_z"] = np.round((g[valeur].to_numpy() - moy) / np.where(et > 0, et, np.nan), 2)
    g["suspect"] = g["anomalie_z"].abs() > SEUIL_SUSPECT
    cumul = g[valeur].rolling(3, min_periods=3).sum()
    cm = cumul.groupby(mois).transform("mean")
    cs = cumul.groupby(mois).transform("std")
    g["ips3"] = np.round((cumul - cm) / cs.where(cs > 0), 2)
    g["classe_ips3"] = g["ips3"].map(classe_ips)
    return g.reset_index()


def controler(series: pd.DataFrame, id_col: str = "hybas_id", valeur: str = "pluie_mm") -> pd.DataFrame:
    sorties = []
    for k, g in series.groupby(id_col):
        r = _par_bassin(g.drop(columns=[id_col]), valeur)
        r.insert(0, id_col, k)
        sorties.append(r)
    return pd.concat(sorties, ignore_index=True)


def synthese(q: pd.DataFrame, id_col: str = "hybas_id") -> pd.DataFrame:
    lignes = []
    for k, g in q.groupby(id_col):
        dernier = g.dropna(subset=["ips3"]).tail(1)
        lignes.append({
            id_col: k,
            "mois": len(g),
            "lacunes": int(g["lacune"].sum()),
            "valeurs_suspectes": int(g["suspect"].sum()),
            "mois_en_secheresse": int((g["ips3"] <= -1).sum()),
            "dernier_ips3": float(dernier["ips3"].iloc[0]) if len(dernier) else np.nan,
            "classe_actuelle": dernier["classe_ips3"].iloc[0] if len(dernier) else "",
        })
    return pd.DataFrame(lignes)


def _svg(g: pd.DataFrame, largeur=320, hauteur=60) -> str:
    v = g["ips3"].to_numpy(dtype=float)
    if np.all(np.isnan(v)):
        return ""
    n = len(v)
    lim = max(2.5, np.nanmax(np.abs(v)))
    x = lambda i: 4 + i * (largeur - 8) / max(n - 1, 1)  # noqa: E731
    y = lambda z: hauteur / 2 - z / lim * (hauteur / 2 - 4)  # noqa: E731
    pts = " ".join(f"{x(i):.1f},{y(z):.1f}" for i, z in enumerate(v) if not np.isnan(z))
    seuil = y(-1)
    return (f"<svg viewBox='0 0 {largeur} {hauteur}' width='{largeur}' height='{hauteur}' role='img' "
            f"aria-label='IPS-3'><line x1='0' x2='{largeur}' y1='{hauteur / 2}' y2='{hauteur / 2}' stroke='#c9d6db'/>"
            f"<line x1='0' x2='{largeur}' y1='{seuil:.1f}' y2='{seuil:.1f}' stroke='#e8a090' stroke-dasharray='3 3'/>"
            f"<polyline fill='none' stroke='#1C7293' stroke-width='1.5' points='{pts}'/></svg>")


def rapport_html(q: pd.DataFrame, id_col: str = "hybas_id", titre: str = "Contrôle qualité des séries de pluie") -> str:
    s = synthese(q, id_col).sort_values("dernier_ips3")
    lignes = []
    for _, r in s.iterrows():
        g = q[q[id_col] == r[id_col]]
        couleur = "#f9dcd6" if r["dernier_ips3"] <= -1 else "#fff"
        lignes.append(
            f"<tr style='background:{couleur}'><td>{escape(str(r[id_col]))}</td><td>{r['mois']}</td>"
            f"<td>{r['lacunes']}</td><td>{r['valeurs_suspectes']}</td><td>{r['mois_en_secheresse']}</td>"
            f"<td>{'' if pd.isna(r['dernier_ips3']) else r['dernier_ips3']}</td>"
            f"<td>{escape(r['classe_actuelle'])}</td><td>{_svg(g)}</td></tr>")
    periode = f"{q['date'].min():%m/%Y} – {q['date'].max():%m/%Y}"
    return (
        "<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'><title>" + escape(titre) + "</title><style>"
        "body{font-family:system-ui,sans-serif;color:#1F2A33;margin:0;background:#f6fafb}"
        "header{background:#0B3C5D;color:#fff;padding:18px 28px}h1{margin:0;font-size:1.3rem}"
        "main{padding:20px 28px}table{border-collapse:collapse;background:#fff;font-size:.85rem}"
        "th,td{border:1px solid #dde7ea;padding:5px 8px;text-align:left}th{background:#EAF4F6}"
        "p.note{font-size:.8rem;color:#5C7A8A;max-width:900px}</style></head><body>"
        f"<header><h1>{escape(titre)}</h1><div>{len(s)} bassins versants · {periode} · source CHIRPS v2.0</div></header>"
        "<main><table><tr><th>Bassin</th><th>Mois</th><th>Lacunes</th><th>Valeurs suspectes (|z|&gt;3,5)</th>"
        "<th>Mois en sécheresse</th><th>Dernier IPS-3</th><th>Classe</th><th>IPS-3 sur la période</th></tr>"
        + "".join(lignes) + "</table><p class='note'>IPS-3 simplifié : cumuls de pluie sur 3 mois standardisés "
        "par mois calendaire (approximation normale). L'IPS de référence de l'OMM ajuste une loi gamma ; ce "
        "calcul illustre la faisabilité d'indicateurs dérivés et ne constitue pas un outil d'alerte. Ligne "
        "pointillée : seuil de sécheresse modérée (-1).</p></main></body></html>")
