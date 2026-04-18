"""
service.py - Service Android en arrière-plan
Permet à la surveillance de continuer même quand l'app est fermée.
Ce fichier est utilisé par Buildozer comme service Android.
"""

import os
import time
import json
from datetime import datetime

# Configuration du path pour Android
try:
    from android.storage import app_storage_path  # type: ignore
    os.chdir(app_storage_path())
except ImportError:
    pass

from monitor import MarketMonitor


def start_foreground_service():
    """Demarre un foreground service Android avec notification persistante."""
    try:
        from jnius import autoclass  # type: ignore
        PythonService = autoclass('org.kivy.android.PythonService')
        service = PythonService.mService
        Context = autoclass('android.content.Context')
        NotificationBuilder = autoclass('android.app.Notification$Builder')
        NotificationChannel = autoclass('android.app.NotificationChannel')
        NotificationManager = autoclass('android.app.NotificationManager')

        CHANNEL_ID = "stockanalyzer_monitor"
        nm = service.getSystemService(Context.NOTIFICATION_SERVICE)
        channel = NotificationChannel(
            CHANNEL_ID, "Surveillance Bourse", NotificationManager.IMPORTANCE_LOW)
        nm.createNotificationChannel(channel)

        builder = NotificationBuilder(service, CHANNEL_ID)
        builder.setContentTitle("StockAnalyzer IA")
        builder.setContentText("Surveillance du marche en cours...")
        builder.setSmallIcon(service.getApplicationInfo().icon)
        builder.setOngoing(True)

        service.startForeground(1, builder.build())
    except Exception as e:
        print(f"Foreground service error: {e}")


def send_android_notification(title: str, message: str):
    """Envoie une notification Android native."""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="StockAnalyzer",
            timeout=30,
        )
    except Exception as e:
        print(f"Notification error: {e}")


def on_signal(ticker, signal, result):
    """Callback quand un signal est détecté par le moniteur."""
    name = ticker
    
    if signal.value in ("ACHAT FORT", "ACHAT"):
        title = f"📈 Signal ACHAT - {name}"
    elif signal.value in ("VENTE FORTE", "VENTE"):
        title = f"📉 Signal VENTE - {name}"
    else:
        title = f"⚖️ {name} - Signal Neutre"
    
    message = (
        f"{result.signal.value} | Score: {result.score:+.1f}\n"
        f"Prix: {result.price:.2f}€ | RSI: {result.rsi:.0f}"
    )
    
    send_android_notification(title, message)
    
    # Logger
    log_entry = {
        "time": datetime.now().isoformat(),
        "ticker": ticker,
        "signal": signal.value,
        "score": result.score,
        "price": result.price,
    }
    
    log_file = "signal_log.json"
    try:
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        
        logs.append(log_entry)
        # Garder les 500 derniers
        logs = logs[-500:]
        
        with open(log_file, 'w') as f:
            json.dump(logs, f)
    except Exception:
        pass


def main():
    """Point d'entrée du service Android."""
    print("StockAnalyzer Service démarré")

    # Foreground service requis par Android 8+
    start_foreground_service()

    monitor = MarketMonitor(
        on_signal=on_signal,
        check_interval=300,  # 5 minutes
    )
    
    # Utiliser l'API publique start() qui lance le thread interne
    monitor.start()

    # Garder le service en vie
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        monitor.stop()


if __name__ == "__main__":
    main()
