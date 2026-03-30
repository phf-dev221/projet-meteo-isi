# ============================================================
# LAMBDA-COLLECTE : Collecte des données météo via OpenWeatherMap
# Déclenchée par EventBridge toutes les 3 heures
# Sauvegarde les données JSON brutes dans S3/raw/
# ============================================================

# Bibliothèques Python nécessaires
import json                      # Pour lire/écrire des données JSON
import boto3                     # SDK AWS pour Python (accès à S3, DynamoDB...)
import urllib.request            # Pour faire des appels HTTP vers l'API météo
import os                        # Pour lire les variables d'environnement Lambda
from datetime import datetime    # Pour horodater les fichiers collectés


def lambda_handler(event, context):
    """
    Point d'entrée de la fonction Lambda.
    AWS appelle cette fonction automatiquement à chaque déclenchement.
    
    Paramètres :
    - event   : données envoyées par le déclencheur (EventBridge ici)
    - context : informations sur l'exécution Lambda (timeout, mémoire...)
    """

    # --------------------------------------------------------
    # VARIABLES D'ENVIRONNEMENT
    # Configurées dans Lambda → Configuration → Variables d'environnement
    # Jamais dans le code pour éviter les fuites de credentials
    # --------------------------------------------------------
    API_KEY = os.environ['OPENWEATHER_API_KEY']  # Clé secrète OpenWeatherMap
    BUCKET  = os.environ['BUCKET_NAME']           # Nom du bucket S3 cible

    # --------------------------------------------------------
    # LISTE DES 6 VILLES À COLLECTER
    # Couvre 4 pays d'Afrique de l'Ouest
    # --------------------------------------------------------
    VILLES = [
        "Dakar",        # Sénégal — Capitale
        "Thies",        # Sénégal — 2ème ville
        "Saint-Louis",  # Sénégal — Nord du pays
        "Bamako",       # Mali — Capitale
        "Abidjan",      # Côte d'Ivoire — Capitale économique
        "Ouagadougou"   # Burkina Faso — Capitale
    ]

    # --------------------------------------------------------
    # INITIALISATION
    # --------------------------------------------------------
    s3 = boto3.client('s3')   # Crée un client S3 pour uploader les fichiers
    resultats = []             # Liste qui stockera les résultats de chaque ville
    now = datetime.utcnow()   # Heure actuelle en UTC (même fuseau que AWS)
                               # Défini UNE FOIS avant la boucle pour que tous
                               # les fichiers aient exactement le même timestamp

    # --------------------------------------------------------
    # BOUCLE PRINCIPALE : traite chaque ville une par une
    # --------------------------------------------------------
    for ville in VILLES:
        try:
            # ----------------------------------------------------
            # ÉTAPE 1 : Construction de l'URL de l'API météo
            # ?q=     : nom de la ville à rechercher
            # &appid= : clé d'authentification API
            # &units=metric : température en Celsius (pas Fahrenheit)
            # ----------------------------------------------------
            url = (
                "http://api.openweathermap.org/data/2.5/weather"
                "?q=" + ville +
                "&appid=" + API_KEY +
                "&units=metric"
            )

            # ----------------------------------------------------
            # ÉTAPE 2 : Appel HTTP vers OpenWeatherMap
            # urllib.request.urlopen() : ouvre la connexion HTTP
            # response.read()          : lit la réponse brute (bytes)
            # .decode("utf-8")         : convertit en texte lisible
            # json.loads()             : convertit le texte JSON en dict Python
            # ----------------------------------------------------
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode("utf-8"))

            # ----------------------------------------------------
            # ÉTAPE 3 : Extraction des données utiles
            # On ne garde que les champs nécessaires de la réponse API
            # data["main"]       : bloc des données météo principales
            # data["weather"][0] : premier élément de la liste météo
            # ----------------------------------------------------
            meteo = {
                "city"        : ville,              # Nom de la ville
                "timestamp"   : now.isoformat(),    # Ex: "2026-03-27T09:00:00"
                "temp"        : data["main"]["temp"],       # Température actuelle
                "temp_min"    : data["main"]["temp_min"],   # Température minimale
                "temp_max"    : data["main"]["temp_max"],   # Température maximale
                "humidity"    : data["main"]["humidity"],   # Humidité en %
                "description" : data["weather"][0]["description"]  # Ex: "few clouds"
            }

            # ----------------------------------------------------
            # ÉTAPE 4 : Construction du chemin S3
            # Format : raw/YYYY/MM/DD/ville/ville_HHMMSS.json
            # Exemple: raw/2026/03/27/dakar/dakar_090000.json
            #
            # ville.lower()          : "Dakar" → "dakar"
            # .replace(" ", "-")     : "Saint-Louis" → "saint-louis"
            # now.strftime('%Y')     : "2026"
            # now.strftime('%m')     : "03"  (mois avec zéro)
            # now.strftime('%d')     : "27"  (jour avec zéro)
            # now.strftime('%H%M%S') : "090000" (heure, minute, seconde)
            # ----------------------------------------------------
            ville_fichier = ville.lower().replace(" ", "-")
            filename = (
                "raw/" +
                now.strftime('%Y') + "/" +   # Année
                now.strftime('%m') + "/" +   # Mois
                now.strftime('%d') + "/" +   # Jour
                ville_fichier + "/" +        # Nom ville (normalisé)
                ville_fichier + "_" +        # Début du nom de fichier
                now.strftime('%H%M%S') +     # Heure de collecte
                ".json"                      # Extension fichier
            )

            # ----------------------------------------------------
            # ÉTAPE 5 : Upload du fichier JSON dans S3
            # Bucket       : nom du bucket cible (variable d'env)
            # Key          : chemin complet du fichier dans S3
            # Body         : contenu du fichier (JSON sérialisé)
            # ContentType  : indique à S3 que c'est un fichier JSON
            # ----------------------------------------------------
            s3.put_object(
                Bucket      = BUCKET,
                Key         = filename,
                Body        = json.dumps(meteo),     # Convertit le dict Python en JSON texte
                ContentType = "application/json"
            )

            # Ajoute un message de succès dans la liste des résultats
            resultats.append(ville + " OK --> " + filename)

        except Exception as e:
            # ----------------------------------------------------
            # GESTION DES ERREURS
            # Si une ville échoue (ex: API indisponible, ville non trouvée),
            # on continue avec les autres villes plutôt que d'arrêter tout
            # str(e) : convertit l'exception en message lisible
            # ----------------------------------------------------
            resultats.append(ville + " erreur: " + str(e))

    # --------------------------------------------------------
    # RETOUR DE LA FONCTION
    # statusCode 200 : HTTP OK — la fonction s'est exécutée
    # body          : liste JSON des résultats pour chaque ville
    # Visible dans CloudWatch Logs et les tests Lambda
    # --------------------------------------------------------
    return {
        "statusCode": 200,
        "body": json.dumps(resultats)
    }
