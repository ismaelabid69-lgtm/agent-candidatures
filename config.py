# =====================================================================
#  CONFIGURATION — c'est le seul fichier que tu as besoin de modifier
#  (avec modele_mail.txt pour le texte du mail).
# =====================================================================

# ---------- Tes informations (utilisées dans la signature du mail) ----------
# Tes vraies infos vont dans config_perso.py (ignoré par Git, jamais publié).
PRENOM = "Prénom"
NOM = "NOM"
TELEPHONE = "06 00 00 00 00"
LINKEDIN = ""                      # optionnel, ex : "linkedin.com/in/ismael-xxx"
TYPES_CONTRAT = "CDI, CDD, intérim ou stage"  # apparaît dans le mail
DISPONIBILITE = "dès que possible" # apparaît dans le mail

# Ton CV en PDF, posé dans ce dossier
FICHIER_CV = "cv.pdf"
# Le nom que verra le recruteur pour la pièce jointe
NOM_PIECE_JOINTE = "CV.pdf"

# ---------- Zone de recherche ----------
# Ton point de départ. Pour avoir tes coordonnées exactes :
# Google Maps -> clic droit sur chez toi -> clique sur les deux nombres pour les copier.
LATITUDE = 45.6975     # par défaut : centre de Vénissieux
LONGITUDE = 4.8867
RAYON_KM = 15

# Codes NAF (activité officielle de l'entreprise) qui collent à un profil
# technicien informatique et réseau. Mets un # devant une ligne pour l'ignorer.
CODES_NAF = {
    "62.01Z": "du développement informatique",
    "62.02A": "du conseil informatique",
    "62.02B": "de la maintenance informatique",
    "62.03Z": "de l'infogérance",
    "62.09Z": "des services informatiques",
    "63.11Z": "de l'hébergement et du traitement de données",
    "61.10Z": "des télécoms",
    "61.90Z": "des télécoms",
    "95.11Z": "de la réparation informatique",
    "46.51Z": "de la distribution informatique",
    "47.41Z": "de la vente de matériel informatique",
    # Hôpitaux et cliniques (ils ont tous un service informatique)
    "86.10Z": "de la santé",
}

# Taille minimale de l'entreprise (code INSEE) :
# "01" = 1-2 salariés, "02" = 3-5, "03" = 6-9, "11" = 10-19, "12" = 20-49
# Les toutes petites structures prennent rarement des stagiaires.
EFFECTIF_MINIMUM = "02"
ACCEPTER_EFFECTIF_INCONNU = False          # effectif non déclaré
ACCEPTER_ENTREPRENEURS_INDIVIDUELS = False # freelances / auto-entrepreneurs

# Entreprises à ne jamais contacter (un bout du nom suffit, majuscules ou pas)
EXCLURE = [
    "LDLC",
]

# ---------- Envoi ----------
ENVOIS_PAR_JOUR = 20
# Pause aléatoire entre deux mails (en secondes) : évite d'avoir l'air d'un robot
DELAI_MIN_SECONDES = 120
DELAI_MAX_SECONDES = 360

# Serveur d'envoi (Gmail par défaut). Port 465 = SSL, 587 = STARTTLS.
SMTP_SERVEUR = "smtp.gmail.com"
SMTP_PORT = 465

# ---------- Planification (quand l'agent tourne dans Docker / via l'API) ----------
PLANIFICATION_ACTIVE = True
HEURE_LANCEMENT = "09:10"          # heure de Paris
JOURS_LANCEMENT = [0, 1, 2, 3, 4]  # 0 = lundi … 6 = dimanche

# ---------- Recherche des adresses mail ----------
# Nombre max d'entreprises dont on cherche le site/mail à chaque lancement
MAX_ENRICHISSEMENTS = 80
# On ré-interroge l'annuaire (nouvelles entreprises) tous les X jours
JOURS_ENTRE_RECHERCHES = 7

# ---------- Infos personnelles (remplacent les valeurs ci-dessus) ----------
try:
    from config_perso import *  # noqa: F401,F403
except ImportError:
    pass
