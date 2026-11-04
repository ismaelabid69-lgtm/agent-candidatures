"""
ÉTAPE 2 — Envoie ta candidature aux entreprises prêtes (20 par jour maximum).

Usage :
  python send.py --apercu     # affiche les mails du jour SANS rien envoyer
  python send.py --test       # t'envoie UN mail d'exemple à toi-même
  python send.py              # envoie pour de vrai (jusqu'à 20 aujourd'hui)
"""
import argparse
import hashlib
import os
import random
import re
import smtplib
import ssl
import sys
import time
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import config
from commun import DONNEES, DOSSIER, charger, charger_env, distance_float, sauvegarder

SECTIONS_OBLIGATOIRES = ["OBJETS", "SALUTATIONS", "INTRODUCTIONS", "CORPS",
                         "CONCLUSIONS", "POLITESSES", "SIGNATURE"]


def lire_modele():
    sections, courante = {}, None
    for ligne in (DOSSIER / "modele_mail.txt").read_text(encoding="utf-8").splitlines():
        if ligne.startswith("#"):
            continue
        titre = re.fullmatch(r"\[([A-Z_ ]+)\]\s*", ligne)
        if titre:
            courante = titre.group(1).strip()
            sections[courante] = [[]]
        elif courante and ligne.strip() == "---":
            sections[courante].append([])
        elif courante:
            sections[courante][-1].append(ligne)
    modele = {nom: ["\n".join(v).strip() for v in variantes if "\n".join(v).strip()]
              for nom, variantes in sections.items()}
    manquantes = [s for s in SECTIONS_OBLIGATOIRES if not modele.get(s)]
    if manquantes:
        sys.exit(f"modele_mail.txt : section(s) manquante(s) ou vide(s) : {', '.join(manquantes)}")
    return modele


class Remplisseur(dict):
    def __missing__(self, cle):
        return "{" + cle + "}"


def choisir(variantes, valeurs, graine):
    """Choisit une variante (toujours la même pour une entreprise donnée),
    en évitant celles qui utilisent une info vide (ex : ville inconnue)."""
    vides = [k for k, v in valeurs.items() if not v]
    utilisables = [v for v in variantes if not any("{" + k + "}" in v for k in vides)] or variantes
    indice = int(hashlib.md5(graine.encode()).hexdigest(), 16) % len(utilisables)
    return utilisables[indice].format_map(Remplisseur(valeurs))


def rediger(e, modele, mon_email):
    valeurs = {
        "entreprise": e["nom"], "ville": e.get("ville", ""),
        "secteur": config.CODES_NAF.get(e.get("naf", ""), "de l'informatique"),
        "prenom": config.PRENOM, "nom": config.NOM, "telephone": config.TELEPHONE,
        "email": mon_email, "linkedin": config.LINKEDIN,
        "types_contrat": config.TYPES_CONTRAT, "disponibilite": config.DISPONIBILITE,
    }
    p = lambda section: choisir(modele[section], valeurs, e["id"] + section)
    signature = "\n".join(ligne for ligne in p("SIGNATURE").splitlines() if ligne.strip())
    morceaux = [p("SALUTATIONS"), p("INTRODUCTIONS"), p("CORPS"), p("CONCLUSIONS"),
                p("POLITESSES"), signature]
    if modele.get("PIED"):
        morceaux.append("—\n" + p("PIED"))
    return p("OBJETS"), "\n\n".join(morceaux) + "\n"


def _ouvrir(hote, port, adresse, mot_de_passe):
    if port == 465:
        serveur = smtplib.SMTP_SSL(hote, port, context=ssl.create_default_context(), timeout=60)
    else:
        serveur = smtplib.SMTP(hote, port, timeout=60)
        serveur.ehlo()
        if port == 587:
            serveur.starttls(context=ssl.create_default_context())
            serveur.ehlo()
    try:
        if mot_de_passe:
            serveur.login(adresse, mot_de_passe)
    except Exception:
        serveur.close()
        raise
    return serveur


