"""
API web de l'agent de candidatures (FastAPI).

Lancer en local :   python -m uvicorn api:app --reload
Documentation :     http://127.0.0.1:8000/docs   (tu peux tester chaque route depuis le navigateur)

Une API, c'est un programme qui répond à des requêtes HTTP :
  GET  = lire une information          (ex : les statistiques)
  POST = déclencher une action         (ex : lancer la collecte)
Les réponses sont en JSON, un format texte que n'importe quel programme sait lire.
"""
import os
import threading
import time
from collections import Counter, deque
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

import collect
import config
import send
from commun import charger, distance_float

PARIS = ZoneInfo("Europe/Paris")
VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Gestion des tâches : une seule tâche à la fois (collecte OU envoi), en arrière-plan
# ---------------------------------------------------------------------------
class GestionnaireTaches:
    def __init__(self):
        self._verrou = threading.Lock()
        self.en_cours = None          # "collecte" / "envoi" / None
        self.journal = deque(maxlen=300)
        self.historique = deque(maxlen=50)

    def log(self, message):
        self.journal.append(f"{datetime.now(PARIS):%Y-%m-%d %H:%M:%S}  {message}")

    def lancer(self, nom, fonction):
        """Démarre `fonction` dans un thread. Renvoie False si une tâche tourne déjà."""
        if not self._verrou.acquire(blocking=False):
            return False
        self.en_cours = nom

        def executer():
            debut = datetime.now(PARIS)
            resultat, erreur = None, None
            self.log(f"--- début : {nom}")
            try:
                resultat = fonction(self.log)
            except Exception as exc:  # on garde l'erreur pour l'afficher dans l'API
                erreur = str(exc)
                self.log(f"ERREUR : {erreur}")
            finally:
                self.historique.appendleft({
                    "tache": nom, "debut": debut.isoformat(timespec="seconds"),
                    "fin": datetime.now(PARIS).isoformat(timespec="seconds"),
                    "resultat": resultat, "erreur": erreur,
                })
                self.log(f"--- fin : {nom}")
                self.en_cours = None
                self._verrou.release()

        threading.Thread(target=executer, name=nom, daemon=True).start()
        return True


taches = GestionnaireTaches()


def tache_collecte(max_enrichissements=None, forcer=False):
    return lambda log: collect.executer(max_enrichissements, forcer, journal=log)


def tache_envoi(nombre=None):
    return lambda log: send.envoyer_lot(nombre, journal=log)


def tache_quotidienne(log):
    """Ce que fait le planificateur chaque matin : collecte puis envoi."""
    statuts = collect.executer(journal=log)
    envoyes = send.envoyer_lot(journal=log)
    return {"statuts": statuts, "envoyes": envoyes}


# ---------------------------------------------------------------------------
# Planificateur : lance la tâche quotidienne à l'heure prévue (remplace cron)
# ---------------------------------------------------------------------------
def doit_lancer(maintenant, dernier_jour):
    heure, minute = (int(x) for x in config.HEURE_LANCEMENT.split(":"))
    return (
        maintenant.weekday() in config.JOURS_LANCEMENT
        and (maintenant.hour, maintenant.minute) >= (heure, minute)
        and dernier_jour != maintenant.date()
    )


def boucle_planificateur(arret: threading.Event):
    dernier_jour = datetime.now(PARIS).date() if datetime.now(PARIS).hour >= 12 else None
    while not arret.is_set():
        maintenant = datetime.now(PARIS)
        if doit_lancer(maintenant, dernier_jour) and taches.lancer("quotidienne", tache_quotidienne):
            dernier_jour = maintenant.date()
        arret.wait(30)


@asynccontextmanager
async def cycle_de_vie(app):
    arret = threading.Event()
    if config.PLANIFICATION_ACTIVE and os.environ.get("PLANIFICATION", "on") != "off":
        threading.Thread(target=boucle_planificateur, args=(arret,), daemon=True).start()
        taches.log(f"Planificateur actif : {config.HEURE_LANCEMENT}, jours {config.JOURS_LANCEMENT}")
    yield
    arret.set()


