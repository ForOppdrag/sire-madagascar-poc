"""Analyse de compatibilité entre jeux de données.

Pour chaque couple de profils, on évalue cinq critères et on en déduit un
verdict : compatible, partiellement compatible ou non mutualisable en l'état.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from itertools import combinations

import pandas as pd

from .profiler import Profil, _norm

VERDICTS = ("compatible", "partiellement compatible", "non mutualisable en l'état")


@dataclass
class Compatibilite:
    a: str
    b: str
    champs_communs: list[str] = field(default_factory=list)
    cle_jointure: str | None = None
    meme_crs: bool | None = None
    emprises_recouvrantes: bool | None = None
    meme_pas_de_temps: bool | None = None
    periodes_recouvrantes: bool | None = None
    conflits_unites: list[str] = field(default_factory=list)
    verdict: str = VERDICTS[2]
    actions: list[str] = field(default_factory=list)


def _recouvre(e1, e2) -> bool:
    return not (e1[2] < e2[0] or e2[2] < e1[0] or e1[3] < e2[1] or e2[3] < e1[1])


def comparer(p1: Profil, p2: Profil) -> Compatibilite:
    r = Compatibilite(a=p1.source, b=p2.source)
    c1 = {_norm(c.nom): c for c in p1.colonnes}
    c2 = {_norm(c.nom): c for c in p2.colonnes}
    communs = sorted(set(c1) & set(c2))
    r.champs_communs = communs

    # clé de jointure : champ commun identifiant dans au moins un des deux jeux
    for k in communs:
        if c1[k].identifiant_candidat or c2[k].identifiant_candidat:
            r.cle_jointure = k
            break
    if not r.cle_jointure:  # repli : champ commun nommé comme un code ou un identifiant
        r.cle_jointure = next((k for k in communs if re.search(r"(^|_)(code|id)(_|$)", k)), None)
    if not r.cle_jointure:  # repli : champs de noms différents mais de même objet (station_id / code_station)
        generiques = {"id", "code", "date", "nom", "type", "num", "no"}
        for k1, k2 in ((x, y) for x in c1 for y in c2):
            t1 = set(k1.split("_")) - generiques
            t2 = set(k2.split("_")) - generiques
            if t1 & t2 and re.search(r"(^|_)(code|id)(_|$)", k1) and re.search(r"(^|_)(code|id)(_|$)", k2):
                r.cle_jointure = f"{k1} ↔ {k2}"
                r.actions.append(f"Aligner les noms de la clé de jointure ({k1} / {k2})")
                break
    if not r.cle_jointure:
        r.actions.append("Définir un identifiant commun (ex. code station ou code commune du référentiel pivot)")

    for k in communs:
        u1, u2 = c1[k].unite_devinee, c2[k].unite_devinee
        if u1 and u2 and u1 != u2:
            r.conflits_unites.append(f"{k} : {u1} / {u2}")
        if c1[k].type_infere != c2[k].type_infere:
            r.actions.append(f"Harmoniser le type du champ « {k} » ({c1[k].type_infere} / {c2[k].type_infere})")

    if p1.geographique and p2.geographique:
        r.meme_crs = (p1.crs or "").split()[0] == (p2.crs or "").split()[0]
        if not r.meme_crs:
            r.actions.append(f"Reprojeter vers un système commun ({p1.crs} / {p2.crs})")
        if p1.emprise and p2.emprise:
            r.emprises_recouvrantes = _recouvre(p1.emprise, p2.emprise)

    reguliers = all(p and not p.startswith("irrégulier") for p in (p1.pas_de_temps, p2.pas_de_temps))
    if reguliers:  # comparaison temporelle réservée aux séries chronologiques
        r.meme_pas_de_temps = p1.pas_de_temps == p2.pas_de_temps
        if not r.meme_pas_de_temps:
            r.actions.append(f"Agréger au pas de temps commun le plus grossier ({p1.pas_de_temps} / {p2.pas_de_temps})")
        if p1.date_min and p2.date_min:
            r.periodes_recouvrantes = not (p1.date_max < p2.date_min or p2.date_max < p1.date_min)

    if r.conflits_unites:
        r.actions.append("Convertir les unités : " + "; ".join(r.conflits_unites))

    # verdict
    bloquants = [
        r.emprises_recouvrantes is False,
        r.periodes_recouvrantes is False,
        not communs and r.cle_jointure is None and not (p1.geographique and p2.geographique),
    ]
    a_corriger = [r.cle_jointure is None or "↔" in r.cle_jointure, r.meme_crs is False,
                  r.meme_pas_de_temps is False, bool(r.conflits_unites)]
    if any(bloquants):
        r.verdict = VERDICTS[2]
    elif any(a_corriger):
        r.verdict = VERDICTS[1]
    else:
        r.verdict = VERDICTS[0]
    return r


def matrice(profils: list[Profil]) -> pd.DataFrame:
    """Matrice carrée des verdicts, pour l'annexe du rapport de diagnostic."""
    noms = [p.source.split("/")[-1] for p in profils]
    m = pd.DataFrame("—", index=noms, columns=noms)
    for (i, p1), (j, p2) in combinations(enumerate(profils), 2):
        v = comparer(p1, p2).verdict
        m.iloc[i, j] = m.iloc[j, i] = v
    return m


def details(profils: list[Profil]) -> list[dict]:
    return [asdict(comparer(p1, p2)) for p1, p2 in combinations(profils, 2)]