_PORT_QUI_MARCHE = None


def connexion(adresse, mot_de_passe):
    """Se connecte à Gmail. Si le port 465 est coupé (souvent un antivirus
    qui filtre les mails), on réessaie automatiquement sur le port 587."""
    global _PORT_QUI_MARCHE
    hote = os.environ.get("SMTP_SERVEUR", config.SMTP_SERVEUR)
    port = int(os.environ.get("SMTP_PORT", config.SMTP_PORT))
    ports = [_PORT_QUI_MARCHE] if _PORT_QUI_MARCHE else [port] + [p for p in (587, 465) if p != port]
    derniere_erreur = None
    for p in ports:
        try:
            serveur = _ouvrir(hote, p, adresse, mot_de_passe)
            _PORT_QUI_MARCHE = p
            return serveur
        except smtplib.SMTPAuthenticationError:
            raise
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, ssl.SSLError, OSError) as exc:
            print(f"   (port {p} indisponible : {exc.__class__.__name__}, on essaie un autre port…)")
            derniere_erreur = exc
    raise derniere_erreur


def envoyer(adresse, mot_de_passe, destinataire, objet, texte, cv):
    msg = EmailMessage()
    msg["From"] = formataddr((f"{config.PRENOM} {config.NOM}", adresse))
    msg["To"] = destinataire
    msg["Subject"] = objet
    msg["Message-ID"] = make_msgid(domain=adresse.split("@")[-1])
    msg.set_content(texte)
    msg.add_attachment(cv.read_bytes(), maintype="application", subtype="pdf",
                       filename=config.NOM_PIECE_JOINTE)
    with connexion(adresse, mot_de_passe) as serveur:
        serveur.send_message(msg)


class ErreurEnvoi(Exception):
    """Problème qui empêche d'envoyer (identifiants, CV manquant…)."""


def identifiants():
    charger_env()
    adresse = os.environ.get("GMAIL_ADRESSE", "").strip()
    mot_de_passe = os.environ.get("GMAIL_MOT_DE_PASSE_APP", "").replace(" ", "")
    return adresse, mot_de_passe


def chemin_cv():
    return DONNEES / config.FICHIER_CV


def entreprises_pretes(entreprises):
    return sorted((e for e in entreprises.values()
                   if e.get("statut") == "pret" and e.get("email")), key=distance_float)


def envoyes_aujourdhui(entreprises):
    aujourd_hui = datetime.now().strftime("%Y-%m-%d")
    return sum(1 for e in entreprises.values() if e.get("date_envoi", "").startswith(aujourd_hui))


