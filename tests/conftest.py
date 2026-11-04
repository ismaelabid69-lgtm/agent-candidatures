"""Chaque test travaille dans un dossier temporaire : on ne touche jamais
au vrai entreprises.csv ni au vrai .env."""
import pytest

import commun


@pytest.fixture
def dossier_temp(tmp_path, monkeypatch):
    monkeypatch.setattr(commun, "FICHIER_SUIVI", tmp_path / "entreprises.csv")
    return tmp_path


@pytest.fixture
def entreprise():
    return {
        "id": "siren:123456789", "nom": "Alpha Reseaux", "ville": "Vénissieux",
        "naf": "62.02B", "email": "rh@alpha-reseaux.fr", "statut": "pret", "distance_km": "0.4",
    }
