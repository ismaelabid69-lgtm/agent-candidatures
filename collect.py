"""
ÉTAPE 1 — Trouve les entreprises informatiques autour de chez toi
et cherche leur adresse mail de contact.

Sources :
  - Annuaire des Entreprises (API officielle de l'État, gratuite, sans clé)
  - OpenStreetMap (gratuit, sans clé) : souvent le site et parfois le mail
  - Optionnel : Google Places, si tu mets GOOGLE_PLACES_KEY dans .env

Résultat : le fichier entreprises.csv (ouvrable dans Excel).

Usage :
  python collect.py                 # recherche + enrichissement
  python collect.py --max 200       # cherche le mail de 200 entreprises
  python collect.py --forcer-recherche
"""
import argparse
import html as html_lib
import math
import os
import re
import time
from datetime import date, timedelta
from urllib.parse import urljoin, urlparse

import requests

import config
from commun import DONNEES, charger, charger_env, distance_float, normaliser, sans_accents, sauvegarder

API_ANNUAIRE = "https://recherche-entreprises.api.gouv.fr/near_point"
API_OVERPASS = "https://overpass-api.de/api/interpreter"
API_PLACES = "https://places.googleapis.com/v1/places:searchText"
FICHIER_DERNIERE_RECHERCHE = DONNEES / ".derniere_recherche"

SESSION = requests.Session()
SESSION.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

ORDRE_EFFECTIFS = ["00", "01", "02", "03", "11", "12", "21", "22", "31",
                   "32", "41", "42", "51", "52", "53"]
LIBELLES_EFFECTIFS = {
    "00": "0", "01": "1-2", "02": "3-5", "03": "6-9", "11": "10-19",
    "12": "20-49", "21": "50-99", "22": "100-199", "31": "200-249",
    "32": "250-499", "41": "500-999", "42": "1000-1999", "51": "2000-4999",
    "52": "5000-9999", "53": "10000+",
}


# ---------------------------------------------------------------------------
# Petits outils
# ---------------------------------------------------------------------------
def distance_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def get_json(url, params=None, essais=4):
    for i in range(essais):
        try:
            r = SESSION.get(url, params=params, timeout=25)
            if r.status_code == 429:  # trop de requêtes : on patiente
                time.sleep(3 * (i + 1))
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"   ! erreur réseau ({exc.__class__.__name__}), nouvel essai…")
            time.sleep(3 * (i + 1))
    return None


def telecharger(url):
    """Renvoie (html, url_finale) ou (None, None)."""
    try:
        r = SESSION.get(url, timeout=12, allow_redirects=True)
        if r.status_code >= 400 or "html" not in r.headers.get("Content-Type", "html"):
            return None, None
        r.encoding = r.apparent_encoding or r.encoding
        return r.text[:600_000], r.url
    except requests.RequestException:
        return None, None


MOTS_COURTS = {"de", "du", "des", "la", "le", "les", "et", "en", "au", "aux", "sur"}


def joli_nom(texte):
    """'ACME RESEAUX ET SYSTEMES' -> 'Acme Reseaux et Systemes' (garde les sigles)."""
    texte = re.sub(r"\s+", " ", texte or "").strip()
    if texte != texte.upper():
        return texte
    mots = []
    for i, mot in enumerate(texte.split(" ")):
        bas = mot.lower()
        if bas in MOTS_COURTS and i > 0:
            mots.append(bas)
        elif len(mot) <= 3:
            mots.append(mot)  # sigles : IBM, SFR, 2CI…
        else:
            mots.append("-".join(p[:1].upper() + p[1:] for p in bas.split("-")))
    return " ".join(mots)


VILLES = {
    "VENISSIEUX": "Vénissieux", "ECULLY": "Écully", "DECINES-CHARPIEU": "Décines-Charpieu",
    "SAINTE-FOY-LES-LYON": "Sainte-Foy-lès-Lyon", "PIERRE-BENITE": "Pierre-Bénite",
    "OULLINS-PIERRE-BENITE": "Oullins-Pierre-Bénite", "LA MULATIERE": "La Mulatière",
    "SEREZIN-DU-RHONE": "Sérézin-du-Rhône", "CHARBONNIERES-LES-BAINS": "Charbonnières-les-Bains",
    "SAINT-PRIEST": "Saint-Priest", "VAULX-EN-VELIN": "Vaulx-en-Velin",
}