def envoyer_lot(nombre=None, journal=print):
    """Envoie jusqu'à `nombre` candidatures aujourd'hui. Renvoie le nombre envoyé.
    Utilisée par la ligne de commande, l'API et le planificateur."""
    nombre = config.ENVOIS_PAR_JOUR if nombre is None else nombre
    adresse, mot_de_passe = identifiants()
    if not adresse or not mot_de_passe:
        raise ErreurEnvoi("Il manque GMAIL_ADRESSE ou GMAIL_MOT_DE_PASSE_APP (fichier .env).")
    cv = chemin_cv()
    if not cv.exists():
        raise ErreurEnvoi(f"CV introuvable : {cv}")
    modele = lire_modele()
    entreprises = charger()
    deja_contactes = {e["email"].lower() for e in entreprises.values()
                      if e.get("statut") == "envoye" and e.get("email")}
    prets = entreprises_pretes(entreprises)
    restant = max(0, nombre - envoyes_aujourdhui(entreprises))
    if not prets or restant == 0:
        journal(f"Rien à envoyer (prêtes : {len(prets)}, quota restant aujourd'hui : {restant}).")
        return 0

    journal(f"Envoi de {min(restant, len(prets))} candidatures (pause de "
            f"{config.DELAI_MIN_SECONDES // 60} à {config.DELAI_MAX_SECONDES // 60} min entre chaque)…")
    envoyes, erreurs_suivies = 0, 0
    for e in prets:
        if envoyes >= restant:
            break
        if e["email"].lower() in deja_contactes:  # même adresse pour deux sociétés
            e["statut"], e["note"] = "doublon", "adresse déjà contactée"
            sauvegarder(entreprises)
            continue
        if envoyes > 0:
            time.sleep(random.uniform(config.DELAI_MIN_SECONDES, config.DELAI_MAX_SECONDES))
        objet, texte = rediger(e, modele, adresse)
        try:
            envoyer(adresse, mot_de_passe, e["email"], objet, texte, cv)
        except smtplib.SMTPAuthenticationError as exc:
            raise ErreurEnvoi("Gmail refuse la connexion : vérifie ton mot de passe d'application.") from exc
        except smtplib.SMTPRecipientsRefused:
            e["statut"], e["note"] = "erreur", "adresse refusée"
            journal(f"   x {e['nom']} : adresse refusée ({e['email']})")
        except (smtplib.SMTPException, OSError) as exc:
            erreurs_suivies += 1
            e["note"] = f"échec d'envoi : {exc}"[:150]
            journal(f"   x {e['nom']} : {exc}")
            if erreurs_suivies >= 3:
                journal("Trois erreurs d'affilée : on arrête pour aujourd'hui.")
                break
        else:
            erreurs_suivies = 0
            envoyes += 1
            deja_contactes.add(e["email"].lower())
            e["statut"] = "envoye"
            e["date_envoi"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            journal(f"   + [{envoyes}/{restant}] {e['nom']} ({e['email']})")
        sauvegarder(entreprises)

    journal(f"Terminé : {envoyes} candidature(s) envoyée(s) aujourd'hui.")
    return envoyes


def main():
    parser = argparse.ArgumentParser(description="Envoie les candidatures du jour.")
    parser.add_argument("--apercu", action="store_true", help="affiche sans envoyer")
    parser.add_argument("--test", action="store_true", help="t'envoie un mail d'exemple")
    parser.add_argument("--nombre", type=int, default=config.ENVOIS_PAR_JOUR)
    args = parser.parse_args()

    adresse, mot_de_passe = identifiants()
    modele = lire_modele()
    prets = entreprises_pretes(charger())
    if not prets:
        sys.exit("Aucune entreprise prête. Lance d'abord : python collect.py")

    if args.apercu:
        for e in prets[:args.nombre]:
            objet, texte = rediger(e, modele, adresse or "ton.adresse@gmail.com")
            print("=" * 70)
            print(f"À : {e['email']}   ({e['nom']}, {e.get('ville')}, {e.get('distance_km')} km)")
            print(f"Objet : {objet}\n\n{texte}")
        print(f"{len(prets)} entreprises prêtes au total. Rien n'a été envoyé.")
        return

    if args.test:
        if not adresse or not mot_de_passe:
            sys.exit("Il manque GMAIL_ADRESSE ou GMAIL_MOT_DE_PASSE_APP (fichier .env). Voir le guide.")
        cv = chemin_cv()
        if not cv.exists():
            sys.exit(f"CV introuvable : {cv}")
        objet, texte = rediger(prets[0], modele, adresse)
        try:
            envoyer(adresse, mot_de_passe, adresse, "[TEST] " + objet, texte, cv)
        except smtplib.SMTPAuthenticationError:
            sys.exit("Gmail refuse le mot de passe : vérifie le code de 16 lettres dans .env "
                     "(que des minuscules, pas de I majuscule à la place d'un l).")
        except (smtplib.SMTPException, OSError) as exc:
            sys.exit(f"Impossible de joindre Gmail ({exc}). Un antivirus ou un pare-feu bloque "
                     "peut-être l'envoi de mails : voir le README.")
        print(f"Mail de test envoyé à {adresse} (exemple pour {prets[0]['nom']}). Va vérifier ta boîte !")
        return

    try:
        envoyer_lot(args.nombre)
    except ErreurEnvoi as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
