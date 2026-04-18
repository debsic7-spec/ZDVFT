"""
monitor.py - Service de surveillance continue du marché
Tourne en arrière-plan et envoie des notifications achat/vente.
"""

import threading
import time
import json
import os
from datetime import datetime
from typing import Callable, Optional

from data_fetcher import fetch_stock_data, fetch_realtime_price, get_stock_name
from analyzer import analyze_stock, Signal

# Fichier de persistance pour les actions suivies
WATCHLIST_FILE = "watchlist.json"


class MarketMonitor:
    """
    Moniteur de marché qui surveille en continu les actions
    et envoie des notifications basées sur l'analyse IA.
    """
    
    def __init__(self, on_signal: Optional[Callable] = None, 
                 check_interval: int = 300):
        """
        Args:
            on_signal: Callback appelé quand un signal est détecté
                       fn(ticker, signal, result)
            check_interval: Intervalle de vérification en secondes (défaut: 5 min)
        """
        self.watchlist: dict = {}  # {ticker_or_isin: {name, last_signal, last_score, ...}}
        self.on_signal = on_signal
        self.check_interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_notifications: dict = {}  # Anti-spam: {ticker: last_notify_time}
        self.notification_cooldown = 1800  # 30 minutes entre chaque notif par action
        
        self._load_watchlist()
    
    def _get_watchlist_path(self) -> str:
        """Retourne le chemin du fichier watchlist."""
        # Sur Android, utiliser le stockage app
        try:
            from android.storage import app_storage_path  # type: ignore
            return os.path.join(app_storage_path(), WATCHLIST_FILE)
        except ImportError:
            # Desktop: utiliser le dossier config/ a cote de src/
            here = os.path.dirname(os.path.abspath(__file__))
            config_dir = os.path.join(os.path.dirname(here), "config")
            if os.path.isdir(config_dir):
                return os.path.join(config_dir, WATCHLIST_FILE)
            return os.path.join(here, WATCHLIST_FILE)
    
    def _load_watchlist(self):
        """Charge la watchlist depuis le fichier."""
        path = self._get_watchlist_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.watchlist = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.watchlist = {}
    
    def _save_watchlist(self):
        """Sauvegarde la watchlist dans le fichier."""
        path = self._get_watchlist_path()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.watchlist, f, ensure_ascii=False, indent=2)
        except IOError:
            pass
    
    def add_stock(self, ticker_or_isin: str) -> str:
        """
        Ajoute une action à la surveillance.
        Retourne le nom de l'action.
        """
        name = get_stock_name(ticker_or_isin)
        self.watchlist[ticker_or_isin] = {
            "name": name,
            "added": datetime.now().isoformat(),
            "last_signal": None,
            "last_score": 0,
            "last_check": None,
            "last_price": 0,
        }
        self._save_watchlist()
        return name
    
    def remove_stock(self, ticker_or_isin: str):
        """Retire une action de la surveillance."""
        if ticker_or_isin in self.watchlist:
            del self.watchlist[ticker_or_isin]
            self._save_watchlist()
    
    def get_watchlist(self) -> dict:
        """Retourne la watchlist actuelle."""
        return self.watchlist
    
    def check_stock(self, ticker_or_isin: str) -> dict:
        """
        Vérifie une action et met à jour la watchlist.
        Retourne le résultat de l'analyse.
        """
        try:
            df = fetch_stock_data(ticker_or_isin, period="3mo", interval="1d")
            result = analyze_stock(df)
            price_info = fetch_realtime_price(ticker_or_isin)
            
            # Mettre à jour la watchlist
            if ticker_or_isin in self.watchlist:
                prev_signal = self.watchlist[ticker_or_isin].get("last_signal")
                prev_score = self.watchlist[ticker_or_isin].get("last_score", 0)
                
                self.watchlist[ticker_or_isin].update({
                    "last_signal": result.signal.value,
                    "last_score": result.score,
                    "last_check": datetime.now().isoformat(),
                    "last_price": result.price,
                    "prev_signal": prev_signal,
                    "prev_score": prev_score,
                })
                self._save_watchlist()
                
                # Détecter changement de signal significatif
                if prev_signal and prev_signal != result.signal.value:
                    self._trigger_notification(ticker_or_isin, result, prev_signal)
                elif abs(result.score - prev_score) > 20:
                    self._trigger_notification(ticker_or_isin, result, prev_signal)
            
            return {
                "success": True,
                "result": result,
                "price_info": price_info,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    def _trigger_notification(self, ticker: str, result, prev_signal: str):
        """Envoie une notification si le cooldown est respecté."""
        now = time.time()
        last = self._last_notifications.get(ticker, 0)
        
        if now - last < self.notification_cooldown:
            return  # Cooldown pas écoulé
        
        self._last_notifications[ticker] = now
        
        if self.on_signal:
            self.on_signal(ticker, result.signal, result)
    
    def check_all(self) -> list:
        """Vérifie toutes les actions de la watchlist."""
        results = []
        for ticker in list(self.watchlist.keys()):
            result = self.check_stock(ticker)
            results.append({"ticker": ticker, **result})
            time.sleep(2)  # Pause entre les requêtes
        return results
    
    def start(self):
        """Démarre la surveillance continue en arrière-plan."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Arrête la surveillance."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
    
    def _monitor_loop(self):
        """Boucle de surveillance continue."""
        while self._running:
            if self.watchlist and self._is_market_hours():
                try:
                    self.check_all()
                except Exception:
                    pass
            
            # Attendre l'intervalle (vérifier toutes les secondes si on doit s'arrêter)
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)

    @staticmethod
    def _is_market_hours() -> bool:
        """Verifie si le marche europeen est potentiellement ouvert (lun-ven 8h-18h30 CET)."""
        now = datetime.now()
        # Weekend
        if now.weekday() >= 5:
            return False
        # Hors heures (approximation UTC+2 pour CET en ete)
        hour = now.hour
        if hour < 8 or hour >= 19:
            return False
        return True
    @property
    def is_running(self) -> bool:
        return self._running
