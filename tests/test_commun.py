import commun
import config


def test_normaliser_enleve_accents_et_formes_juridiques():
    assert commun.normaliser("Société Générale d'Informatique SAS") == "societegeneraledinformatique"
    assert commun.normaliser("ACME (groupe XYZ) SARL") == "acme"


def test_sauvegarder_puis_charger(dossier_temp, entreprise):
    commun.sauvegarder({entreprise["id"]: entreprise})
    relu = commun.charger()
    assert relu[entreprise["id"]]["email"] == "rh@alpha-reseaux.fr"
    assert relu[entreprise["id"]]["statut"] == "pret"


def test_liste_exclure_appliquee(dossier_temp, entreprise, monkeypatch):
    monkeypatch.setattr(config, "EXCLURE", ["alpha"])
    commun.sauvegarder({entreprise["id"]: entreprise})
    assert commun.charger()[entreprise["id"]]["statut"] == "exclu"


def test_entreprise_reprise_si_retiree_de_exclure(dossier_temp, entreprise, monkeypatch):
    monkeypatch.setattr(config, "EXCLURE", ["alpha"])
    commun.sauvegarder(commun.charger() or {entreprise["id"]: entreprise})
    commun.sauvegarder(commun.charger())
    monkeypatch.setattr(config, "EXCLURE", [])
    assert commun.charger()[entreprise["id"]]["statut"] == "a_enrichir"


def test_une_entreprise_deja_contactee_n_est_jamais_exclue(dossier_temp, entreprise, monkeypatch):
    entreprise["statut"] = "envoye"
    monkeypatch.setattr(config, "EXCLURE", ["alpha"])
    commun.sauvegarder({entreprise["id"]: entreprise})
    assert commun.charger()[entreprise["id"]]["statut"] == "envoye"


def test_distance_illisible_classee_en_dernier():
    assert commun.distance_float({"distance_km": "2.5"}) == 2.5
    assert commun.distance_float({"distance_km": ""}) == 99
    assert commun.distance_float({"distance_km": "abc"}) == 99
