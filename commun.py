"""Fonctions partagées : lecture/écriture du fichier de suivi, mots de passe, noms."""
import csv
import os
import re
import sys
import unicodedata
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
# Dossier des données (CSV, CV…) : le sous-dossier "donnees" s'il existe.
# Dans Docker, la variable DOSSIER_DONNEES pointe vers le volume /data.
DONNEES = Path(os.environ.get("DOSSIER_DONNEES") or
               (DOSSIER / "donnees" if (DOSSIER / "donnees").is_dir() else DOSSIER))
FICHIER_SUIVI = DONNEES / "entreprises.csv"

COLONNES = [
    "id", "nom", "ville", "adresse", "distance_km", "naf", "effectif",
    "site", "email", "source_email", "statut", "date_envoi", "note",
]


def charger():
    """Lit entreprises.csv et renvoie un dict {id: ligne}."""
    if not FICHIER_SUIVI.exists():
        return {}
    with open(FICHIER_SUIVI, newline="", encoding="utf-8-sig") as f:
        entreprises = {ligne["id"]: ligne for ligne in csv.DictReader(f, delimiter=";")}
    # Applique la liste EXCLURE de config.py, même aux entreprises déjà trouvées
    import config
    motifs = [normaliser(x) for x in getattr(config, "EXCLURE", []) if normaliser(x)]
    for e in entreprises.values():
        if e.get("statut") not in ("envoye", "exclu") and \
                any(m in normaliser(e.get("nom", "")) for m in motifs):
            e["statut"], e["note"] = "exclu", "exclu via config.py"
        elif e.get("statut") == "exclu" and e.get("note") == "exclu via config.py" and \
                not any(m in normaliser(e.get("nom", "")) for m in motifs):
            e["statut"], e["note"] = "a_enrichir", ""  # retirée de EXCLURE : on la reprend
    return entreprises


def sauvegarder(entreprises):
    """Écrit entreprises.csv (séparateur ; pour qu'Excel l'ouvre proprement)."""
    temporaire = FICHIER_SUIVI.with_suffix(".tmp")
    with open(temporaire, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for e in entreprises.values():
            w.writerow({c: e.get(c, "") for c in COLONNES})
    try:
        os.replace(temporaire, FICHIER_SUIVI)
    except PermissionError:
        sys.exit("entreprises.csv est ouvert dans Excel : ferme-le puis relance.")


def charger_env():
    """Charge le fichier .env (identifiants) dans les variables d'environnement."""
    chemin = DOSSIER / ".env"
    if not chemin.exists():
        return  # dans Docker, les variables arrivent directement par docker-compose
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


def sans_accents(texte):
    texte = unicodedata.normalize("NFKD", texte or "")
    return "".join(c for c in texte if not unicodedata.combining(c))


FORMES_JURIDIQUES = r"\b(sas|sasu|sarl|sarlu|eurl|sa|snc|sci|scop|selarl)\b"


def normaliser(nom):
    """'ACME Informatique SAS' -> 'acmeinformatique' (pour comparer des noms)."""
    texte = sans_accents(nom).lower()
    texte = re.sub(r"\(.*?\)", " ", texte)
    texte = re.sub(FORMES_JURIDIQUES, " ", texte)
    return re.sub(r"[^a-z0-9]", "", texte)


def distance_float(e):
    try:
        return float(e.get("distance_km") or 99)
    except ValueError:
        return 99.0