def jolie_ville(ville):
    v = (ville or "").strip().upper()
    if not v:
        return ""
    if v.startswith("LYON"):
        return "Lyon"
    if v in VILLES:
        return VILLES[v]
    morceaux = re.split(r"([- ])", v.lower())
    return "".join(
        m if (m in MOTS_COURTS and i > 0) or m in "- " else m[:1].upper() + m[1:]
        for i, m in enumerate(morceaux)
    )


def est_exclue(nom):
    n = normaliser(nom)
    return any(normaliser(x) and normaliser(x) in n for x in config.EXCLURE)


def effectif_ok(code):
    if code not in ORDRE_EFFECTIFS:
        return config.ACCEPTER_EFFECTIF_INCONNU
    return ORDRE_EFFECTIFS.index(code) >= ORDRE_EFFECTIFS.index(config.EFFECTIF_MINIMUM)


# ---------------------------------------------------------------------------
# Source 1 : Annuaire des Entreprises
# ---------------------------------------------------------------------------
def ajouter_depuis_annuaire(res, naf, entreprises):
    siren = res.get("siren")
    if not siren or f"siren:{siren}" in entreprises:
        return False
    if res.get("etat_administratif") not in (None, "A"):  # entreprise fermée
        return False
    complements = res.get("complements") or {}
    if complements.get("est_entrepreneur_individuel") and not config.ACCEPTER_ENTREPRENEURS_INDIVIDUELS:
        return False
    effectif = res.get("tranche_effectif_salarie")
    if not effectif_ok(effectif):
        return False

    # L'établissement le plus proche de chez toi
    etablissements = [e for e in (res.get("matching_etablissements") or [])
                      if e.get("etat_administratif") in (None, "A")]
    meilleur, meilleure_dist = None, None
    for etab in etablissements or [res.get("siege") or {}]:
        try:
            d = distance_km(config.LATITUDE, config.LONGITUDE,
                            float(etab["latitude"]), float(etab["longitude"]))
        except (KeyError, TypeError, ValueError):
            d = None
        if meilleur is None or (d is not None and (meilleure_dist is None or d < meilleure_dist)):
            meilleur, meilleure_dist = etab, d
    etab = meilleur or {}
    if meilleure_dist is not None and meilleure_dist > config.RAYON_KM + 0.5:
        return False

    enseignes = [x for x in (etab.get("liste_enseignes") or []) if x]
    nom = joli_nom(enseignes[0] if enseignes else
                   res.get("nom_raison_sociale") or res.get("nom_complet") or "")
    if not nom or est_exclue(nom):
        return False

    entreprises[f"siren:{siren}"] = {
        "id": f"siren:{siren}",
        "nom": nom,
        "ville": jolie_ville(etab.get("libelle_commune")),
        "adresse": (etab.get("adresse") or "").title(),
        "distance_km": f"{meilleure_dist:.1f}" if meilleure_dist is not None else "",
        "naf": naf,
        "effectif": LIBELLES_EFFECTIFS.get(effectif, "?"),
        "statut": "a_enrichir",
    }
    return True


def rechercher_annuaire(entreprises):
    nouvelles = 0
    for naf in config.CODES_NAF:
        page = 1
        while True:
            data = get_json(API_ANNUAIRE, {
                "lat": config.LATITUDE, "long": config.LONGITUDE,
                "radius": config.RAYON_KM, "activite_principale": naf,
                "page": page, "per_page": 25,
            })
            if not data:
                break
            for res in data.get("results") or []:
                nouvelles += ajouter_depuis_annuaire(res, naf, entreprises)
            if page >= (data.get("total_pages") or 1) or page >= 400:
                break
            page += 1
            time.sleep(0.2)  # l'API autorise ~7 requêtes/seconde
        print(f"   {naf} : terminé ({nouvelles} nouvelles au total)")
    return nouvelles


