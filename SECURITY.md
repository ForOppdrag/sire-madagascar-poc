# Politique de sécurité

Ces démonstrateurs sont destinés à une exécution **locale**, à des fins
d'illustration. Ils ne doivent pas être exposés sur Internet en l'état.

## Signaler une vulnérabilité

Merci de ne pas ouvrir de ticket public. Écrivez à **contact@oppdrag.tech**
en décrivant le problème et la manière de le reproduire. Nous accusons
réception sous 5 jours ouvrés.

## Mesures en place

- Secrets hors du code (`.env` non versionné) ; démarrage refusé sans mot de passe
- Base de données non exposée ; interfaces d'administration limitées à `127.0.0.1`
- Mandataire en lecture seule, en-têtes de sécurité, version du serveur masquée
- Échappement des données affichées dans la page web
- Analyse statique et tests à chaque modification (GitHub Actions)
- Mises à jour des dépendances surveillées par Dependabot
- Contrôle automatisé de la pile lancée : `poc1-interoperabilite/scripts/verifier_securite.py`
