# Pipeline de Données Météo Automatisé pour l'Agriculture en Afrique de l'Ouest

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org/)
[![AWS](https://img.shields.io/badge/AWS-Services-orange)](https://aws.amazon.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## 📋 Table des matières

- [Contexte & Enjeux](#contexte--enjeux)
- [Architecture](#architecture)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Configuration AWS](#configuration-aws)
- [Fonctions Lambda](#fonctions-lambda)
- [Surveillance & Alertes](#surveillance--alertes)
- [Déploiement](#déploiement)
- [Utilisation](#utilisation)
- [Troubleshooting](#troubleshooting)
- [Contributeurs](#contributeurs)

## 🌍 Contexte & Enjeux

L'agriculture représente entre **15 % et 30 % du PIB** de la majorité des pays d'Afrique de l'Ouest (BCEAO, 2023). Les petits exploitants agricoles au **Sénégal**, au **Mali**, en **Côte d'Ivoire** ou au **Burkina Faso** prennent des décisions cruciales — dates de semis, irrigation, récolte — **sans accès à des données météorologiques fiables et actualisées**.

### 🎯 Objectif

Construire un **pipeline automatisé et serverless** qui :
- ✅ Collecte en continu des données météorologiques en temps réel
- ✅ Stocke les données sur AWS (S3 + DynamoDB)
- ✅ Traite et transforme les données automatiquement
- ✅ Génère des rapports périodiques (CSV hebdomadaires)
- ✅ Fonctionne 24h/24 sans intervention humaine
- ✅ Alerte automatiquement en cas de panne

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│  OpenWeatherMap API (Gratuit)                                   │
│         ↓                                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ EventBridge (Trigger: Toutes les 3 heures - Cron)       │    │
│  └────────────────────┬────────────────────────────────────┘    │
│                       ↓                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Lambda-Collecte (Python 3.11)                            │    │
│  │ - Appel API OpenWeatherMap (6 villes)                   │    │
│  │ - Format: JSON brut avec horodatage                     │    │
│  └────────────────────┬────────────────────────────────────┘    │
│                       ↓                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ S3 Bucket (raw/YYYY/MM/DD/ville/)                       │    │
│  │ - Versioning enabled                                    │    │
│  │ - Lifecycle: Standard → IA (30j) → Glacier (90j)        │    │
│  └────────────────────┬────────────────────────────────────┘    │
│                       ↓                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Lambda-Traitement (Trigger: S3 PUT Event)               │    │
│  │ - Agrégations: min/max/avg temp, humidité, etc.         │    │
│  └────────────────────┬────────────────────────────────────┘    │
│                       ↓                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ DynamoDB Table (PK=ville#date, SK=heure)                │    │
│  │ + S3 Bucket (processed/YYYY/MM/)                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                       ↓                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ EventBridge (Trigger: Chaque dimanche 23h - Cron)       │    │
│  └────────────────────┬────────────────────────────────────┘    │
│                       ↓                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Lambda-Export (Python 3.11)                              │    │
│  │ - Lecture DynamoDB                                      │    │
│  │ - Export CSV hebdomadaire                               │    │
│  └────────────────────┬────────────────────────────────────┘    │
│                       ↓                                           │
│  ��─────────────────────────────────────────────────────────┐    │
│  │ S3 Bucket (reports/YYYY/MM/rapport_semaine_XX.csv)      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                       ↓                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ CloudWatch Alarms                                        │    │
│  │ - Erreurs Lambda > 0                                    │    │
│  │ - Durée Lambda-Collecte > 5000ms                        │    │
│  │ - Taille S3 > 500 MB                                    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 📊 Villes couvertes

- 🇸🇳 **Sénégal** : Dakar, Thiès, Saint-Louis
- 🇲🇱 **Mali** : Bamako
- 🇨🇮 **Côte d'Ivoire** : Abidjan
- 🇧🇫 **Burkina Faso** : Ouagadougou

## 🔧 Prérequis

### Outils locaux
- **Python** 3.11+
- **AWS CLI** v2+
- **SAM CLI** (optionnel, pour déploiement local)
- **pip** (gestionnaire de paquets Python)
- **Git**

### Accès AWS
- Compte AWS avec les permissions IAM suivantes:
  - S3 (CreateBucket, PutObject, GetObject)
  - Lambda (CreateFunction, UpdateFunction)
  - DynamoDB (CreateTable, PutItem, Query)
  - CloudWatch (PutMetricAlarm)
  - EventBridge (PutRule, PutTargets)
  - IAM (CreateRole, AttachRolePolicy)

### API OpenWeatherMap
- Clé API gratuite : https://openweathermap.org/api
- Plan utilisé : **Free tier** (1000 appels/jour)

## 📦 Installation

### 1. Cloner le repository
```bash
git clone https://github.com/phf-dev221/projet-meteo-isi.git
cd projet-meteo-isi
```

### 2. Créer un environnement virtuel Python
```bash
python3.11 -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 4. Configurer les variables d'environnement
```bash
cp .env.example .env
# Éditer .env avec vos paramètres
nano .env
```

**Variables essentielles (.env)** :
```env
AWS_REGION=eu-west-1
AWS_PROFILE=default
OPENWEATHERMAP_API_KEY=votre_clé_api_ici
S3_BUCKET_NAME=meteo-isi-data
DYNAMODB_TABLE_NAME=meteo-isi-processed
CITIES=Dakar,Thiès,Saint-Louis,Bamako,Abidjan,Ouagadougou
COLLECTION_INTERVAL_HOURS=3
ALERT_EMAIL=votre.email@example.com
```

## ☁️ Configuration AWS

### 1. Créer le bucket S3
```bash
aws s3api create-bucket \
  --bucket meteo-isi-data \
  --region eu-west-1 \
  --create-bucket-configuration LocationConstraint=eu-west-1 \
  --profile default
```

### 2. Activer le versioning S3
```bash
aws s3api put-bucket-versioning \
  --bucket meteo-isi-data \
  --versioning-configuration Status=Enabled \
  --profile default
```

### 3. Appliquer la politique Lifecycle S3
```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket meteo-isi-data \
  --lifecycle-configuration file://config/s3-lifecycle.json \
  --profile default
```

**config/s3-lifecycle.json** :
```json
{
  "Rules": [
    {
      "Id": "transition-standard-ia",
      "Status": "Enabled",
      "Prefix": "raw/",
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        }
      ]
    }
  ]
}
```

### 4. Créer la table DynamoDB
```bash
aws dynamodb create-table \
  --table-name meteo-isi-processed \
  --attribute-definitions \
    AttributeName=ville_date,AttributeType=S \
    AttributeName=heure,AttributeType=S \
  --key-schema \
    AttributeName=ville_date,KeyType=HASH \
    AttributeName=heure,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region eu-west-1 \
  --profile default
```

### 5. Créer le rôle IAM pour Lambda
```bash
# Créer la policy d'exécution
aws iam create-role \
  --role-name lambda-meteo-execution-role \
  --assume-role-policy-document file://config/lambda-trust-policy.json \
  --profile default

# Attacher les policies
aws iam attach-role-policy \
  --role-name lambda-meteo-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Custom policy pour S3 et DynamoDB
aws iam put-role-policy \
  --role-name lambda-meteo-execution-role \
  --policy-name lambda-meteo-policy \
  --policy-document file://config/lambda-policy.json \
  --profile default
```

## 🔨 Fonctions Lambda

### Lambda-Collecte

**Emplacement** : `src/lambda_collecte/lambda_function.py`

**Déclencheur** : EventBridge (Cron: `0 */3 * * ? *` = toutes les 3 heures)

**Fonctionnalités** :
- Appelle OpenWeatherMap API pour 6 villes
- Stocke les données JSON brutes dans `S3/raw/YYYY/MM/DD/ville/`
- Incluent horodatage précis (ISO 8601)
- Gestion d'erreurs robuste avec retry automatique

**Exemple de données collectées** :
```json
{
  "timestamp": "2026-03-30T14:00:00Z",
  "city": "Dakar",
  "latitude": 14.6928,
  "longitude": -17.0471,
  "temperature": 28.5,
  "feels_like": 27.8,
  "humidity": 75,
  "pressure": 1013,
  "wind_speed": 12.5,
  "wind_deg": 45,
  "clouds": 20,
  "rain_1h": 0,
  "description": "clear sky"
}
```

**Déploiement** :
```bash
cd src/lambda_collecte
zip -r function.zip lambda_function.py requirements.txt
aws lambda create-function \
  --function-name lambda-meteo-collecte \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-meteo-execution-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 60 \
  --memory-size 256 \
  --environment Variables={OPENWEATHERMAP_API_KEY=votre_clé,S3_BUCKET=meteo-isi-data,CITIES=Dakar,Thiès,Saint-Louis,Bamako,Abidjan,Ouagadougou} \
  --profile default
```

### Lambda-Traitement

**Emplacement** : `src/lambda_traitement/lambda_function.py`

**Déclencheur** : S3 PUT Event (sur `s3://meteo-isi-data/raw/*`)

**Fonctionnalités** :
- Lit les fichiers JSON bruts depuis S3
- Calcule les agrégations :
  - Température min/max/moyenne
  - Humidité moyenne
  - Total précipitations
  - Vitesse du vent moyenne
- Persiste les résultats dans DynamoDB
- Crée également des fichiers CSV dans `processed/YYYY/MM/`

**Schéma DynamoDB** :
```
PK (Partition Key): ville#date (e.g., "Dakar#2026-03-30")
SK (Sort Key): heure (e.g., "14:00:00")

Attributes:
- temperature_min: 24.5
- temperature_max: 31.2
- temperature_avg: 28.1
- humidity_avg: 73
- rain_total: 0
- wind_speed_avg: 12.3
- data_count: 12
- last_update: 2026-03-30T14:00:00Z
```

**Déploiement** :
```bash
cd src/lambda_traitement
zip -r function.zip lambda_function.py requirements.txt
aws lambda create-function \
  --function-name lambda-meteo-traitement \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-meteo-execution-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 120 \
  --memory-size 512 \
  --environment Variables={S3_BUCKET=meteo-isi-data,DYNAMODB_TABLE=meteo-isi-processed} \
  --profile default
```

**Ajouter le déclencheur S3** :
```bash
aws lambda create-event-source-mapping \
  --event-source-arn arn:aws:s3:::meteo-isi-data \
  --function-name lambda-meteo-traitement \
  --event-source Events=s3:ObjectCreated:* \
  --filter-criteria '{
    "Key": {
      "FilterRules": [
        {"Name": "prefix", "Value": "raw/"}
      ]
    }
  }' \
  --profile default
```

### Lambda-Export

**Emplacement** : `src/lambda_export/lambda_function.py`

**Déclencheur** : EventBridge (Cron: `0 23 ? * SUN *` = Chaque dimanche 23h UTC)

**Fonctionnalités** :
- Lit les données depuis DynamoDB (dernière semaine)
- Génère un rapport CSV structuré
- Stocke dans `S3/reports/YYYY/MM/rapport_semaine_XX.csv`
- Notification optionnelle par email (SNS)

**Format du rapport CSV** :
```csv
Ville,Date,Température Min (°C),Température Max (°C),Température Moyenne (°C),Humidité (%),Précipitations (mm),Vitesse Vent Moy (m/s)
Dakar,2026-03-24,24.5,31.2,28.1,73,0,12.3
Dakar,2026-03-25,25.1,30.8,27.9,71,0,11.8
...
```

**Déploiement** :
```bash
cd src/lambda_export
zip -r function.zip lambda_function.py requirements.txt
aws lambda create-function \
  --function-name lambda-meteo-export \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-meteo-execution-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 300 \
  --memory-size 512 \
  --environment Variables={S3_BUCKET=meteo-isi-data,DYNAMODB_TABLE=meteo-isi-processed,SNS_TOPIC_ARN=arn:aws:sns:eu-west-1:ACCOUNT_ID:meteo-isi-alerts} \
  --profile default
```

## 📊 Surveillance & Alertes

### CloudWatch Alarms

#### 1️⃣ Alarme: Erreurs Lambda > 0
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name meteo-lambda-errors \
  --alarm-description "Alert si erreurs Lambda-Collecte > 0" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 0 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=FunctionName,Value=lambda-meteo-collecte \
  --alarm-actions arn:aws:sns:eu-west-1:ACCOUNT_ID:meteo-isi-alerts \
  --profile default
```

#### 2️⃣ Alarme: Durée Lambda-Collecte > 5000ms
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name meteo-lambda-duration \
  --alarm-description "Alert si Lambda-Collecte dépasse 5000ms" \
  --metric-name Duration \
  --namespace AWS/Lambda \
  --statistic Average \
  --period 300 \
  --threshold 5000 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=FunctionName,Value=lambda-meteo-collecte \
  --alarm-actions arn:aws:sns:eu-west-1:ACCOUNT_ID:meteo-isi-alerts \
  --profile default
```

#### 3️⃣ Alarme: Taille S3 > 500 MB
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name meteo-s3-size \
  --alarm-description "Alert si bucket S3 > 500 MB" \
  --metric-name BucketSizeBytes \
  --namespace AWS/S3 \
  --statistic Maximum \
  --period 86400 \
  --threshold 524288000 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=BucketName,Value=meteo-isi-data Name=StorageType,Value=StandardStorage \
  --alarm-actions arn:aws:sns:eu-west-1:ACCOUNT_ID:meteo-isi-alerts \
  --profile default
```

### SNS Topic pour notifications
```bash
aws sns create-topic \
  --name meteo-isi-alerts \
  --region eu-west-1 \
  --profile default

aws sns subscribe \
  --topic-arn arn:aws:sns:eu-west-1:ACCOUNT_ID:meteo-isi-alerts \
  --protocol email \
  --notification-endpoint votre.email@example.com \
  --profile default
```

### Dashboard CloudWatch
```bash
aws cloudwatch put-dashboard \
  --dashboard-name meteo-isi-dashboard \
  --dashboard-body file://config/dashboard.json \
  --profile default
```

## 🚀 Déploiement

### Option 1: Déploiement manuel (rapide)
```bash
# Cloner et configurer
git clone https://github.com/phf-dev221/projet-meteo-isi.git
cd projet-meteo-isi
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configurer
cp .env.example .env
nano .env

# Lancer le script de déploiement
python scripts/deploy.py --region eu-west-1 --profile default
```

### Option 2: Déploiement avec AWS CloudFormation (production)
```bash
aws cloudformation create-stack \
  --stack-name meteo-isi-stack \
  --template-body file://config/cloudformation-template.yaml \
  --parameters ParameterKey=OpenWeatherMapAPIKey,ParameterValue=votre_clé_api \
               ParameterKey=AlertEmail,ParameterValue=votre.email@example.com \
  --capabilities CAPABILITY_IAM \
  --region eu-west-1 \
  --profile default

# Vérifier le statut
aws cloudformation describe-stacks \
  --stack-name meteo-isi-stack \
  --profile default
```

### Option 3: Déploiement avec SAM CLI
```bash
sam build
sam deploy \
  --guided \
  --region eu-west-1 \
  --profile default
```

## 💻 Utilisation

### Tester Lambda-Collecte localement
```bash
python -m pytest tests/test_lambda_collecte.py -v
```

### Déclencher manuellement Lambda-Collecte
```bash
aws lambda invoke \
  --function-name lambda-meteo-collecte \
  --payload '{}' \
  --profile default \
  response.json

cat response.json
```

### Consulter les données dans DynamoDB
```bash
aws dynamodb scan \
  --table-name meteo-isi-processed \
  --filter-expression "begins_with(ville_date, :ville)" \
  --expression-attribute-values '{":ville": {"S": "Dakar"}}' \
  --profile default
```

### Télécharger un rapport CSV depuis S3
```bash
aws s3 cp \
  s3://meteo-isi-data/reports/2026/03/rapport_semaine_13.csv \
  ./rapport_semaine_13.csv \
  --profile default
```

### Afficher les logs CloudWatch
```bash
aws logs tail /aws/lambda/lambda-meteo-collecte --follow --profile default
```

## 🔍 Troubleshooting

### ❌ Problème: "Permission denied" pour Lambda

**Solution** :
```bash
# Vérifier les permissions du rôle IAM
aws iam get-role-policy \
  --role-name lambda-meteo-execution-role \
  --policy-name lambda-meteo-policy \
  --profile default

# Réappliquer la policy
aws iam put-role-policy \
  --role-name lambda-meteo-execution-role \
  --policy-name lambda-meteo-policy \
  --policy-document file://config/lambda-policy.json \
  --profile default
```

### ❌ Problème: "API key invalid" OpenWeatherMap

**Solution** :
```bash
# Vérifier la clé API
echo $OPENWEATHERMAP_API_KEY

# Tester l'API manuellement
curl "https://api.openweathermap.org/data/2.5/weather?q=Dakar&appid=YOUR_API_KEY&units=metric"

# Mettre à jour la clé dans Lambda
aws lambda update-function-configuration \
  --function-name lambda-meteo-collecte \
  --environment Variables={OPENWEATHERMAP_API_KEY=nouvelle_clé} \
  --profile default
```

### ❌ Problème: S3 trigger ne déclenche pas Lambda-Traitement

**Solution** :
```bash
# Vérifier la configuration du déclencheur
aws lambda list-event-source-mappings \
  --function-name lambda-meteo-traitement \
  --profile default

# Supprimer et recréer si nécessaire
aws s3api put-bucket-notification-configuration \
  --bucket meteo-isi-data \
  --notification-configuration file://config/s3-notification.json \
  --profile default
```

### ❌ Problème: DynamoDB table "Throughput exceeded"

**Solution** :
```bash
# Le projet utilise PAY_PER_REQUEST (pas de limite)
# Si vous avez une table existante:
aws dynamodb update-billing-mode \
  --table-name meteo-isi-processed \
  --billing-mode PAY_PER_REQUEST \
  --profile default
```

## 📈 Métriques clés

- **Données collectées** : 6 villes × 8 appels/jour = 48 points/jour
- **Stockage estimé** : ~2 KB/requête × 48 × 365 = **35 MB/an**
- **Coûts AWS estimés** :
  - Lambda: ~$1-2/mois
  - S3: <$1/mois
  - DynamoDB: <$2/mois
  - **Total: ~$5-10/mois**

## 📚 Ressources

- [OpenWeatherMap API Docs](https://openweathermap.org/api)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS S3 Lifecycle Policies](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)
- [AWS DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/BestPractices.html)
- [AWS EventBridge Cron](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-cron-expressions.html)

## 👥 Contributeurs

- **Mainteneur** : Ansata Diamanka - Pape Hamady FALL
- **Projet** : P-01 ISI - Pipeline de Données Météo
- **Année** : 2026

## 📄 Licence

Ce projet est sous licence **MIT**. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

**Dernière mise à jour** : 2026-03-30

Pour toute question ou problème, veuillez ouvrir une [issue](https://github.com/phf-dev221/projet-meteo-isi/issues).
