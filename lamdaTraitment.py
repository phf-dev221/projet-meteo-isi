 # ============================================================
# LAMBDA-TRAITEMENT : Traitement des données météo brutes
# Déclenchée automatiquement par un trigger S3
# dès qu'un fichier JSON arrive dans S3/raw/
# Sauvegarde dans DynamoDB + S3/processed/
# ============================================================

# Bibliothèques nécessaires
import json                          # Pour lire/écrire des données JSON
import boto3                         # SDK AWS pour accéder à S3 et DynamoDB
import os                            # Pour lire les variables d'environnement
from urllib.parse import unquote_plus # Pour décoder les caractères spéciaux
                                      # dans les chemins S3
                                      # Ex: "saint%2Dlouis" → "saint-louis"


def lambda_handler(event, context):
    """
    Point d'entrée de la fonction Lambda.
    Déclenchée par un événement S3 (nouveau fichier dans raw/)
    
    Paramètres :
    - event   : contient les infos sur le fichier S3 qui a déclenché la fonction
                structure : event['Records'][i]['s3']['bucket'] et ['object']
    - context : informations sur l'exécution Lambda
    """

    # --------------------------------------------------------
    # VARIABLES D'ENVIRONNEMENT
    # Configurées dans Lambda → Configuration → Variables d'environnement
    # --------------------------------------------------------
    BUCKET = os.environ['BUCKET_NAME']      # Nom du bucket S3 (meteo-pipeline-pa)
    TABLE  = os.environ['DYNAMODB_TABLE']   # Nom de la table DynamoDB (WeatherStats)

    # --------------------------------------------------------
    # INITIALISATION DES CLIENTS AWS
    # --------------------------------------------------------
    s3       = boto3.client('s3')              # Client S3 pour lire/écrire des fichiers
    dynamodb = boto3.resource('dynamodb')      # Ressource DynamoDB (niveau plus haut)
    table    = dynamodb.Table(TABLE)           # Référence directe à la table WeatherStats

    resultats = []   # Liste qui stockera les résultats de chaque fichier traité

    # --------------------------------------------------------
    # BOUCLE PRINCIPALE : un événement S3 peut contenir
    # plusieurs fichiers (Records) — on les traite tous
    # --------------------------------------------------------
    for record in event['Records']:
        try:
            # ----------------------------------------------------
            # ÉTAPE 1 : Récupérer les infos du fichier déclenché
            #
            # event['Records'] : liste des fichiers qui ont déclenché Lambda
            # record['s3']['bucket']['name'] : nom du bucket source
            # record['s3']['object']['key']  : chemin du fichier dans S3
            #
            # unquote_plus() : décode les caractères spéciaux de l'URL
            # Exemple : "raw/2026/03/27/saint%2Dlouis/..."
            #        → "raw/2026/03/27/saint-louis/..."
            # ----------------------------------------------------
            bucket = record['s3']['bucket']['name']
            key    = unquote_plus(record['s3']['object']['key'])

            # Affiche dans CloudWatch Logs pour débogage
            print("Bucket: " + bucket)
            print("Key: " + key)

            # ----------------------------------------------------
            # ÉTAPE 2 : Lire le fichier JSON depuis S3
            #
            # s3.get_object()      : télécharge le fichier depuis S3
            # fichier['Body']      : contenu brut du fichier (stream)
            # .read()              : lit tout le contenu en bytes
            # .decode("utf-8")     : convertit les bytes en texte
            # json.loads()         : convertit le texte JSON en dict Python
            # ----------------------------------------------------
            fichier = s3.get_object(Bucket=bucket, Key=key)
            meteo   = json.loads(fichier['Body'].read().decode("utf-8"))

            # ----------------------------------------------------
            # ÉTAPE 3 : Extraire les données du dictionnaire JSON
            #
            # float() : convertit les valeurs en nombre décimal
            # Nécessaire car les valeurs JSON peuvent être des strings
            # timestamp[:10] : prend uniquement la date "2026-03-27"
            #                  depuis "2026-03-27T09:00:00.123456"
            # ----------------------------------------------------
            ville     = meteo['city']             # Ex: "Dakar"
            timestamp = meteo['timestamp']        # Ex: "2026-03-27T09:00:00"
            temp      = float(meteo['temp'])      # Ex: 20.7
            temp_min  = float(meteo['temp_min'])  # Ex: 20.07
            temp_max  = float(meteo['temp_max'])  # Ex: 20.7
            humidity  = float(meteo['humidity'])  # Ex: 84.0

            # ----------------------------------------------------
            # ÉTAPE 4 : Créer la clé primaire DynamoDB (pk)
            #
            # Clé composite = ville + "#" + date
            # Exemples :
            #   "Dakar#2026-03-27"
            #   "Bamako#2026-03-27"
            #
            # timestamp[:10] extrait uniquement "2026-03-27"
            # depuis "2026-03-27T09:00:00.123456"
            # Le "#" sert de séparateur lisible entre ville et date
            # ----------------------------------------------------
            pk = ville + "#" + timestamp[:10]

            # ----------------------------------------------------
            # ÉTAPE 5 : Construire le dictionnaire des données traitées
            #
            # str() : DynamoDB n'accepte pas les float directement
            # On convertit donc les nombres en string pour le stockage
            # Exemple : float(20.7) → str("20.7")
            # ----------------------------------------------------
            processed_data = {
                "pk"          : pk,            # Clé de partition : "Dakar#2026-03-27"
                "timestamp"   : timestamp,     # Horodatage complet ISO 8601
                "city"        : ville,         # Nom de la ville
                "temp"        : str(temp),     # Température actuelle en string
                "temp_min"    : str(temp_min), # Température minimale en string
                "temp_max"    : str(temp_max), # Température maximale en string
                "humidity"    : str(humidity), # Humidité en string
                "description" : meteo["description"]  # Ex: "few clouds"
            }

            # ----------------------------------------------------
            # ÉTAPE 6 : Sauvegarder dans DynamoDB
            #
            # table.put_item() : insère ou remplace un enregistrement
            # Si la clé pk existe déjà → elle est mise à jour
            # Si elle n'existe pas → elle est créée
            # ----------------------------------------------------
            table.put_item(Item=processed_data)

            # ----------------------------------------------------
            # ÉTAPE 7 : Construire le chemin S3/processed/
            #
            # key = "raw/2026/03/27/dakar/dakar_090000.json"
            # key.split("/") → ["raw", "2026", "03", "27", "dakar", "dakar_090000.json"]
            #
            # parts[1]  → "2026"  (année)
            # parts[2]  → "03"    (mois)
            # parts[-1] → "dakar_09