# ---------------------------------------------------------------------------
# Source 2 : OpenStreetMap (sites web et mails publiés sur la carte)
# ---------------------------------------------------------------------------
def rechercher_osm(entreprises):
    rayon_m = int(config.RAYON_KM * 1000)
    autour = f"(around:{rayon_m},{config.LATITUDE},{config.LONGITUDE})"
    requete = f"""[out:json][timeout:90];
(
  nwr{autour}["office"~"^(it|telecommunication)$"]["name"];
  nwr{autour}["shop"="computer"]["name"];
);
out center tags;"""
    try:
        r = SESSION.post(API_OVERPASS, data={"data": requete}, timeout=120)
        r.raise_for_status()
        elements = r.json().get("elements", [])
    except (requests.RequestException, ValueError) as exc:
        print(f"   ! OpenStreetMap indisponible ({exc.__class__.__name__}), on passe.")
        return 0

    par_nom = {normaliser(e["nom"]): e for e in entreprises.values()}
    nouvelles = 0
    for el in elements:
        tags = el.get("tags", {})
        nom = tags.get("name", "").strip()
        if not nom or est_exclue(nom):
            continue
        site = tags.get("website") or tags.get("contact:website") or ""
        email = (tags.get("email") or tags.get("contact:email") or "").split(";")[0].strip()
        existante = par_nom.get(normaliser(nom))
        if existante:  # déjà trouvée dans l'annuaire : on complète
            if site and not existante.get("site"):
                existante["site"] = site
            if email and not existante.get("email"):
                existante["email"], existante["source_email"] = email, "openstreetmap"
            continue
        cle = f"osm:{el['type']}{el['id']}"
        if cle in entreprises:
            continue
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        d = distance_km(config.LATITUDE, config.LONGITUDE, lat, lon) if lat and lon else None
        entreprises[cle] = {
            "id": cle, "nom": nom,
            "ville": jolie_ville(tags.get("addr:city", "")),
            "adresse": " ".join(x for x in (tags.get("addr:housenumber"), tags.get("addr:street")) if x),
            "distance_km": f"{d:.1f}" if d is not None else "",
            "naf": "95.11Z" if tags.get("shop") == "computer" else "62.09Z",
            "site": site, "email": email,
            "source_email": "openstreetmap" if email else "",
            "statut": "a_enrichir",
        }
        par_nom[normaliser(nom)] = entreprises[cle]
        nouvelles += 1
    return nouvelles


# ---------------------------------------------------------------------------
# Trouver le site web
# ---------------------------------------------------------------------------
def chercher_site_google(e):
    cle = os.environ.get("GOOGLE_PLACES_KEY")
    if not cle:
        return ""
    try:
        r = SESSION.post(API_PLACES, timeout=20, headers={
            "X-Goog-Api-Key": cle,
            "X-Goog-FieldMask": "places.displayName,places.websiteUri",
        }, json={
            "textQuery": f"{e['nom']} {e.get('ville', '')}",
            "languageCode": "fr", "pageSize": 3,
            "locationBias": {"circle": {
                "center": {"latitude": config.LATITUDE, "longitude": config.LONGITUDE},
                "radius": 30000.0}},
        })
        r.raise_for_status()
        cible = normaliser(e["nom"])
        for lieu in r.json().get("places", []):
            nom_lieu = normaliser((lieu.get("displayName") or {}).get("text", ""))
            if lieu.get("websiteUri") and (cible in nom_lieu or nom_lieu in cible):
                return lieu["websiteUri"]
    except (requests.RequestException, ValueError):
        pass
    return ""


def page_correspond(html, e):
    texte = re.sub(r"[^a-z0-9]", "", sans_accents(html_lib.unescape(html)).lower())
    if normaliser(e["nom"]) not in texte:
        return False
    siren = e["id"].split(":")[1] if e["id"].startswith("siren:") else ""
    indices = [siren, normaliser(e.get("ville", "")), "lyon", "69"]
    return any(i and i in texte for i in indices)


