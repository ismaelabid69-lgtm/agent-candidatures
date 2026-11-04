# Apprendre le DevOps avec ce projet

Ce guide te fait passer par les vrais outils du métier, sur ton propre projet. Chaque partie explique le concept, puis te donne les commandes à taper toi-même dans le terminal de VS Code (PowerShell), ouvert dans le dossier du projet.

| Partie | Outil | Ce que tu apprends |
|---|---|---|
| 1 | **Git** | Versionner ton code, revenir en arrière, travailler en branches |
| 2 | **GitHub + CI** | Publier ton code, faire tester chaque modification automatiquement |
| 3 | **API** | Piloter un programme par HTTP, lire du JSON, documentation Swagger |
| 4 | **Docker** | Emballer l'application pour qu'elle tourne partout pareil |

---

## Partie 1 — Git

**Le concept.** Git prend des « photos » de ton projet, qu'on appelle des **commits**. Chaque commit garde l'état de tous les fichiers, un message et une date. Tu peux revenir à n'importe quelle photo, voir ce qui a changé entre deux photos, et travailler sur une copie à part (une **branche**) sans casser la version qui marche.

Le vocabulaire :
- **dépôt** (repository) : le dossier suivi par Git (il contient un dossier caché `.git`)
- **zone de préparation** (staging) : la liste des modifications que tu vas mettre dans le prochain commit
- **commit** : la photo enregistrée
- **branche** : une ligne de travail ; la principale s'appelle `main`
- **remote** : la copie du dépôt sur GitHub

### Exercice 1.1 — Premier commit

```powershell
git config --global user.name "Ismaël ABID"
git config --global user.email "ismael.abid69@gmail.com"
git init -b main                # transforme le dossier en dépôt Git
git status                      # ce que Git voit : tout est "untracked" (non suivi)
git add .                       # prépare tous les fichiers (sauf ceux du .gitignore)
git status                      # vérifie : PAS de cv.pdf, .env, config_perso.py, donnees/
git commit -m "Premier commit : agent de candidatures"
git log --oneline               # l'historique : une ligne par commit
```

> Pourquoi `.env` et `cv.pdf` n'apparaissent pas ? Grâce au fichier `.gitignore`. Ouvre-le : chaque ligne est un fichier ou un dossier que Git doit ignorer. C'est comme ça qu'on évite de publier des mots de passe, une erreur très courante (et grave) en entreprise.

### Exercice 1.2 — Modifier, voir la différence, revenir en arrière

1. Dans `config.py`, change `RAYON_KM = 15` en `RAYON_KM = 20` et enregistre.
2. Puis :
```powershell
git diff                        # montre exactement la ligne modifiée (- ancienne, + nouvelle)
git restore config.py           # annule la modification : retour à la version du dernier commit
git diff                        # plus rien : le fichier est revenu comme avant
```

### Exercice 1.3 — Travailler sur une branche

```powershell
git switch -c rayon-20km        # crée une branche et va dessus
# modifie RAYON_KM = 20 dans config.py, enregistre
git commit -am "Rayon de recherche passé à 20 km"
git switch main                 # retour sur main : config.py est revenu à 15 km !
git switch rayon-20km           # et là, il est à 20 km
git switch main
git merge rayon-20km            # on intègre la branche dans main
git branch -d rayon-20km        # on supprime la branche, elle ne sert plus
git log --oneline --graph
```

> En entreprise, on ne modifie jamais `main` directement : on crée une branche, on fait une **pull request** sur GitHub, la CI teste, un collègue relit, puis on fusionne.

---

## Partie 2 — GitHub et intégration continue (CI)

**Le concept.** GitHub héberge ton dépôt en ligne. **GitHub Actions** lit le fichier `.github/workflows/ci.yml` et, à chaque `git push`, lance sur un serveur de GitHub :
1. **ruff** : vérifie le style et repère les erreurs (variable inutilisée, import manquant…)
2. **pytest** : lance les tests du dossier `tests/`, sur Python 3.12 et 3.14
3. **docker build** : construit l'image, démarre le conteneur et vérifie que l'API répond

Si une étape échoue, tu reçois un mail et le commit a une croix rouge. C'est le principe de l'**intégration continue** : on détecte un problème dès qu'il est introduit, pas trois semaines plus tard.

