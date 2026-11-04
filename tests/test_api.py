import threading
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

import api
import collect
import commun
import config


@pytest.fixture
def client(dossier_temp, entreprise, monkeypatch):
    monkeypatch.setattr(config, "PLANIFICATION_ACTIVE", False)
    monkeypatch.setenv("GMAIL_ADRESSE", "moi@gmail.com")
    autre = dict(entreprise, id="siren:2", nom="Beta Telecom", ville="Bron",
                 statut="envoye", distance_km="3.0", email="contact@beta.fr")
    commun.sauvegarder({entreprise["id"]: entreprise, autre["id"]: autre})
    return TestClient(api.app)


def test_sante(client):
    r = client.get("/sante")
    assert r.status_code == 200
    assert r.json()["statut"] == "ok"


def test_stats(client):
    data = client.get("/stats").json()
    assert data["total"] == 2
    assert data["par_statut"] == {"pret": 1, "envoye": 1}


def test_filtre_par_statut(client):
    r = client.get("/entreprises", params={"statut": "pret"})
    assert [e["nom"] for e in r.json()] == ["Alpha Reseaux"]


def test_filtre_par_ville(client):
    assert [e["nom"] for e in client.get("/entreprises?ville=bron").json()] == ["Beta Telecom"]


def test_apercu_du_mail(client):
    data = client.get("/entreprises/siren:123456789/apercu").json()
    assert data["a"] == "rh@alpha-reseaux.fr"
    assert "Alpha Reseaux" in data["objet"] + data["texte"]


def test_entreprise_inconnue_404(client):
    assert client.get("/entreprises/siren:000/apercu").status_code == 404


def test_une_seule_tache_a_la_fois(client, monkeypatch):
    debloque = threading.Event()
    monkeypatch.setattr(collect, "executer", lambda *a, **k: debloque.wait(5) and {"pret": 1})
    assert client.post("/collecte").status_code == 202
    assert client.post("/envois").status_code == 409   # refusé : la collecte tourne
    debloque.set()
    for _ in range(50):
        if api.taches.en_cours is None:
            break
        threading.Event().wait(0.05)
    assert client.get("/taches").json()["historique"][0]["tache"] == "collecte"


@pytest.mark.parametrize("moment, dernier_jour, attendu", [
    (datetime(2026, 11, 2, 9, 30), None, True),                    # lundi après l'heure
    (datetime(2026, 11, 2, 8, 0), None, False),                    # trop tôt
    (datetime(2026, 11, 7, 10, 0), None, False),                   # samedi
    (datetime(2026, 11, 2, 9, 30), datetime(2026, 11, 2).date(), False),  # déjà fait
])
def test_planificateur(monkeypatch, moment, dernier_jour, attendu):
    monkeypatch.setattr(config, "HEURE_LANCEMENT", "09:10")
    monkeypatch.setattr(config, "JOURS_LANCEMENT", [0, 1, 2, 3, 4])
    assert api.doit_lancer(moment, dernier_jour) is attendu
