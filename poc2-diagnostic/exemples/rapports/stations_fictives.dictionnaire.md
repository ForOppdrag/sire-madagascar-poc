# Dictionnaire et profil de qualité — stations_fictives.csv

- **Lignes** : 21 · **Champs** : 6
- **Score de qualité indicatif** : 82.3 / 100
- **Complétude globale** : 99%
- **Lignes dupliquées** : 1
- **Système de coordonnées** : EPSG:4326 (supposé, colonnes lat/lon)
- **Emprise (WGS 84)** : [44.24092, -23.7661, 49.33884, 48.28111]
- **Objets hors Madagascar** : 1
- **Temps** : champ « date_installation », du 1995-01-01 au 2015-10-23, pas irrégulier (~400 jours), dernière valeur il y a 4040 jours

## Alertes

- « date_installation » : date stockée en texte, conversion nécessaire avant intégration
- 1 ligne(s) entièrement dupliquée(s)
- 1 objet(s) hors de l'emprise de Madagascar (inversion lat/lon ou système de coordonnées erroné ?)
- Données anciennes : dernière valeur il y a 4040 jours

## Dictionnaire de données

| champ | type | unité devinée | unité validée | définition | complétude | valeurs distinctes | min | max | identifiant candidat | exemples |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| code_station | texte |  |  |  | 100% | 20 |  |  | oui | ST001 / ST002 / ST003 |
| nom | texte |  |  |  | 100% | 20 |  |  | oui | Station fictive 1 / Station fictive 2 / Station fictive 3 |
| latitude | décimal | degrés (latitude) |  |  | 100% | 20 | -23.7661 | 48.28111 |  | -15.59951 / -19.4529 / -14.62612 |
| longitude | décimal | degrés (longitude) |  |  | 100% | 20 | 44.24092 | 49.33884 |  | 48.16948 / 45.94989 / 49.33884 |
| bassin | texte |  |  |  | 95% | 4 |  |  |  | Onilahy / Betsiboka / Ikopa |
| date_installation | date stockée en texte |  |  |  | 100% | 20 |  |  |  | 01/01/1995 / 05/02/1996 / 11/03/1997 |

_Premier jet généré automatiquement : définitions et unités à valider avec le producteur._