### Exercice 2.1 — Lancer les tests en local (ce que fera la CI)

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m pytest -v
```

Ouvre `tests/test_send.py` : chaque fonction `test_...` vérifie un comportement. Par exemple `test_bascule_sur_le_port_587_si_le_465_coupe` simule une panne de Gmail sans envoyer de vrai mail. C'est le principe du **mock** : on remplace une vraie dépendance par une fausse qu'on contrôle.

### Exercice 2.2 — Publier sur GitHub

1. Sur github.com : **New repository**, nom `agent-candidatures`, **public**, sans README.
2. Puis :
```powershell
git remote add origin https://github.com/TON_PSEUDO/agent-candidatures.git
git push -u origin main
```
3. Sur la page du dépôt, onglet **Actions** : regarde la CI tourner en direct. Clique sur une étape pour voir ses logs.
4. Dans `README.md`, remplace `TON_PSEUDO` par ton pseudo GitHub, puis `git commit -am "Badge CI"` et `git push`. La pastille verte apparaît sur la page d'accueil du dépôt.

### Exercice 2.3 — Casser la CI exprès (pour comprendre)

Dans `tests/test_collect.py`, change `== "SFR Business"` en `== "SFR BUSINESS"`, puis :
```powershell
python -m pytest            # 1 test échoue en local
git commit -am "Test cassé exprès"
git push                    # croix rouge sur GitHub + mail
```
Remets la bonne valeur, commit, push : tout redevient vert. Voilà comment la CI protège ton code.

---

## Partie 3 — L'API

**Le concept.** Une **API web** est un programme qui attend des requêtes **HTTP**, comme un site web, mais qui répond avec des données (en **JSON**) au lieu de pages. Chaque adresse s'appelle une **route** (ou endpoint) :

| Méthode | Route | Effet |
|---|---|---|
| GET | `/sante` | L'API est-elle vivante ? (utilisée par Docker) |
| GET | `/stats` | Nombre d'entreprises par statut, envois du jour |
| GET | `/entreprises?statut=pret` | La liste, filtrable par statut ou ville |
| GET | `/entreprises/{id}/apercu` | Le mail exact que recevrait une entreprise |
| POST | `/collecte` | Lance la recherche d'entreprises (en arrière-plan) |
| POST | `/envois` | Lance l'envoi des candidatures du jour |
| GET | `/taches` | Ce qui tourne, l'historique et le journal |

**GET** lit une information, **POST** déclenche une action. Les codes de réponse ont un sens : `200` OK, `202` accepté (l'action démarre), `404` introuvable, `409` conflit (une tâche tourne déjà).

L'API contient aussi un **planificateur** : du lundi au vendredi à 9 h 10, il lance tout seul la collecte puis l'envoi (réglable dans `config.py`).

### Exercice 3.1 — Démarrer l'API

```powershell
python -m pip install -r requirements.txt
python -m uvicorn api:app --reload
```
`--reload` relance l'API à chaque fois que tu modifies le code. Laisse ce terminal ouvert.

### Exercice 3.2 — La documentation interactive

Ouvre **http://127.0.0.1:8000/docs** dans ton navigateur. C'est **Swagger**, généré automatiquement à partir du code. Clique sur `GET /stats` → **Try it out** → **Execute** : tu vois la requête envoyée, le code de réponse et le JSON.

Essaie `GET /entreprises` avec `statut = envoye` : ce sont les entreprises déjà contactées.

### Exercice 3.3 — Appeler l'API depuis le terminal

Ouvre un **deuxième** terminal (le `+` dans VS Code) :
```powershell
Invoke-RestMethod http://127.0.0.1:8000/stats
Invoke-RestMethod "http://127.0.0.1:8000/entreprises?ville=Bron&limite=5" | Format-Table nom, ville, email, statut
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/collecte?max_enrichissements=10"
Invoke-RestMethod http://127.0.0.1:8000/taches
```
La dernière commande montre la collecte qui avance en direct. Relance-la plusieurs fois.

> C'est exactement comme ça que les outils communiquent en entreprise : un script, une autre application ou un tableau de bord appelle l'API.

---

## Partie 4 — Docker

**Le concept.** « Chez moi ça marche » est le problème numéro 1 en informatique : une autre version de Python, une bibliothèque manquante… (tu l'as vécu avec `No module named 'requests'`). Docker règle ça en emballant l'application **avec tout ce dont elle a besoin** :

- **image** : le paquet figé (système Linux minimal + Python + bibliothèques + ton code). Décrite par le `Dockerfile`.
- **conteneur** : une image en train de tourner. Isolé du reste de ton PC.
- **volume** : un dossier de ton PC partagé avec le conteneur, pour que les données survivent quand on supprime le conteneur.
- **docker compose** : décrit dans `docker-compose.yml` comment lancer le conteneur (ports, volumes, variables).

### Lis le Dockerfile ligne par ligne

Ouvre `Dockerfile` : chaque instruction est commentée. Points importants :
- `FROM python:3.12-slim` : on part d'une image officielle.
- On copie `requirements.txt` **avant** le code : Docker met chaque étape en cache, donc tant que les dépendances ne changent pas, il ne les réinstalle pas.
- `USER agent` : l'application ne tourne pas en administrateur (bonne pratique de sécurité).
- `HEALTHCHECK` : Docker appelle `/sante` toutes les 30 s et marque le conteneur `healthy` ou `unhealthy`.

### Exercice 4.1 — Installer Docker Desktop

1. Télécharge **Docker Desktop pour Windows** sur docker.com et installe-le (il active WSL 2, le Linux intégré à Windows).
2. ⚠️ Il faut **plusieurs Go libres** sur ton disque : fais de la place avant si besoin.
3. Redémarre, lance Docker Desktop, puis vérifie :
```powershell
docker --version
docker run hello-world          # télécharge une mini image et la lance
```

### Exercice 4.2 — Lancer l'agent dans Docker

Arrête d'abord l'API lancée à l'exercice 3 (`Ctrl + C`). Ensuite, range tes données dans un dossier `donnees` : c'est lui que Docker partage avec le conteneur (à faire **quand aucun envoi n'est en cours**) :
```powershell
mkdir donnees
Move-Item entreprises.csv, cv.pdf, .derniere_recherche donnees\
```
Les scripts utilisent automatiquement ce dossier dès qu'il existe, avec ou sans Docker. Puis :
```powershell
docker compose up -d --build    # construit l'image et démarre le conteneur en arrière-plan
docker compose ps               # état du conteneur : attends "healthy"
docker compose logs -f          # les logs en direct (Ctrl + C pour quitter)
```
Ouvre http://127.0.0.1:8000/docs : c'est la même API, mais elle tourne maintenant dans un conteneur Linux.

### Exercice 4.3 — Explorer le conteneur

```powershell
docker images                                   # tes images et leur taille
docker exec -it agent-candidatures bash         # ouvre un terminal DANS le conteneur
```
Dans le conteneur (tu es sous Linux !) :
```bash
whoami          # agent (pas root)
ls /app         # ton code
ls /data        # tes données : c'est ton dossier "donnees" monté en volume
python --version
exit
```

### Exercice 4.4 — Prouver que les données sont persistantes

```powershell
docker compose down             # supprime le conteneur
docker compose ps               # plus rien
docker compose up -d            # le recrée
Invoke-RestMethod http://127.0.0.1:8000/stats   # les mêmes chiffres : les données sont dans le volume
```

### Commandes Docker à retenir

| Commande | Effet |
|---|---|
| `docker compose up -d --build` | Construire et démarrer |
| `docker compose ps` | État des conteneurs |
| `docker compose logs -f` | Logs en direct |
| `docker compose restart` | Redémarrer (après un changement de `config.py`) |
| `docker compose down` | Arrêter et supprimer le conteneur (les données restent) |
| `docker exec -it agent-candidatures bash` | Entrer dans le conteneur |

> Avec `restart: unless-stopped`, le conteneur redémarre tout seul quand Docker Desktop démarre : ton agent envoie ses candidatures chaque matin sans que tu lances quoi que ce soit.

---

## Pour aller plus loin

- **Publier l'image** sur le GitHub Container Registry depuis la CI (`docker push ghcr.io/...`)
- **Déployer** sur une VM Linux (VirtualBox ou un petit serveur) avec **Ansible**
- **Remplacer le CSV** par une base **SQLite** ou **PostgreSQL** (un 2e conteneur dans `docker-compose.yml`)
- **Superviser** : exposer des métriques pour **Prometheus** et faire un tableau de bord **Grafana**
- **Alertes** : un message Discord quand un envoi échoue

## Ce que tu peux dire en entretien

> « J'ai développé un agent en Python qui automatise ma recherche d'emploi. Le code est versionné sur GitHub avec une intégration continue (GitHub Actions) qui lance le lint, 34 tests unitaires et un test de l'image Docker à chaque push. L'application expose une API REST (FastAPI) avec une documentation Swagger, tourne dans un conteneur Docker avec healthcheck, utilisateur non-root et volume persistant, et intègre un planificateur pour les envois quotidiens. Les secrets sont gérés hors du code, via des variables d'environnement. »