def deviner_site(e):
    """Essaie nom-entreprise.fr / .com et vérifie que la page parle bien d'elle."""
    base = sans_accents(e["nom"]).lower()
    base = re.sub(r"\(.*?\)", " ", base)
    base = re.sub(r"[^a-z0-9 ]", " ", re.sub(r"[-'’&]", " ", base))
    mots = [m for m in base.split() if not re.fullmatch(r"sas|sasu|sarl|eurl|sa|snc", m)]
    if not mots or len("".join(mots)) < 4:
        return ""
    for nom_domaine in dict.fromkeys(["".join(mots), "-".join(mots)]):
        for ext in (".fr", ".com"):
            html, url = telecharger(f"https://www.{nom_domaine}{ext}")
            if html and page_correspond(html, e):
                return url
    return ""


# ---------------------------------------------------------------------------
# Trouver l'adresse mail sur le site
# ---------------------------------------------------------------------------
REGEX_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
MOTS_PAGES = ("contact", "mention", "legal", "recrut", "carriere", "career", "emploi",
              "job", "rejoindre", "join", "propos", "about", "qui-sommes", "societe", "equipe")
A_IGNORER = ("example", "exemple", "sentry", "wixpress", "domain.", "votre", "your", "nom@",
             "prenom", "@2x", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", "noreply",
             "no-reply", "donotreply", "rgpd", "dpo@", "privacy", "cnil", "factur", "compta",
             "invoice", "abuse@", "unsubscribe", "@sentry", "user@", "test@")
WEBMAILS = {"gmail.com", "orange.fr", "free.fr", "outlook.fr", "outlook.com", "hotmail.fr",
            "hotmail.com", "yahoo.fr", "laposte.net", "sfr.fr", "wanadoo.fr", "icloud.com"}
PRIORITES = ["recrutement", "rh", "jobs", "job", "emploi", "carriere", "career", "candidature",
             "stage", "talent", "contact", "info", "accueil", "bonjour", "hello", "agence",
             "direction", "secretariat"]


def domaine_racine(hote):
    parties = (hote or "").lower().removeprefix("www.").split(".")
    return ".".join(parties[-2:])


def decoder_cloudflare(hexa):
    try:
        cle = int(hexa[:2], 16)
        return "".join(chr(int(hexa[i:i + 2], 16) ^ cle) for i in range(2, len(hexa), 2))
    except ValueError:
        return ""


def extraire_emails(html):
    texte = html_lib.unescape(html)
    texte = re.sub(r"\s*[\[\(\{]\s*(?:at|arobase|@)\s*[\]\)\}]\s*", "@", texte, flags=re.I)
    texte = re.sub(r"\s*[\[\(\{]\s*(?:dot|point)\s*[\]\)\}]\s*", ".", texte, flags=re.I)
    trouves = set(REGEX_EMAIL.findall(texte))
    for hexa in re.findall(r'data-cfemail="([0-9a-fA-F]+)"', html):
        trouves.add(decoder_cloudflare(hexa))
    return {m.strip(".").lower() for m in trouves
            if m and not any(x in m.lower() for x in A_IGNORER)}


def note_email(email, domaine_site):
    local, _, dom = email.partition("@")
    if domaine_racine(dom) == domaine_site:
        note = 100
    elif dom in WEBMAILS:
        note = 30
    else:
        return -1  # mail d'un autre domaine : souvent l'agence qui a fait le site
    for i, prefixe in enumerate(PRIORITES):
        if local.startswith(prefixe):
            return note + 50 - i
    return note + 5


