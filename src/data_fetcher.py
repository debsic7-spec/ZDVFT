"""
data_fetcher.py - Récupération des données boursières
Supporte les codes ISIN français et les tickers Yahoo Finance
"""

import yfinance as yf
import pandas as pd
import requests
import re
import time
from datetime import datetime


# === Cache TTL simple (evite refetch a chaque analyse) ===
_cache = {}  # {key: (timestamp, data)}
_CACHE_TTL = 300  # 5 minutes

def _cache_get(key):
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < _CACHE_TTL:
            return data
        del _cache[key]
    return None

def _cache_set(key, data):
    _cache[key] = (time.time(), data)


# Mapping ISIN connus vers tickers Yahoo Finance (Euronext Paris)
ISIN_TO_TICKER = {
    "FR0013341781": "AL2SI.PA",    # 2CRSI
    "FR0000120271": "TTE.PA",      # TotalEnergies
    "FR0000121014": "MC.PA",       # LVMH
    "FR0000120578": "SAN.PA",      # Sanofi
    "FR0000131104": "BNP.PA",      # BNP Paribas
    "FR0000125338": "CAP.PA",      # Capgemini
    "FR0000120321": "OR.PA",       # L'Oréal
    "FR0000125486": "DG.PA",       # Vinci
    "FR0000127771": "VIV.PA",      # Vivendi
    "FR0000120073": "AIR.PA",      # Airbus
    "FR0000131906": "RNO.PA",      # Renault
    "FR0000121972": "HO.PA",       # Safran
    "FR0000124141": "VIE.PA",      # Veolia
    "FR0000133308": "ORA.PA",      # Orange
    "FR0000130809": "SGO.PA",      # Saint-Gobain
    "FR0000051807": "TEP.PA",      # Teleperformance
    "FR0010307819": "LHN.PA",      # Lagardère
    "FR0000045072": "CS.PA",       # AXA  
    "FR0000120628": "ACA.PA",      # Crédit Agricole
    "FR0000130650": "DSY.PA",      # Dassault Systèmes
}


def isin_to_ticker(isin_code: str) -> str:
    """
    Convertit un code ISIN en ticker Yahoo Finance.
    Supporte les ISIN français (FR...) avec lookup local + recherche en ligne.
    """
    isin_code = isin_code.strip().upper()
    
    # Vérifier le mapping local
    if isin_code in ISIN_TO_TICKER:
        return ISIN_TO_TICKER[isin_code]
    
    # Si c'est déjà un ticker (pas un ISIN), le retourner
    if not re.match(r'^[A-Z]{2}\d{10}$', isin_code):
        # Deja un ticker — ne PAS ajouter .PA aux tickers US/internationaux
        # Heuristique: si contient un '.', c'est deja qualifie (ex: MC.PA, AAPL)
        # Si pas de '.', verifier si c'est un ticker connu US vs FR
        if '.' in isin_code:
            return isin_code
        # Tickers courts sans suffixe: tenter tel quel (US par defaut)
        # L'utilisateur peut toujours ajouter .PA manuellement
        return isin_code
    
    # Recherche via Yahoo Finance search API
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search"
        params = {"q": isin_code, "quotesCount": 1, "newsCount": 0}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            quotes = data.get("quotes", [])
            if quotes:
                return quotes[0]["symbol"]
    except Exception:
        pass
    
    return isin_code  # Retourner tel quel si non trouvé


def fetch_stock_data(ticker_or_isin: str, period: str = "3mo", interval: str = "1d") -> pd.DataFrame:
    """
    Récupère les données boursières pour un ticker ou ISIN.
    
    Args:
        ticker_or_isin: Code ISIN (ex: FR0013341781) ou ticker Yahoo (ex: LR.PA)
        period: Période (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
        interval: Intervalle (1m, 5m, 15m, 1h, 1d, 1wk, 1mo)
    
    Returns:
        DataFrame avec colonnes Open, High, Low, Close, Volume
    """
    ticker = isin_to_ticker(ticker_or_isin)
    cache_key = f"{ticker}_{period}_{interval}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval=interval)
    
    if df.empty:
        raise ValueError(f"Aucune donnée trouvée pour {ticker_or_isin} (ticker: {ticker})")
    
    _cache_set(cache_key, df)
    return df


def fetch_realtime_price(ticker_or_isin: str) -> dict:
    """
    Récupère le prix en temps réel d'une action.
    
    Returns:
        dict avec: price, change, change_percent, volume, name, currency
    """
    ticker = isin_to_ticker(ticker_or_isin)
    stock = yf.Ticker(ticker)
    info = stock.fast_info
    
    error_flag = False
    try:
        hist = stock.history(period="2d")
        if len(hist) >= 2:
            current_price = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2]
            change = current_price - prev_close
            change_pct = (change / prev_close) * 100
        elif len(hist) == 1:
            current_price = hist['Close'].iloc[-1]
            change = 0
            change_pct = 0
        else:
            current_price = info.last_price if hasattr(info, 'last_price') else 0
            change = 0
            change_pct = 0
            error_flag = True
    except Exception:
        try:
            current_price = info.last_price if hasattr(info, 'last_price') and info.last_price else 0
        except Exception:
            current_price = 0
        change = 0
        change_pct = 0
        error_flag = True
    
    try:
        currency = info.currency if hasattr(info, 'currency') else "EUR"
    except Exception:
        currency = "EUR"
    return {
        "ticker": ticker,
        "price": round(current_price, 2),
        "change": round(change, 2),
        "change_percent": round(change_pct, 2),
        "volume": int(info.last_volume) if hasattr(info, 'last_volume') and info.last_volume else 0,
        "currency": currency,
        "error": error_flag,
    }


def fetch_intraday_data(ticker_or_isin: str) -> pd.DataFrame:
    """Récupère les données intraday (intervalle 5 min, dernière journée)."""
    return fetch_stock_data(ticker_or_isin, period="1d", interval="5m")


def get_stock_name(ticker_or_isin: str) -> str:
    """Récupère le nom complet de l'action (utilise fast_info + fallback info)."""
    ticker = isin_to_ticker(ticker_or_isin)
    cached = _cache_get(f"name_{ticker}")
    if cached:
        return cached
    try:
        stock = yf.Ticker(ticker)
        # fast_info est 10x plus rapide que info
        try:
            fi = stock.fast_info
            name = getattr(fi, 'longName', None) or getattr(fi, 'shortName', None)
        except Exception:
            name = None
        if not name:
            name = stock.info.get("longName", stock.info.get("shortName", ticker))
        _cache_set(f"name_{ticker}", name)
        return name
    except Exception:
        return ticker