app = FastAPI(
    title="Agent de candidatures",
    description="Trouve les entreprises autour de chez moi et leur envoie ma candidature.",
    version=VERSION,
    lifespan=cycle_de_vie,
)
DEMARRAGE = time.time()


# ---------------------------------------------------------------------------
# Routes (endpoints)
# ---------------------------------------------------------------------------
class Entreprise(BaseModel):
    id: str
    nom: str
    ville: str = ""
    distance_km: str = ""
    naf: str = ""
    effectif: str = ""
    site: str = ""
    email: str = ""
    statut: str = ""
    date_envoi: str = ""
    note: str = ""


@app.get("/sante", tags=["Supervision"])
def sante():
    """Vérifie que l'API répond. Utilisé par le healthcheck de Docker."""
    return {"statut": "ok", "version": VERSION, "uptime_s": int(time.time() - DEMARRAGE)}


@app.get("/stats", tags=["Supervision"])
def stats():
    """Nombre d'entreprises par statut et envois du jour."""
    entreprises = charger()
    par_statut = Counter(e.get("statut", "") for e in entreprises.values())
    return {
        "total": len(entreprises),
        "par_statut": dict(par_statut),
        "envoyes_aujourdhui": send.envoyes_aujourdhui(entreprises),
        "quota_journalier": config.ENVOIS_PAR_JOUR,
        "tache_en_cours": taches.en_cours,
    }


@app.get("/entreprises", response_model=list[Entreprise], tags=["Entreprises"])
def lister(
    statut: str | None = Query(None, description="pret, envoye, a_enrichir, sans_email…"),
    ville: str | None = None,
    limite: int = Query(50, ge=1, le=2000),
):
    """Liste les entreprises, des plus proches aux plus éloignées."""
    resultat = sorted(charger().values(), key=distance_float)
    if statut:
        resultat = [e for e in resultat if e.get("statut") == statut]
    if ville:
        resultat = [e for e in resultat if ville.lower() in e.get("ville", "").lower()]
    return resultat[:limite]


@app.get("/entreprises/{id_entreprise}/apercu", tags=["Entreprises"])
def apercu(id_entreprise: str):
    """Montre le mail exact que recevrait cette entreprise (rien n'est envoyé)."""
    entreprise = charger().get(id_entreprise)
    if not entreprise:
        raise HTTPException(status_code=404, detail="Entreprise introuvable")
    adresse, _ = send.identifiants()
    objet, texte = send.rediger(entreprise, send.lire_modele(), adresse or "ton.adresse@gmail.com")
    return {"a": entreprise.get("email"), "objet": objet, "texte": texte}


@app.post("/collecte", status_code=202, tags=["Actions"])
def lancer_collecte(max_enrichissements: int = Query(80, ge=1, le=2000), forcer_recherche: bool = False):
    """Lance la recherche d'entreprises et de mails en arrière-plan."""
    if not taches.lancer("collecte", tache_collecte(max_enrichissements, forcer_recherche)):
        raise HTTPException(status_code=409, detail=f"Une tâche tourne déjà : {taches.en_cours}")
    return {"message": "Collecte lancée. Suis-la sur GET /taches."}


@app.post("/envois", status_code=202, tags=["Actions"])
def lancer_envois(nombre: int = Query(config.ENVOIS_PAR_JOUR, ge=1, le=50)):
    """Envoie les candidatures du jour en arrière-plan (respecte le quota journalier)."""
    if not taches.lancer("envoi", tache_envoi(nombre)):
        raise HTTPException(status_code=409, detail=f"Une tâche tourne déjà : {taches.en_cours}")
    return {"message": "Envoi lancé. Suis-le sur GET /taches."}


@app.get("/taches", tags=["Actions"])
def etat_taches(lignes: int = Query(50, ge=1, le=300)):
    """Tâche en cours, historique et dernières lignes du journal."""
    return {
        "en_cours": taches.en_cours,
        "historique": list(taches.historique),
        "journal": list(taches.journal)[-lignes:],
    }
