# Agent de candidatures automatiques

![CI](https://github.com/ismaelabid69-lgtm/agent-candidatures/actions/workflows/ci.yml/badge.svg)

Un agent Python qui trouve les entreprises informatiques, télécoms et hôpitaux à moins de 15 km de chez moi, cherche leur adresse mail de contact, puis leur envoie une candidature spontanée personnalisée avec mon CV (20 par jour maximum, une seule fois par entreprise).

Projet personnel mené dans une démarche **DevOps** : code versionné, tests automatisés, intégration continue, API REST et conteneurisation Docker.

📘 **[Guide pas à pas : apprendre Git, la CI, les API et Docker avec ce projet](docs/APPRENDRE.md)**

## Fonctionnement

```
 Annuaire des Entreprises (API État)   ─┐
 OpenStreetMap (API Overpass)          ─┼─► collect.py ──► entreprises.csv ──► send.py ──► Gmail (SMTP)
 Sites web des entreprises (scraping)  ─┘   filtre, déduplique,  (suivi des      mail personnalisé
                                            trouve les mails      statuts)       + CV, 20/jour
```

| Étape | Ce qui se passe |
|---|---|
| **Recherche** | Interroge l'API officielle `recherche-entreprises.api.gouv.fr` par code d'activité (NAF) dans un rayon donné, filtre les entreprises fermées, trop petites ou hors zone. |
| **Enrichissement** | Trouve le site web (OpenStreetMap, Google Places en option, ou déduction du domaine), puis parcourt les pages contact / mentions légales / recrutement pour extraire la meilleure adresse (recrutement@ > rh@ > contact@), y compris les adresses masquées par Cloudflare. |
| **Rédaction** | Assemble un mail à partir de variantes (objet, intro, conclusion…) choisies de façon déterministe par entreprise : chaque entreprise reçoit un mail cohérent et différent des autres. |
| **Envoi** | SMTP Gmail avec mot de passe d'application, pause aléatoire entre deux envois, limite quotidienne, bascule automatique du port 465 vers 587 si la connexion est coupée, aucun doublon. |

## Architecture

```
                    ┌────────────────────── conteneur Docker ──────────────────────┐
  navigateur /      │  API FastAPI (api.py)          planificateur (lun-ven 9h10)  │
  curl / script ───►│  GET /stats /entreprises …  ──► collect.py ──► send.py ──────┼──► Gmail
                    │  POST /collecte /envois                                     │
                    └───────────────┬──────────────────────────────────────────────┘
                                    │ volume
                              donnees/ (CSV de suivi, CV)
```

## Stack technique

- **Python 3.12+** : `requests`, `smtplib`, **FastAPI** + **Uvicorn** (API REST, doc Swagger auto)
- **Docker** : image `python:3.12-slim`, utilisateur non-root, healthcheck, volume persistant, **docker compose**
- **pytest** (34 tests : filtrage, extraction des mails, rédaction, SMTP simulé, routes de l'API, planificateur) et **ruff** (lint)
- **GitHub Actions** : lint + tests sur Python 3.12 et 3.14, puis build de l'image et test du conteneur

## Lancer le projet

### Avec Docker (recommandé)

```bash
cp .env.example .env                       # adresse Gmail + mot de passe d'application
cp config_perso.example.py config_perso.py # nom, téléphone
mkdir donnees && cp ton_cv.pdf donnees/cv.pdf
docker compose up -d --build
```
API et documentation : http://127.0.0.1:8000/docs

### En ligne de commande

```bash
python -m pip install -r requirements.txt
python collect.py             # recherche des entreprises et de leurs mails
python send.py --apercu       # affiche les mails sans rien envoyer
python send.py --test         # s'envoie un mail d'exemple
python send.py                # envoi réel (20 max par jour)
python -m uvicorn api:app     # ou : lancer l'API sans Docker
```

Toute la configuration (zone, rayon, secteurs, entreprises exclues, nombre d'envois, heure de lancement) est dans `config.py`, le texte du mail dans `modele_mail.txt`.

## API

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/sante` | Healthcheck |
| GET | `/stats` | Entreprises par statut, envois du jour |
| GET | `/entreprises?statut=&ville=&limite=` | Liste filtrée, triée par distance |
| GET | `/entreprises/{id}/apercu` | Mail exact qui serait envoyé |
| POST | `/collecte` | Lance la recherche (arrière-plan) |
| POST | `/envois` | Lance les envois du jour (arrière-plan) |
| GET | `/taches` | Tâche en cours, historique, journal |

## Tests

```bash
python -m pip install -r requirements-dev.txt
ruff check .
pytest -v
```

## Sécurité et données personnelles

Le dépôt ne contient **aucune donnée personnelle** : le CV, `.env` (identifiants), `config_perso.py` et le dossier `donnees/` sont exclus par le `.gitignore` et le `.dockerignore`. Les identifiants arrivent par variables d'environnement, jamais dans le code ni dans l'image Docker. L'API n'écoute que sur `127.0.0.1`.

## Feuille de route

- [x] Agent fonctionnel : recherche, enrichissement, envoi
- [x] Versionnement Git, tests automatisés, intégration continue (GitHub Actions)
- [x] API REST (FastAPI) avec planificateur intégré
- [x] Conteneurisation (Dockerfile, docker-compose, healthcheck) testée en CI
- [ ] Déploiement automatique sur une VM Linux (Ansible) avec exécution planifiée
- [ ] Base de données à la place du CSV
- [ ] Supervision : métriques (Prometheus), tableau de bord (Grafana), alertes Discord

## Auteur

Ismaël ABID — BTS CIEL, technicien informatique et réseaux, Vénissieux.
