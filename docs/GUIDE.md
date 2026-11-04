# Guide d'installation et d'utilisation

Il trouve les entreprises informatiques à moins de 15 km de chez toi, cherche leur adresse mail, puis leur envoie ta candidature (CDI, CDD, intérim ou stage) (20 par jour, chacune personnalisée avec le nom de l'entreprise, sa ville et son activité), avec ton CV en pièce jointe.

| Fichier | Rôle |
|---|---|
| `config.py` | Tes infos, la zone, le nombre d'envois par jour |
| `modele_mail.txt` | Le texte du mail (plusieurs variantes) |
| `collect.py` | Étape 1 : trouve les entreprises et leurs mails |
| `send.py` | Étape 2 : envoie les candidatures |
| `entreprises.csv` | Créé automatiquement : la liste et le suivi (s'ouvre dans Excel) |

---

## 1. Installation (une seule fois)

1. Dézippe le dossier, par exemple dans `Documents\candidatures`.
2. Ouvre le dossier dans VS Code, puis un terminal (`Ctrl + ù`) et tape :
   ```
   pip install -r requirements.txt
   ```
3. Mets ton CV en PDF dans le dossier, sous le nom `cv.pdf`.
4. Ouvre `config.py` et remplis : ton nom, ton téléphone, les types de contrat, et tes coordonnées (Google Maps → clic droit sur chez toi → clique sur les deux nombres pour les copier).
5. Relis `modele_mail.txt` et ajuste le texte si besoin.

## 2. Mot de passe d'application Gmail

Gmail refuse ton vrai mot de passe pour un script : il faut un « mot de passe d'application ».

1. Active la validation en 2 étapes sur ton compte Google (si ce n'est pas déjà fait).
2. Va sur https://myaccount.google.com/apppasswords, donne un nom (ex : « Candidatures ») et copie le code de 16 lettres.
3. Copie le fichier `.env.example`, renomme la copie en `.env` et remplis-la :
   ```
   GMAIL_ADRESSE=ton.adresse@gmail.com
   GMAIL_MOT_DE_PASSE_APP=abcd efgh ijkl mnop
   ```

## 3. Premier lancement (à faire toi-même pour vérifier)

```
python collect.py
```
La première fois, ça prend quelques minutes. Ouvre ensuite `entreprises.csv` dans Excel pour voir ce qui a été trouvé (et ferme-le avant de relancer un script).

```
python send.py --apercu
```
Affiche les 20 mails du jour **sans rien envoyer**. Vérifie que tout est correct.

```
python send.py --test
```
T'envoie **un seul** mail d'exemple, à toi-même, avec le CV. Regarde-le dans ta boîte Gmail.

Quand tout te va : `python send.py` envoie pour de vrai. Il fait une pause de 2 à 6 minutes entre chaque mail, donc les 20 envois prennent environ 1h20.

## 4. Automatiser (tu n'as plus rien à faire)

### Planificateur de tâches Windows (PC allumé le matin)

1. Ouvre le « Planificateur de tâches » → *Créer une tâche de base*.
2. Déclencheur : *Quotidien*, 9h00 (tu peux décocher samedi et dimanche dans les propriétés après).
3. Action : *Démarrer un programme* → choisis `lancer.bat` dans le dossier.
4. Dans les propriétés, coche « Exécuter même si l'utilisateur n'est pas connecté ».

## 5. Le fichier de suivi `entreprises.csv`

Colonne `statut` :

| Statut | Signification |
|---|---|
| `a_enrichir` | Trouvée, mail pas encore cherché |
| `pret` | Mail trouvé, sera contactée dans les prochains jours |
| `envoye` | Candidature envoyée (date dans `date_envoi`) |
| `sans_email` / `sans_site` | Rien trouvé automatiquement |
| `doublon` | Même adresse qu'une entreprise déjà contactée |
| `erreur` | Adresse refusée |
| `exclu` | À mettre toi-même pour ne jamais contacter une entreprise |

Astuce : pour une entreprise `sans_email`, si tu trouves son mail à la main, colle-le dans la colonne `email` et mets `pret` dans `statut`.

## 6. Bonnes pratiques

- **Regarde ta boîte mail chaque jour** : l'agent envoie, mais c'est toi qui réponds aux entreprises.
- Si quelqu'un répond « STOP » ou n'est pas intéressé, rien à faire : chaque entreprise n'est contactée qu'une seule fois.
- Les mails revenus en erreur (« Delivery Status Notification ») : mets `erreur` dans le statut de l'entreprise concernée.
- Pour trouver plus de mails, tu peux ajouter une clé Google Places dans `.env` (`GOOGLE_PLACES_KEY=`) : le script trouvera plus de sites web.
- Pour élargir ou réduire la cible : `RAYON_KM`, `CODES_NAF` et `EFFECTIF_MINIMUM` dans `config.py`.