def chercher_email(site):
    if not site.startswith("http"):
        site = "https://" + site
    html, url = telecharger(site)
    if not html:
        return ""
    domaine = domaine_racine(urlparse(url).hostname)
    emails = extraire_emails(html)

    liens = []
    for lien in re.findall(r'href=["\']([^"\'#]+)["\']', html, flags=re.I):
        complet = urljoin(url, lien)
        if domaine_racine(urlparse(complet).hostname) == domaine and \
                any(m in complet.lower() for m in MOTS_PAGES):
            liens.append(complet.split("?")[0])
    if not liens:
        liens = [urljoin(url, p) for p in ("/contact", "/mentions-legales", "/nous-contacter")]
    for lien in list(dict.fromkeys(liens))[:5]:
        page, _ = telecharger(lien)
        if page:
            emails |= extraire_emails(page)

    classes = sorted((note_email(m, domaine), m) for m in emails)
    classes = [(n, m) for n, m in classes if n > 0]
    return classes[-1][1] if classes else ""


def enrichir(e):
    if not e.get("site"):
        e["site"] = chercher_site_google(e) or deviner_site(e)
    if not e.get("email") and e.get("site"):
        email = chercher_email(e["site"])
        if email:
            e["email"], e["source_email"] = email, e["site"]
    if e.get("email"):
        e["statut"] = "pret"
    else:
        e["statut"] = "sans_email" if e.get("site") else "sans_site"


# ---------------------------------------------------------------------------
def recherche_necessaire(forcer):
    if forcer or not FICHIER_DERNIERE_RECHERCHE.exists():
        return True
    try:
        derniere = date.fromisoformat(FICHIER_DERNIERE_RECHERCHE.read_text().strip())
    except ValueError:
        return True
    return date.today() - derniere >= timedelta(days=config.JOURS_ENTRE_RECHERCHES)


def executer(max_enrichissements=None, forcer_recherche=False, journal=print):
    """Recherche les entreprises puis leurs mails. Renvoie le nombre d'entreprises par statut.
    Utilisée par la ligne de commande, l'API et le planificateur."""
    max_enrichissements = config.MAX_ENRICHISSEMENTS if max_enrichissements is None else max_enrichissements
    charger_env()
    entreprises = charger()

    if recherche_necessaire(forcer_recherche):
        journal(f"1) Annuaire des Entreprises (rayon {config.RAYON_KM} km)…")
        n1 = rechercher_annuaire(entreprises)
        journal("2) OpenStreetMap…")
        n2 = rechercher_osm(entreprises)
        journal(f"   -> {n1 + n2} nouvelles entreprises ajoutées")
        FICHIER_DERNIERE_RECHERCHE.write_text(date.today().isoformat())
        sauvegarder(entreprises)
    else:
        journal("Annuaire déjà consulté récemment, on passe directement aux mails.")

    a_faire = sorted((e for e in entreprises.values() if e.get("statut") == "a_enrichir"),
                     key=distance_float)[:max_enrichissements]
    journal(f"3) Recherche du site et du mail pour {len(a_faire)} entreprises…")
    for i, e in enumerate(a_faire, 1):
        try:
            enrichir(e)
        except Exception as exc:  # une page bizarre ne doit pas tout arrêter
            e["statut"], e["note"] = "sans_site", f"erreur : {exc}"[:150]
        journal(f"   [{i}/{len(a_faire)}] {e['nom'][:40]:40} -> {e.get('email') or e['statut']}")
        if i % 10 == 0:
            sauvegarder(entreprises)
    sauvegarder(entreprises)

    statuts = {}
    for e in entreprises.values():
        statuts[e.get("statut", "")] = statuts.get(e.get("statut", ""), 0) + 1
    journal("Bilan : " + ", ".join(f"{k} = {v}" for k, v in sorted(statuts.items())))
    return statuts


def main():
    parser = argparse.ArgumentParser(description="Trouve les entreprises et leurs mails.")
    parser.add_argument("--max", type=int, default=config.MAX_ENRICHISSEMENTS,
                        help="nombre d'entreprises dont on cherche le mail")
    parser.add_argument("--forcer-recherche", action="store_true",
                        help="ré-interroge l'annuaire même si c'est récent")
    args = parser.parse_args()
    statuts = executer(args.max, args.forcer_recherche)
    print(f"Prêtes à recevoir ta candidature : {statuts.get('pret', 0)}")


if __name__ == "__main__":
    main()
