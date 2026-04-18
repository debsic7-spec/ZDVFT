[app]

# Nom de l'application
title = StockAnalyzer IA PEA
package.name = stockanalyzer
package.domain = org.stockanalyzer

# Code source
source.dir = src
source.include_exts = py,png,jpg,kv,atlas,json

# Version
version = 3.0.0

# Dépendances Python
requirements = python3,kivy==2.3.0,kivymd==1.2.0,pillow,requests,certifi,charset-normalizer,idna,urllib3,numpy,pandas,matplotlib,yfinance,plyer,android,pyjnius,multitasking,frozendict,lxml,html5lib,beautifulsoup4,appdirs,platformdirs,pytz,six,python-dateutil,setuptools

# Permissions Android
android.permissions = INTERNET,ACCESS_NETWORK_STATE,POST_NOTIFICATIONS,RECEIVE_BOOT_COMPLETED,FOREGROUND_SERVICE,WAKE_LOCK

# API Android - Poco F7 = Android 15 (API 35)
android.api = 35
android.minapi = 28
android.ndk = 25b
android.sdk = 35

# Architecture - Poco F7 = Dimensity 8400 Ultra (arm64 uniquement)
android.archs = arm64-v8a

# Orientation
orientation = portrait

# Plein écran
fullscreen = 0

# Service en arrière-plan pour la surveillance continue
services = StockMonitor:service.py:foreground

# Icône et splash (decommenter quand les fichiers sont prets)
# icon.filename = %(source.dir)s/data/icon.png
# presplash.filename = %(source.dir)s/data/presplash.png

# Exclure les fichiers inutiles de l'APK
source.exclude_exts = spec,md
source.exclude_dirs = __pycache__,bin,.buildozer

# Couleur de fond du presplash
android.presplash_color = #1a1a2e

# Accepter le SDK
android.accept_sdk_license = True

# Mode de compilation
android.release_artifact = apk

# Logs
log_level = 2

[buildozer]
log_level = 2
warn_on_root = 1
