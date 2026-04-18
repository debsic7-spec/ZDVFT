# StockAnalyzer IA - Application Android d'analyse boursière

Application Android qui analyse les actions en temps réel avec une IA basée sur l'analyse technique. 
Elle envoie des **notifications push** quand elle détecte une opportunité d'**achat** ou de **vente**.

## Fonctionnalités

- **Analyse IA multi-indicateurs** : RSI, MACD, Moyennes Mobiles (20/50/200), Bandes de Bollinger, Volume, Tendance
- **Support ISIN français** : Entrez directement un code ISIN (ex: `FR0013341781`) ou un ticker Yahoo Finance (ex: `LR.PA`)
- **Score global** : De -100 (VENTE FORTE) à +100 (ACHAT FORT) avec niveau de confiance
- **Surveillance continue** : Monitoring en arrière-plan toutes les 5 minutes
- **Notifications push** : Alerte instantanée quand le signal change (montée = achat, descente = vente)
- **Watchlist** : Suivez plusieurs actions simultanément
- **Service Android** : Continue de surveiller même quand l'app est fermée

## Structure du projet

```
StockAnalyzer/
├── main.py              # Application Kivy/KivyMD (interface Android)
├── analyzer.py          # Moteur d'analyse IA (indicateurs techniques)
├── data_fetcher.py      # Récupération données boursières (Yahoo Finance)
├── monitor.py           # Surveillance continue + déclenchement notifications
├── service.py           # Service Android arrière-plan
├── buildozer.spec       # Configuration build APK Android
├── requirements.txt     # Dépendances Python
└── README.md            # Ce fichier
```

## Installation et test sur PC

### 1. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 2. Lancer l'application (mode PC)
```bash
python main.py
```

L'app s'ouvre dans une fenêtre 400x750 simulant un écran de téléphone.

### 3. Tester l'analyse
Entrez un code dans le champ de recherche :
- ISIN français : `FR0013341781` (Legrand)
- Ticker Euronext : `FP.PA` (TotalEnergies), `MC.PA` (LVMH), `SAN.PA` (Sanofi)

## Compilation APK Android

### Prérequis
- Linux ou WSL (Windows Subsystem for Linux)
- Python 3.10+
- Buildozer installé

### Installation de Buildozer (sur Linux/WSL)
```bash
pip install buildozer
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config \
    zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
```

### Compiler l'APK
```bash
cd StockAnalyzer
buildozer android debug
```

L'APK sera dans `bin/stockanalyzer-1.0.0-arm64-v8a-debug.apk`.

### Installer sur téléphone
```bash
buildozer android deploy
# OU copier l'APK manuellement et l'installer
```

## Indicateurs IA utilisés

| Indicateur | Poids | Description |
|-----------|-------|-------------|
| **MACD** | 25% | Détecte les croisements de tendance (haussier/baissier) |
| **RSI** | 20% | Identifie les zones de surachat (>70) et survente (<30) |
| **Moyennes Mobiles** | 20% | Compare prix aux MM20, MM50, MM200 (Golden/Death Cross) |
| **Bollinger** | 15% | Position du prix dans les bandes de volatilité |
| **Tendance** | 15% | Régression linéaire sur les 10 derniers jours |
| **Volume** | 5% | Compare le volume actuel à la moyenne 20 jours |

## Signaux

| Signal | Score | Action recommandée |
|--------|-------|--------------------|
| **ACHAT FORT** | > +40 | Opportunité d'achat claire |
| **ACHAT** | +15 à +40 | Tendance favorable à l'achat |
| **NEUTRE** | -15 à +15 | Attendre une confirmation |
| **VENTE** | -40 à -15 | Tendance défavorable, envisager la vente |
| **VENTE FORTE** | < -40 | Signal de vente urgent |

## Notes importantes

- Les données proviennent de **Yahoo Finance** (gratuites, 15 min de délai possible)
- L'analyse technique ne garantit **aucun résultat** - c'est un outil d'aide à la décision
- La surveillance consomme des données mobiles (~100Ko par vérification par action)
- Intervalle de vérification : 5 minutes (configurable dans le code)
- Cooldown notifications : 30 minutes par action (évite le spam)
