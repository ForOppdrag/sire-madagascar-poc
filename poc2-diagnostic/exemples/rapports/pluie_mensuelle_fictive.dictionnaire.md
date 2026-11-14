# Dictionnaire et profil de qualité — pluie_mensuelle_fictive.csv

- **Lignes** : 720 · **Champs** : 3
- **Score de qualité indicatif** : 90.4 / 100
- **Complétude globale** : 98%
- **Lignes dupliquées** : 0
- **Temps** : champ « date », du 2018-01-01 au 2023-12-01, pas mensuel, dernière valeur il y a 1079 jours

## Alertes

- « date » : date stockée en texte, conversion nécessaire avant intégration
- « pluie_mm » : 1 valeur(s) négative(s) physiquement impossible(s)
- Données anciennes : dernière valeur il y a 1079 jours

## Dictionnaire de données

| champ | type | unité devinée | unité validée | définition | complétude | valeurs distinctes | min | max | identifiant candidat | exemples |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| station_id | texte |  |  |  | 100% | 10 |  |  |  | ST001 / ST002 / ST003 |
| date | date stockée en texte |  |  |  | 100% | 72 |  |  |  | 2018-01-01 / 2018-02-01 / 2018-03-01 |
| pluie_mm | décimal | mm |  |  | 94% | 601 | -12.0 | 603.6 |  | 162.3 / 124.1 / 24.3 |

_Premier jet généré automatiquement : définitions et unités à valider avec le producteur._
