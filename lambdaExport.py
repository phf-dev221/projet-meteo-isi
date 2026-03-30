# ============================================================
# LAMBDA-EXPORT : Génération du rapport CSV hebdomadaire
# Déclenchée chaque dimanche à 23h par EventBridge
# Lit toutes les données de DynamoDB
# Génère un fichier CSV et le sauvegarde dans S3/reports/
# ============================================================

# Bibliothèques nécessaires
import json                  # Pour sérialiser le corps de la réponse
import boto3                 # SDK AWS pour accéder à S3 et DynamoDB
import csv                   # Pour générer des fichiers au format CSV
import os                    # Pour lire les variables d'environnement
import io                    # Pour créer un fichier CSV en mémoire (sans disque)
from datetime import datetime # Pour horodater le nom du fichier CSV généré


def lambda_handler(event, context):
    """
    Point d'entrée de la fonction Lambda.
    Déclenchée par EventBridge chaque dimanche à 23h.

    Paramètres :
    - event   : données envoyées par EventBridge (non utilisées ici)
    - context : informations sur l'exécution Lambda
    """

    # --------------------------------------------------------
    # VARIABLES D'ENVIRONNEMENT
    # Configurées dans Lambda → Configuration → Variables d'environnement
    # --------------------------------------------------------
    BUCKET = os.environ['BUCKET_NAME']     # Nom du bucket S3 (meteo-pipeline-pa)
    TABLE  = os.environ['DYNAMODB_TABLE']  # Nom de la table DynamoDB (WeatherStats)

    # --------------------------------------------------------
    # INITIALISATION DES CLIENTS AWS
    # --------------------------------------------------------
    s3       = boto3.client('s3')          # Client S3 pour uploader le fichier CSV
    dynamodb = boto3.resource('dynamodb')  # Ressource DynamoDB (niveau plus haut)
    table    = dynamodb.Table(TABLE)       # Référence directe à la table WeatherStats

    # --------------------------------------------------------
    # ÉTAPE 1 : Lire TOUS les enregistrements de DynamoDB
    #
    # table.scan() : parcourt TOUTE la table sans filtre
    # Retourne un dict avec 'Items' = liste de tous les enregistrements
    # Adapté ici car on veut exporter TOUTES les données de la semaine
    # --------------------------------------------------------
    response = table.scan()
    items    = response['Items']  # Liste de tous les enregistrements trouvés

    # --------------------------------------------------------
    # ÉTAPE 2 : Vérification — table vide ?
    #
    # Si DynamoDB ne contient aucune donnée, on retourne
    # immédiatement sans générer de fichier CSV vide
    # --------------------------------------------------------
    if not items:
        return {
            "statusCode": 200,
            "body": "Aucune donnee dans DynamoDB"
        }

    # --------------------------------------------------------
    # ÉTAPE 3 : Créer le fichier CSV EN MÉMOIRE
    #
    # io.StringIO() : crée un "faux fichier" texte en mémoire RAM
    # Avantage : pas besoin d'écrire sur disque (/tmp limité à 512 Mo)
    #            plus rapide, plus propre pour Lambda
    #
    # csv.writer(output) : crée un writer CSV qui écrira dans output
    # --------------------------------------------------------
    output = io.StringIO()       # Buffer texte en mémoire (comme un fichier virtuel)
    writer = csv.writer(output)  # Objet qui formate et écrit les lignes CSV

    # --------------------------------------------------------
    # ÉTAPE 4 : Écrire la ligne d'en-tête du CSV
    #
    # writer.writerow() : écrit une ligne dans le CSV
    # La première ligne contient les noms des colonnes
    # Ces noms correspondent exactement aux attributs DynamoDB
    # --------------------------------------------------------
    writer.writerow([
        "pk",           # Clé composite : ville#date (ex: Dakar#2026-03-27)
        "city",         # Nom de la ville (ex: Dakar)
        "timestamp",    # Horodatage complet ISO 8601
        "temp",         # Température actuelle en Celsius
        "temp_min",     # Température minimale
        "temp_max",     # Température maximale
        "humidity",     # Humidité en pourcentage
        "description"   # Description météo (ex: few clouds)
    ])

    # --------------------------------------------------------
    # ÉTAPE 5 : Écrire les données — une ligne par enregistrement
    #
    # On parcourt chaque enregistrement de DynamoDB
    # item.get("champ", "") : lit la valeur du champ
    #   - Si le champ existe → retourne sa valeur
    #   - Si le champ est absent → retourne "" (valeur par défaut)
    #     Evite une erreur KeyError si un champ manque
    # --------------------------------------------------------
    for item in items:
        writer.writerow([
            item.get("pk", ""),           # Ex: "Dakar#2026-03-27"
            item.get("city", ""),         # Ex: "Dakar"
            item.get("timestamp", ""),    # Ex: "2026-03-27T09:00:00"
            item.get("temp", ""),         # Ex: "20.7"
            item.get("temp_min", ""),     # Ex: "20.07"
            item.get("temp_max", ""),     # Ex: "20.7"
            item.get("humidity", ""),     # Ex: "84"
            item.get("description", "")  # Ex: "few clouds"
        ])

    # --------------------------------------------------------
    # ÉTAPE 6 : Construire le nom du fichier CSV avec horodatage
    #
    # datetime.utcnow() : heure actuelle en UTC
    # strftime('%Y%m%d_%H%M%S') : formate la date
    #   %Y → 2026    (année sur 4 chiffres)
    #   %m → 03      (mois sur 2 chiffres)
    #   %d → 27      (jour sur 2 chiffres)
    #   %H → 23      (heure sur 2 chiffres)
    #   %M → 00      (minutes sur 2 chiffres)
    #   %S → 00      (secondes sur 2 chiffres)
    #
    # Résultat : "reports/rapport_20260327_230000.csv"
    # --------------------------------------------------------
    now      = datetime.utcnow()
    filename = (
        "reports/rapport_" +
        now.strftime('%Y%m%d_%H%M%S') +  # Ex: "20260327_230000"
        ".csv"
    )

    # --------------------------------------------------------
    # ÉTAPE 7 : Uploader le fichier CSV dans S3/reports/
    #
    # output.getvalue() : récupère tout le contenu du buffer
    #                     mémoire sous forme de texte
    #                     C'est le contenu complet du fichier CSV
    #
    # Bucket      : bucket cible (variable d'environnement)
    # Key         : chemin du fichier dans S3
    # Body        : contenu du fichier CSV (texte)
    # ContentType : "text/csv" indique à S3 que c'est un CSV
    #               (permet l'ouverture directe dans Excel)
    # --------------------------------------------------------
    s3.put_object(
        Bucket      = BUCKET,
        Key         = filename,
        Body        = output.getvalue(),  # Contenu complet du CSV en mémoire
        ContentType = "text/csv"
    )

    # --------------------------------------------------------
    # RETOUR DE LA FONCTION
    # statusCode 200  : HTTP OK — export réussi
    # body            : message de confirmation avec :
    #   - le chemin du fichier créé dans S3
    #   - le nombre de lignes exportées
    # Exemple : "Export OK -> reports/rapport_20260327_230000.csv (37 lignes)"
    # --------------------------------------------------------
    return {
        "statusCode": 200,
        "body": (
            "Export OK -> " +
            filename +
            " (" + str(len(items)) + " lignes)"
        )
    }
