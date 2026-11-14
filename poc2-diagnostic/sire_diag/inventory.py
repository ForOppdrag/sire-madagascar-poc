"""Base d'inventaire des systèmes d'information et des jeux de données.

Stockage SQLite volontairement simple : un fichier unique, versionnable,
lisible avec n'importe quel outil, utilisable hors ligne sur site.
"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS institution (
    code        TEXT PRIMARY KEY,
    nom         TEXT NOT NULL,
    point_focal TEXT
);
CREATE TABLE IF NOT EXISTS systeme (
    code            TEXT PRIMARY KEY,
    nom             TEXT NOT NULL,
    institution     TEXT REFERENCES institution(code),
    fonctions       TEXT,
    technologies    TEXT,
    hebergement     TEXT,
    sauvegarde      TEXT,
    api             TEXT,
    licence         TEXT,
    statut          TEXT CHECK (statut IN ('actif', 'partiel', 'arrete', 'inconnu')) DEFAULT 'inconnu'
);
CREATE TABLE IF NOT EXISTS jeu_donnees (
    code                TEXT PRIMARY KEY,
    titre               TEXT NOT NULL,
    systeme             TEXT REFERENCES systeme(code),
    producteur          TEXT REFERENCES institution(code),
    theme               TEXT,
    format              TEXT,
    acces               TEXT CHECK (acces IN ('api', 'base', 'fichier', 'papier', 'inconnu')) DEFAULT 'inconnu',
    frequence_maj       TEXT,
    couverture_spatiale TEXT,
    couverture_temporelle TEXT,
    classification      TEXT CHECK (classification IN ('public', 'interne', 'restreint', 'inconnu')) DEFAULT 'inconnu',
    donnees_personnelles INTEGER DEFAULT 0,
    niveau_integration_cible INTEGER CHECK (niveau_integration_cible BETWEEN 0 AND 4),
    commentaire         TEXT
);
"""

NIVEAUX_INTEGRATION = {
    0: "Catalogué",
    1: "Consultable",
    2: "Exposé",
    3: "Répliqué et harmonisé",
    4: "Référence",
}


@dataclass
class JeuDonnees:
    code: str
    titre: str
    systeme: str | None = None
    producteur: str | None = None
    theme: str | None = None
    format: str | None = None
    acces: str = "inconnu"
    frequence_maj: str | None = None
    couverture_spatiale: str | None = None
    couverture_temporelle: str | None = None
    classification: str = "inconnu"
    donnees_personnelles: bool = False
    niveau_integration_cible: int | None = None
    commentaire: str | None = None


@dataclass
class Systeme:
    code: str
    nom: str
    institution: str | None = None
    fonctions: str | None = None
    technologies: str | None = None
    hebergement: str | None = None
    sauvegarde: str | None = None
    api: str | None = None
    licence: str | None = None
    statut: str = "inconnu"


@dataclass
class Inventaire:
    chemin: Path
    _cx: sqlite3.Connection = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.chemin = Path(self.chemin)
        self._cx = sqlite3.connect(self.chemin)
        self._cx.execute("PRAGMA foreign_keys = ON")
        self._cx.executescript(SCHEMA)

    # -- écriture -------------------------------------------------------
    def ajouter_institution(self, code: str, nom: str, point_focal: str | None = None) -> None:
        self._cx.execute(
            "INSERT OR REPLACE INTO institution VALUES (?, ?, ?)", (code, nom, point_focal)
        )
        self._cx.commit()

    def ajouter_systeme(self, s: Systeme) -> None:
        d = asdict(s)
        cols = ", ".join(d)
        self._cx.execute(
            f"INSERT OR REPLACE INTO systeme ({cols}) VALUES ({', '.join('?' * len(d))})",
            tuple(d.values()),
        )
        self._cx.commit()

    def ajouter_jeu(self, j: JeuDonnees) -> None:
        d = asdict(j)
        d["donnees_personnelles"] = int(bool(d["donnees_personnelles"]))
        cols = ", ".join(d)
        self._cx.execute(
            f"INSERT OR REPLACE INTO jeu_donnees ({cols}) VALUES ({', '.join('?' * len(d))})",
            tuple(d.values()),
        )
        self._cx.commit()

    # -- lecture --------------------------------------------------------
    def jeux(self) -> list[dict]:
        cur = self._cx.execute("SELECT * FROM jeu_donnees ORDER BY code")
        noms = [c[0] for c in cur.description]
        return [dict(zip(noms, row)) for row in cur.fetchall()]

    def systemes(self) -> list[dict]:
        cur = self._cx.execute("SELECT * FROM systeme ORDER BY code")
        noms = [c[0] for c in cur.description]
        return [dict(zip(noms, row)) for row in cur.fetchall()]

    def synthese(self) -> dict:
        """Indicateurs de synthèse pour le rapport de diagnostic."""
        jeux = self.jeux()
        par_acces: dict[str, int] = {}
        par_niveau: dict[str, int] = {}
        for j in jeux:
            par_acces[j["acces"]] = par_acces.get(j["acces"], 0) + 1
            niveau = j["niveau_integration_cible"]
            libelle = NIVEAUX_INTEGRATION.get(niveau, "Non attribué")
            par_niveau[libelle] = par_niveau.get(libelle, 0) + 1
        return {
            "nb_systemes": len(self.systemes()),
            "nb_jeux": len(jeux),
            "jeux_avec_donnees_personnelles": sum(j["donnees_personnelles"] for j in jeux),
            "repartition_acces": par_acces,
            "repartition_niveau_cible": par_niveau,
        }

    def exporter_csv(self, dossier: Path) -> list[Path]:
        dossier = Path(dossier)
        dossier.mkdir(parents=True, exist_ok=True)
        sorties = []
        for nom, lignes in (("systemes", self.systemes()), ("jeux_donnees", self.jeux())):
            p = dossier / f"{nom}.csv"
            with p.open("w", newline="", encoding="utf-8") as f:
                if lignes:
                    w = csv.DictWriter(f, fieldnames=list(lignes[0]))
                    w.writeheader()
                    w.writerows(lignes)
            sorties.append(p)
        return sorties

    def fermer(self) -> None:
        self._cx.close()
