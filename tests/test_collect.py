import collect
import config


def resultat_api(**changements):
    res = {
        "siren": "123456789", "nom_raison_sociale": "ALPHA RESEAUX ET SYSTEMES",
        "etat_administratif": "A", "tranche_effectif_salarie": "11",
        "complements": {"est_entrepreneur_individuel": False},
        "matching_etablissements": [{
            "latitude": "45.70", "longitude": "4.89", "libelle_commune": "VENISSIEUX",
            "adresse": "12 RUE DU TEST 69200 VENISSIEUX", "etat_administratif": "A",
        }],
    }
    res.update(changements)
    return res


def test_entreprise_valide_ajoutee():
    entreprises = {}
    assert collect.ajouter_depuis_annuaire(resultat_api(), "62.02B", entreprises)
    e = entreprises["siren:123456789"]
    assert e["nom"] == "Alpha Reseaux et Systemes"
    assert e["ville"] == "Vénissieux"
    assert e["statut"] == "a_enrichir"
    assert float(e["distance_km"]) < 1


def test_trop_petite_entreprise_ignoree():
    assert not collect.ajouter_depuis_annuaire(resultat_api(tranche_effectif_salarie="01"), "62.01Z", {})


def test_entreprise_fermee_ignoree():
    assert not collect.ajouter_depuis_annuaire(resultat_api(etat_administratif="C"), "62.01Z", {})


def test_entreprise_hors_rayon_ignoree():
    loin = [{"latitude": "45.95", "longitude": "4.89", "etat_administratif": "A"}]
    assert not collect.ajouter_depuis_annuaire(resultat_api(matching_etablissements=loin), "62.01Z", {})


def test_entreprise_exclue_ignoree(monkeypatch):
    monkeypatch.setattr(config, "EXCLURE", ["alpha"])
    assert not collect.ajouter_depuis_annuaire(resultat_api(), "62.01Z", {})


def test_distance_lyon_venissieux():
    # Place Bellecour -> centre de Vénissieux : environ 6 km
    assert 5 < collect.distance_km(45.7578, 4.8320, 45.6975, 4.8867) < 9


def test_extraction_des_mails_et_pieges():
    cle = 0x42
    cloudflare = f"{cle:02x}" + "".join(f"{ord(c) ^ cle:02x}" for c in "rh@alpha.fr")
    html = f"""<a href="mailto:contact@alpha.fr">x</a> recrutement [at] alpha.fr
    <img src="logo@2x.png"> noreply@alpha.fr <span data-cfemail="{cloudflare}"></span>"""
    assert collect.extraire_emails(html) == {"contact@alpha.fr", "recrutement@alpha.fr", "rh@alpha.fr"}


def test_priorite_recrutement_puis_contact():
    notes = {m: collect.note_email(m, "alpha.fr")
             for m in ("recrutement@alpha.fr", "contact@alpha.fr", "jean@alpha.fr")}
    assert notes["recrutement@alpha.fr"] > notes["contact@alpha.fr"] > notes["jean@alpha.fr"]


def test_mail_d_un_autre_domaine_refuse():
    assert collect.note_email("dev@agence-web.com", "alpha.fr") < 0


def test_mise_en_forme_des_noms_et_villes():
    assert collect.joli_nom("SFR BUSINESS") == "SFR Business"
    assert collect.joli_nom("Déjà Bien Écrit") == "Déjà Bien Écrit"
    assert collect.jolie_ville("LYON 7EME") == "Lyon"
    assert collect.jolie_ville("CALUIRE-ET-CUIRE") == "Caluire-et-Cuire"
