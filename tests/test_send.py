import smtplib

import pytest

import send


@pytest.fixture
def modele():
    return send.lire_modele()


def test_modele_contient_toutes_les_sections(modele):
    for section in send.SECTIONS_OBLIGATOIRES:
        assert modele[section], f"section {section} vide"


def test_mail_personnalise(modele, entreprise):
    objet, texte = send.rediger(entreprise, modele, "moi@gmail.com")
    assert objet
    assert "{" not in objet + texte, "une variable n'a pas été remplacée"
    assert "moi@gmail.com" in texte


def test_meme_entreprise_meme_mail(modele, entreprise):
    assert send.rediger(entreprise, modele, "a@b.fr") == send.rediger(entreprise, modele, "a@b.fr")


def test_les_mails_varient_d_une_entreprise_a_l_autre(modele, entreprise):
    mails = set()
    for i in range(30):
        e = dict(entreprise, id=f"siren:{i}", nom=f"Entreprise {i}")
        mails.add(send.rediger(e, modele, "a@b.fr")[1].replace(e["nom"], ""))
    assert len(mails) > 5


def test_ville_inconnue_ne_laisse_pas_de_trou(modele, entreprise):
    for i in range(30):
        e = dict(entreprise, id=f"siren:{i}", ville="")
        _, texte = send.rediger(e, modele, "a@b.fr")
        assert " à ," not in texte and "installée à ," not in texte


def test_bascule_sur_le_port_587_si_le_465_coupe(monkeypatch):
    essais = []

    def faux_serveur(hote, port, adresse, mot_de_passe):
        essais.append(port)
        if port == 465:
            raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
        return "connecte"

    monkeypatch.setattr(send, "_ouvrir", faux_serveur)
    monkeypatch.setattr(send, "_PORT_QUI_MARCHE", None)
    assert send.connexion("a@b.fr", "x") == "connecte"
    assert essais == [465, 587]


def test_mauvais_mot_de_passe_pas_de_nouvel_essai(monkeypatch):
    def refus(*args):
        raise smtplib.SMTPAuthenticationError(535, b"refuse")

    monkeypatch.setattr(send, "_ouvrir", refus)
    monkeypatch.setattr(send, "_PORT_QUI_MARCHE", None)
    with pytest.raises(smtplib.SMTPAuthenticationError):
        send.connexion("a@b.fr", "x")
