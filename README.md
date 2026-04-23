# 📈 PEA Tracker IA

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E.svg?logo=javascript&logoColor=black)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF.svg?logo=github-actions&logoColor=white)

Une application web moderne (Progressive Web App) conçue pour le suivi boursier et l'analyse technique automatisée d'actifs éligibles au PEA (Plan d'Épargne en Actions). 

Ce projet intègre un puissant moteur d'analyse Python qui s'appuie sur `yfinance` et la bibliothèque `ta` (Technical Analysis) pour générer des **signaux IA** (Acheter, Vendre, Garder) basés sur de multiples facteurs heuristiques.

---

## ✨ Fonctionnalités Principales

- 📊 **Graphiques Boursiers Avancés** : Affichage en chandeliers, lignes ou aires. Superposition d'indicateurs techniques (VWAP, SMA 20/50, Bandes de Bollinger, Volume).
- 🤖 **Signaux IA & Backtesting** : Évaluation en temps réel de la force de l'actif (RSI, MACD, volatilité ATR) avec un score de confiance et affichage des signaux historiques sur le graphique.
- 🔮 **Comité de Tendance (Prédiction 1h)** : Simulation algorithmique (Mouvement Brownien Géométrique couplé à l'état du RSI) pour projeter le prix sur l'heure suivante.
- 🎯 **Screener & Chasseur d'Opportunités** : Scan automatique régulier des marchés pour déceler les anomalies (RSI survendu, couteaux qui tombent, retournements de tendance MACD).
- 🔔 **Alertes & Notifications Push Web** : Définition d'alertes de prix personnalisées et notifications envoyées nativement sur le navigateur (PC/Mobile) lors de la détection de signaux IA forts.
- 💼 **Gestion de Portefeuille** : Suivi des positions en cours et calcul du P&L (Profits & Pertes) en direct.
- 📱 **Mobile-First & PWA** : Installable comme une application native sur Android/iOS. Intègre un mode "Offline/Démo" qui génère des données factices si l'API est injoignable.

---

## 🛠️ Stack Technique

### Backend
- **Python / FastAPI** : API asynchrone haute performance.
- **Pandas & Numpy** : Manipulation et traitement des séries temporelles financières.
- **yfinance** : Récupération des données de marché en temps réel (Yahoo Finance).
- **ta (Technical Analysis)** : Calcul des RSI, MACD, ATR, et Bandes de Bollinger.
- **Pytest & Ruff** : Tests unitaires avec simulation (mocking) de l'API externe et formatage du code.

### Frontend
- **HTML5 / CSS3 (Vanilla)** : Interface utilisateur "Glassmorphism", thème sombre optimisé pour la lisibilité.
- **JavaScript ES6+** : Gestion asynchrone de l'état, architecture sans framework lourd.
- **Chart.js** : Rendu des graphiques dynamiques et financiers (via `chartjs-chart-financial`).

---

## 🚀 Installation & Exécution locale

### Prérequis
- Python 3.10 ou supérieur
- Git

### 1. Cloner le dépôt
```bash
git clone https://github.com/votre-nom/pea-tracker-ia.git
cd pea-tracker-ia
```

### 2. Installer les dépendances
Il est recommandé d'utiliser un environnement virtuel :
```bash
python -m venv venv
# Sur Windows :
venv\Scripts\activate
# Sur Mac/Linux :
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Lancer le serveur de développement
```bash
python backend/server.py
```
L'application sera accessible sur : **http://localhost:8000**

---

## 🧪 Tests & Qualité du code

Le projet inclut une suite de tests unitaires (via `pytest`) testant les endpoints et le pipeline de données sans dépendre du réseau.

```bash
# Exécuter les tests et afficher la couverture de code
PYTHONPATH=. pytest tests/ -v --cov=backend
```

---

## ⚙️ Déploiement CI/CD

Le pipeline **GitHub Actions** (`.github/workflows/deploy.yml`) est configuré pour se déclencher à chaque `push` sur la branche `main`.
Il exécute l'analyseur de code `Ruff`, lance la suite de tests unitaires `Pytest`, et s'ils réussissent, déclenche le déploiement continu via un Webhook sur **Render.com**.

---

*⚠️ **Disclaimer** : Ce projet est développé à des fins éducatives et expérimentales. Les signaux d'achat ou de vente générés par l'algorithme ne constituent en aucun cas des conseils d'investissement financiers. Le marché boursier comporte des risques de perte en capital.*