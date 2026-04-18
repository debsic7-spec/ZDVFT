"""
analyzer.py - Moteur d'analyse IA du marche boursier v2.1
Combine indicateurs techniques + prediction future pour signaux achat/vente.

11 Indicateurs :
- RSI + divergences
- MACD + croisements
- Moyennes Mobiles (SMA 20, 50, 200) + Golden/Death Cross
- Bandes de Bollinger + position
- Stochastique (%K, %D)
- Volume + pression achat/vente
- Tendance (regression lineaire)
- Momentum (ROC multi-periodes)
- ADX (force de tendance)
- OBV (On Balance Volume)
- Ichimoku Cloud (tendance + support/resistance)

Score global de -100 (VENDRE FORT) a +100 (ACHETER FORT)
+ Prediction future sur 5/10/20 jours avec cone de volatilite
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Signal(Enum):
    ACHAT_FORT = "ACHAT FORT"
    ACHAT = "ACHAT"
    NEUTRE = "NEUTRE"
    VENTE = "VENTE"
    VENTE_FORTE = "VENTE FORTE"


@dataclass
class PredictionResult:
    """Prediction future IA."""
    days: list
    prix_moyen: list
    prix_haut: list
    prix_bas: list
    prix_tres_haut: list
    prix_tres_bas: list
    # Scenarios haut et bas (chemins distincts)
    scenario_haut: list   # chemin optimiste jour par jour
    scenario_bas: list    # chemin pessimiste jour par jour
    # Pic et creux attendus
    pic_prix: float       # prix max attendu sur 20j
    pic_jour: int         # jour du pic
    creux_prix: float     # prix min attendu sur 20j
    creux_jour: int       # jour du creux
    tendance: str
    objectif_5j: float
    objectif_10j: float
    objectif_20j: float
    variation_5j_pct: float
    variation_10j_pct: float
    variation_20j_pct: float
    confiance: float


@dataclass
class IntradayPrediction:
    """Prediction intraday haute frequence (5 min)."""
    intervals: list           # [5, 10, 15, 20, 25, 30] minutes
    prix_predit: list         # prix predit a chaque intervalle
    prix_haut: list           # borne haute (1 sigma)
    prix_bas: list            # borne basse (1 sigma)
    prix_extreme_haut: list   # borne haute (2 sigma)
    prix_extreme_bas: list    # borne basse (2 sigma)
    direction: str            # "HAUSSE", "BAISSE", "LATERAL"
    force: float              # 0-100, force du mouvement attendu
    objectif_5min: float      # prix predit a 5 min
    objectif_15min: float     # prix predit a 15 min
    objectif_30min: float     # prix predit a 30 min
    variation_5min_pct: float
    variation_15min_pct: float
    variation_30min_pct: float
    signal_scalping: str      # "ACHAT IMMEDIAT", "VENTE IMMEDIATE", "ATTENTE"
    stop_loss: float          # niveau stop-loss suggere
    take_profit: float        # niveau take-profit suggere
    confiance: float          # 0-100
    raisons: list             # liste de raisons du signal


@dataclass
class AnalysisResult:
    """Resultat complet de l'analyse IA."""
    signal: Signal
    score: float
    confidence: float
    price: float
    rsi: float
    macd_signal: str
    ma_signal: str
    bollinger_signal: str
    volume_signal: str
    summary: str
    details: dict
    prediction: Optional[PredictionResult] = None
    intraday: Optional[IntradayPrediction] = None

    @property
    def color(self) -> str:
        if self.signal in (Signal.ACHAT_FORT, Signal.ACHAT):
            return "#4CAF50"
        elif self.signal in (Signal.VENTE_FORTE, Signal.VENTE):
            return "#F44336"
        return "#FF9800"


# === Calcul des indicateurs techniques ===

def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower


def compute_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=period).mean()


def compute_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3):
    low_min = df['Low'].rolling(window=k_period).min()
    high_max = df['High'].rolling(window=k_period).max()
    k = 100 * (df['Close'] - low_min) / (high_max - low_min)
    d = k.rolling(window=d_period).mean()
    return k, d


def find_support_resistance(df: pd.DataFrame, window: int = 20):
    """Detecte les niveaux de support et resistance."""
    highs = df['High'].rolling(window=window, center=True).max()
    lows = df['Low'].rolling(window=window, center=True).min()
    resistance_levels = []
    support_levels = []
    for i in range(window, len(df) - window):
        if df['High'].iloc[i] == highs.iloc[i]:
            resistance_levels.append(df['High'].iloc[i])
        if df['Low'].iloc[i] == lows.iloc[i]:
            support_levels.append(df['Low'].iloc[i])
    price = df['Close'].iloc[-1]
    supports = sorted(set(round(s, 2) for s in support_levels if s < price), reverse=True)[:3]
    resistances = sorted(set(round(r, 2) for r in resistance_levels if r > price))[:3]
    return supports, resistances


def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index — mesure la force de la tendance (0-100)."""
    high, low, close = df['High'], df['Low'], df['Close']
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    atr = compute_atr(df, period)
    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1)
    adx = dx.ewm(span=period, adjust=False).mean()
    return adx


def compute_obv(df: pd.DataFrame) -> pd.Series:
    """On Balance Volume — flux de volume cumulé."""
    sign = np.sign(df['Close'].diff()).fillna(0)
    return (sign * df['Volume']).cumsum()


def compute_ichimoku(df: pd.DataFrame):
    """Ichimoku Cloud — retourne tenkan, kijun, senkou_a, senkou_b."""
    high, low = df['High'], df['Low']
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(26)
    senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    return tenkan, kijun, senkou_a, senkou_b


# === Analyse des signaux individuels ===

def analyze_rsi(rsi_value: float, rsi_series: pd.Series = None, close: pd.Series = None) -> tuple:
    if rsi_value < 20:
        score, desc = 40, "RSI tres survendu - Fort signal d'achat"
    elif rsi_value < 30:
        score, desc = 25, "RSI survendu - Signal d'achat"
    elif rsi_value < 40:
        score, desc = 10, "RSI bas - Tendance acheteuse"
    elif rsi_value < 60:
        score, desc = 0, "RSI neutre"
    elif rsi_value < 70:
        score, desc = -10, "RSI haut - Tendance vendeuse"
    elif rsi_value < 80:
        score, desc = -25, "RSI surachete - Signal de vente"
    else:
        score, desc = -40, "RSI tres surachete - Fort signal de vente"

    if rsi_series is not None and close is not None and len(rsi_series) > 20:
        price_trend = close.iloc[-1] - close.iloc[-10]
        rsi_trend = rsi_series.iloc[-1] - rsi_series.iloc[-10]
        if price_trend < 0 and rsi_trend > 0:
            score += 10
            desc += " + Divergence haussiere!"
        elif price_trend > 0 and rsi_trend < 0:
            score -= 10
            desc += " + Divergence baissiere!"
    return score, desc


def analyze_stochastic(k_value: float, d_value: float) -> tuple:
    if k_value < 20 and d_value < 20:
        return 20, f"Stoch survendu ({k_value:.0f}/{d_value:.0f}) - Achat"
    elif k_value < 20:
        return 12, f"Stoch %K survendu ({k_value:.0f}) - Achat probable"
    elif k_value > 80 and d_value > 80:
        return -20, f"Stoch surachete ({k_value:.0f}/{d_value:.0f}) - Vente"
    elif k_value > 80:
        return -12, f"Stoch %K surachete ({k_value:.0f}) - Vente probable"
    elif k_value > d_value and k_value < 50:
        return 8, f"Stoch croisement haussier ({k_value:.0f}/{d_value:.0f})"
    elif k_value < d_value and k_value > 50:
        return -8, f"Stoch croisement baissier ({k_value:.0f}/{d_value:.0f})"
    else:
        return 0, f"Stoch neutre ({k_value:.0f}/{d_value:.0f})"


def analyze_macd(macd_line: float, signal_line: float, histogram: float,
                  prev_histogram: float) -> tuple:
    score = 0
    if macd_line > signal_line:
        score += 15
        if prev_histogram < 0 and histogram > 0:
            score += 20
            return score, "Croisement HAUSSIER detecte!"
        return score, "Tendance haussiere"
    else:
        score -= 15
        if prev_histogram > 0 and histogram < 0:
            score -= 20
            return score, "Croisement BAISSIER detecte!"
        return score, "Tendance baissiere"


def analyze_moving_averages(price: float, sma20: float, sma50: float,
                              sma200: Optional[float]) -> tuple:
    score = 0
    signals = []
    if price > sma20:
        score += 10; signals.append("Prix > MM20")
    else:
        score -= 10; signals.append("Prix < MM20")
    if price > sma50:
        score += 10; signals.append("Prix > MM50")
    else:
        score -= 10; signals.append("Prix < MM50")
    if sma20 > sma50:
        score += 8; signals.append("Croisement dore")
    else:
        score -= 8; signals.append("Croisement mortel")
    if sma200 is not None and not np.isnan(sma200):
        if price > sma200:
            score += 8; signals.append("Prix > MM200")
        else:
            score -= 8; signals.append("Prix < MM200")
    return score, " | ".join(signals)


def analyze_bollinger(price: float, upper: float, middle: float, lower: float) -> tuple:
    band_width = upper - lower
    if band_width == 0:
        return 0, "Donnees insuffisantes"
    position = (price - lower) / band_width
    if position < 0.05:
        return 25, "Prix SOUS bande basse - Achat fort"
    elif position < 0.2:
        return 15, "Proche bande basse - Achat"
    elif position < 0.4:
        return 5, "Zone basse - Acheteur"
    elif position < 0.6:
        return 0, "Milieu bandes - Neutre"
    elif position < 0.8:
        return -5, "Zone haute - Vendeur"
    elif position < 0.95:
        return -15, "Proche bande haute - Vente"
    else:
        return -25, "AU-DESSUS bande haute - Vente forte"


def analyze_volume(df: pd.DataFrame) -> tuple:
    volumes = df['Volume']
    closes = df['Close']
    if len(volumes) < 20:
        return 0, "Donnees insuffisantes"
    avg_volume = volumes.iloc[-20:].mean()
    current_volume = volumes.iloc[-1]
    if avg_volume == 0:
        return 0, "Pas de donnees"
    ratio = current_volume / avg_volume
    price_up = closes.iloc[-1] > closes.iloc[-2] if len(closes) >= 2 else True
    if ratio > 2.0:
        score = 8 if price_up else -8
        return score, f"Volume TRES eleve ({ratio:.1f}x) en {'hausse' if price_up else 'baisse'}"
    elif ratio > 1.5:
        score = 5 if price_up else -5
        return score, f"Volume eleve ({ratio:.1f}x) en {'hausse' if price_up else 'baisse'}"
    elif ratio > 0.7:
        return 0, f"Volume normal ({ratio:.1f}x)"
    else:
        return -2, f"Volume faible ({ratio:.1f}x)"


def detect_trend(closes: pd.Series, window: int = 10) -> tuple:
    if len(closes) < window:
        return 0, "Donnees insuffisantes"
    recent = closes.iloc[-window:].values
    x = np.arange(len(recent))
    slope = np.polyfit(x, recent, 1)[0]
    slope_pct = (slope / recent[0]) * 100
    if slope_pct > 1.5:
        return 15, f"HAUSSIERE forte (+{slope_pct:.2f}%/j)"
    elif slope_pct > 0.5:
        return 8, f"Haussiere (+{slope_pct:.2f}%/j)"
    elif slope_pct > -0.5:
        return 0, f"Laterale ({slope_pct:+.2f}%/j)"
    elif slope_pct > -1.5:
        return -8, f"Baissiere ({slope_pct:.2f}%/j)"
    else:
        return -15, f"BAISSIERE forte ({slope_pct:.2f}%/j)"


def compute_momentum(closes: pd.Series) -> tuple:
    if len(closes) < 20:
        return 0, "Donnees insuffisantes"
    roc_5 = (closes.iloc[-1] / closes.iloc[-5] - 1) * 100
    roc_10 = (closes.iloc[-1] / closes.iloc[-10] - 1) * 100
    roc_20 = (closes.iloc[-1] / closes.iloc[-20] - 1) * 100
    score = 0
    if roc_5 > 3: score += 10
    elif roc_5 > 1: score += 5
    elif roc_5 < -3: score -= 10
    elif roc_5 < -1: score -= 5
    if roc_10 > 0: score += 3
    else: score -= 3
    return score, f"ROC 5j:{roc_5:+.1f}% | 10j:{roc_10:+.1f}% | 20j:{roc_20:+.1f}%"


def analyze_adx(adx_value: float, plus_di: float = None, minus_di: float = None) -> tuple:
    """Score ADX: tendance forte = meilleure fiabilite des autres signaux."""
    if np.isnan(adx_value):
        return 0, "ADX indisponible"
    if adx_value >= 50:
        return 12, f"Tendance TRES forte (ADX {adx_value:.0f})"
    elif adx_value >= 25:
        return 6, f"Tendance confirmee (ADX {adx_value:.0f})"
    elif adx_value >= 20:
        return 0, f"Tendance naissante (ADX {adx_value:.0f})"
    else:
        return -4, f"Pas de tendance (ADX {adx_value:.0f})"


def analyze_obv(obv: pd.Series, close: pd.Series) -> tuple:
    """Score OBV: divergence volume/prix = signal de retournement."""
    if len(obv) < 20:
        return 0, "OBV donnees insuffisantes"
    obv_slope = (obv.iloc[-1] - obv.iloc[-10]) / max(abs(obv.iloc[-10]), 1)
    price_slope = (close.iloc[-1] - close.iloc[-10]) / close.iloc[-10]
    # Divergence haussiere: prix baisse mais OBV monte
    if price_slope < -0.01 and obv_slope > 0.01:
        return 15, "Divergence HAUSSIERE OBV (accumulation)"
    # Divergence baissiere: prix monte mais OBV baisse
    elif price_slope > 0.01 and obv_slope < -0.01:
        return -15, "Divergence BAISSIERE OBV (distribution)"
    # Confirmation haussiere
    elif price_slope > 0 and obv_slope > 0:
        return 5, "OBV confirme hausse"
    # Confirmation baissiere
    elif price_slope < 0 and obv_slope < 0:
        return -5, "OBV confirme baisse"
    return 0, "OBV neutre"


def analyze_ichimoku(price: float, tenkan: float, kijun: float,
                     senkou_a: float, senkou_b: float) -> tuple:
    """Score Ichimoku: position vs nuage + croisements TK."""
    if any(np.isnan(v) for v in [tenkan, kijun, senkou_a, senkou_b]):
        return 0, "Ichimoku donnees insuffisantes"
    cloud_top = max(senkou_a, senkou_b)
    cloud_bottom = min(senkou_a, senkou_b)
    score = 0
    signals = []
    # Prix vs nuage
    if price > cloud_top:
        score += 10
        signals.append("AU-DESSUS nuage")
    elif price < cloud_bottom:
        score -= 10
        signals.append("EN-DESSOUS nuage")
    else:
        signals.append("DANS le nuage")
    # Croisement TK
    if tenkan > kijun:
        score += 5
        signals.append("TK haussier")
    else:
        score -= 5
        signals.append("TK baissier")
    return score, " | ".join(signals)


# === Prediction future IA ===

def predict_future(df: pd.DataFrame, days_ahead: int = 20) -> PredictionResult:
    """
    Prediction basee sur tendance + volatilite ATR + momentum + RSI mean-reversion.
    Genere un cone de confiance qui s'elargit avec le temps.
    """
    close = df['Close']
    price = close.iloc[-1]

    window = min(20, len(close) - 1)
    recent = close.iloc[-window:].values
    x = np.arange(window)
    slope_linear = np.polyfit(x, recent, 1)[0]

    # Volatilite via ATR
    atr = compute_atr(df)
    current_atr = atr.iloc[-1] if not atr.empty and not np.isnan(atr.iloc[-1]) else price * 0.02
    daily_vol = current_atr / price

    # Momentum
    roc_5 = (close.iloc[-1] / close.iloc[-min(5, len(close)-1)] - 1)
    roc_10 = (close.iloc[-1] / close.iloc[-min(10, len(close)-1)] - 1)

    # Biais directionnel combine
    trend_bias = slope_linear / price
    momentum_bias = (roc_5 * 0.6 + roc_10 * 0.4) / 10

    # RSI mean-reversion
    rsi = compute_rsi(close)
    current_rsi = rsi.iloc[-1] if not np.isnan(rsi.iloc[-1]) else 50
    rsi_bias = 0
    if current_rsi > 75:
        rsi_bias = -0.002 * (current_rsi - 50) / 50
    elif current_rsi < 25:
        rsi_bias = 0.002 * (50 - current_rsi) / 50

    daily_bias = max(-0.03, min(0.03, trend_bias + momentum_bias + rsi_bias))

    # Biais scenario optimiste/pessimiste
    # Scenario haut: momentum positif + trend fort
    bullish_extra = max(0, momentum_bias) * 2 + max(0, trend_bias) * 1.5
    optimist_bias = max(-0.02, min(0.05, daily_bias + abs(daily_vol) * 0.5 + bullish_extra))
    # Scenario bas: momentum negatif + mean-reversion forte
    bearish_extra = min(0, momentum_bias) * 2 + min(0, trend_bias) * 1.5
    pessimist_bias = max(-0.05, min(0.02, daily_bias - abs(daily_vol) * 0.5 + bearish_extra))

    days = list(range(1, days_ahead + 1))
    prix_moyen, prix_haut, prix_bas, prix_tres_haut, prix_tres_bas = [], [], [], [], []
    scenario_haut, scenario_bas = [], []

    for d in days:
        decay = 0.95 ** d
        # Compounding geometrique (correct) au lieu de lineaire
        predicted = price * (1 + daily_bias * decay) ** d
        vol_spread = daily_vol * np.sqrt(d) * price

        # Scenarios: trajectoires distinctes
        opt = price * (1 + optimist_bias * decay) ** d
        pes = price * (1 + pessimist_bias * decay) ** d

        prix_moyen.append(round(predicted, 4))
        prix_haut.append(round(predicted + vol_spread, 4))
        prix_bas.append(round(predicted - vol_spread, 4))
        prix_tres_haut.append(round(predicted + vol_spread * 1.96, 4))
        prix_tres_bas.append(round(predicted - vol_spread * 1.96, 4))
        scenario_haut.append(round(opt, 4))
        scenario_bas.append(round(pes, 4))

    # Detecter pic et creux attendus
    pic_idx = int(np.argmax(scenario_haut))
    creux_idx = int(np.argmin(scenario_bas))
    pic_prix = round(scenario_haut[pic_idx], 2)
    pic_jour = days[pic_idx]
    creux_prix = round(scenario_bas[creux_idx], 2)
    creux_jour = days[creux_idx]

    obj_5 = prix_moyen[min(4, len(prix_moyen)-1)]
    obj_10 = prix_moyen[min(9, len(prix_moyen)-1)]
    obj_20 = prix_moyen[min(19, len(prix_moyen)-1)]
    var_5 = ((obj_5 / price) - 1) * 100
    var_10 = ((obj_10 / price) - 1) * 100
    var_20 = ((obj_20 / price) - 1) * 100

    tendance = "haussiere" if var_20 > 2 else ("baissiere" if var_20 < -2 else "laterale")
    # Confiance: haute quand le bias est FAIBLE (marche previsible), basse quand le bias est EXTREME
    confiance = max(20, min(85, 70 - abs(daily_bias) * 800))

    return PredictionResult(
        days=days, prix_moyen=prix_moyen, prix_haut=prix_haut, prix_bas=prix_bas,
        prix_tres_haut=prix_tres_haut, prix_tres_bas=prix_tres_bas,
        scenario_haut=scenario_haut, scenario_bas=scenario_bas,
        pic_prix=pic_prix, pic_jour=pic_jour,
        creux_prix=creux_prix, creux_jour=creux_jour,
        tendance=tendance,
        objectif_5j=round(obj_5, 2), objectif_10j=round(obj_10, 2), objectif_20j=round(obj_20, 2),
        variation_5j_pct=round(var_5, 2), variation_10j_pct=round(var_10, 2),
        variation_20j_pct=round(var_20, 2), confiance=round(confiance, 1),
    )


# === Prediction intraday 5 min (scalping) ===

def predict_intraday(df_intraday: pd.DataFrame, df_daily: pd.DataFrame = None) -> IntradayPrediction:
    """
    Prediction ultra-court terme basee sur donnees 5 min.
    Combine: micro-tendance, VWAP, momentum rapide, RSI rapide,
    pression achat/vente, acceleration de prix, niveaux cles.
    """
    close = df_intraday['Close']
    high = df_intraday['High']
    low = df_intraday['Low']
    volume = df_intraday['Volume']
    price = float(close.iloc[-1])
    n = len(close)

    raisons = []
    score_total = 0.0  # -100 a +100

    # --- 1. Micro-tendance lineaire (dernieres 6 bougies = 30 min) ---
    lookback = min(6, n - 1)
    recent = close.iloc[-lookback:].values
    x = np.arange(lookback)
    if lookback >= 3:
        slope = np.polyfit(x, recent, 1)[0]
        slope_pct = (slope / price) * 100  # % par bougie de 5 min
    else:
        slope = 0
        slope_pct = 0

    if slope_pct > 0.1:
        score_total += 20
        raisons.append(f"Micro-tendance HAUSSIERE ({slope_pct:+.3f}%/5min)")
    elif slope_pct > 0.03:
        score_total += 10
        raisons.append(f"Micro-tendance haussiere ({slope_pct:+.3f}%/5min)")
    elif slope_pct < -0.1:
        score_total -= 20
        raisons.append(f"Micro-tendance BAISSIERE ({slope_pct:+.3f}%/5min)")
    elif slope_pct < -0.03:
        score_total -= 10
        raisons.append(f"Micro-tendance baissiere ({slope_pct:+.3f}%/5min)")

    # --- 2. Acceleration (2eme derivee) ---
    if n >= 4:
        v1 = close.iloc[-2] - close.iloc[-3]
        v2 = close.iloc[-1] - close.iloc[-2]
        accel = v2 - v1
        accel_pct = (accel / price) * 100
        if accel_pct > 0.05:
            score_total += 12
            raisons.append(f"Acceleration HAUSSIERE ({accel_pct:+.3f}%)")
        elif accel_pct < -0.05:
            score_total -= 12
            raisons.append(f"Acceleration BAISSIERE ({accel_pct:+.3f}%)")

    # --- 3. RSI rapide (5 periodes) ---
    rsi_fast = compute_rsi(close, period=5)
    current_rsi_fast = float(rsi_fast.iloc[-1]) if not np.isnan(rsi_fast.iloc[-1]) else 50
    if current_rsi_fast < 15:
        score_total += 25
        raisons.append(f"RSI(5) SURVENDU extreme ({current_rsi_fast:.0f}) -> Rebond imminent")
    elif current_rsi_fast < 25:
        score_total += 15
        raisons.append(f"RSI(5) survendu ({current_rsi_fast:.0f})")
    elif current_rsi_fast > 85:
        score_total -= 25
        raisons.append(f"RSI(5) SURACHETE extreme ({current_rsi_fast:.0f}) -> Correction imminente")
    elif current_rsi_fast > 75:
        score_total -= 15
        raisons.append(f"RSI(5) surachete ({current_rsi_fast:.0f})")

    # --- 4. VWAP (Volume Weighted Average Price) ---
    if volume.sum() > 0:
        typical_price = (high + low + close) / 3
        vwap = float((typical_price * volume).cumsum().iloc[-1] / volume.cumsum().iloc[-1])
        vwap_diff_pct = ((price - vwap) / vwap) * 100
        if price > vwap * 1.002:
            score_total += 10
            raisons.append(f"Prix AU-DESSUS VWAP ({vwap:.2f}, +{vwap_diff_pct:.2f}%)")
        elif price < vwap * 0.998:
            score_total -= 10
            raisons.append(f"Prix EN-DESSOUS VWAP ({vwap:.2f}, {vwap_diff_pct:.2f}%)")
    else:
        vwap = price

    # --- 5. Pression volume (achat vs vente) ---
    if n >= 7 and volume.iloc[-6:].sum() > 0:
        up_vol = sum(volume.iloc[i] for i in range(-6, 0) if close.iloc[i] > close.iloc[i-1])
        down_vol = sum(volume.iloc[i] for i in range(-6, 0) if close.iloc[i] < close.iloc[i-1])
        total_vol = up_vol + down_vol
        if total_vol > 0:
            buy_pressure = up_vol / total_vol
            if buy_pressure > 0.7:
                score_total += 12
                raisons.append(f"Pression ACHETEUSE forte ({buy_pressure:.0%})")
            elif buy_pressure > 0.55:
                score_total += 5
                raisons.append(f"Pression acheteuse ({buy_pressure:.0%})")
            elif buy_pressure < 0.3:
                score_total -= 12
                raisons.append(f"Pression VENDEUSE forte ({1-buy_pressure:.0%})")
            elif buy_pressure < 0.45:
                score_total -= 5
                raisons.append(f"Pression vendeuse ({1-buy_pressure:.0%})")

    # --- 6. Spike de volume (derniere bougie vs moyenne) ---
    if n >= 12:
        avg_vol = float(volume.iloc[-12:-1].mean())
        curr_vol = float(volume.iloc[-1])
        if avg_vol > 0:
            vol_ratio = curr_vol / avg_vol
            price_up = close.iloc[-1] > close.iloc[-2]
            if vol_ratio > 3.0:
                bonus = 15 if price_up else -15
                score_total += bonus
                raisons.append(f"SPIKE volume x{vol_ratio:.1f} en {'hausse' if price_up else 'baisse'}")
            elif vol_ratio > 2.0:
                bonus = 8 if price_up else -8
                score_total += bonus
                raisons.append(f"Volume eleve x{vol_ratio:.1f} en {'hausse' if price_up else 'baisse'}")

    # --- 7. EMA crossover rapide (3 vs 8) ---
    if n >= 10:
        ema3 = compute_ema(close, 3)
        ema8 = compute_ema(close, 8)
        ema3_val = float(ema3.iloc[-1])
        ema8_val = float(ema8.iloc[-1])
        ema3_prev = float(ema3.iloc[-2])
        ema8_prev = float(ema8.iloc[-2])
        if ema3_prev <= ema8_prev and ema3_val > ema8_val:
            score_total += 18
            raisons.append("CROISEMENT EMA3/EMA8 HAUSSIER!")
        elif ema3_prev >= ema8_prev and ema3_val < ema8_val:
            score_total -= 18
            raisons.append("CROISEMENT EMA3/EMA8 BAISSIER!")
        elif ema3_val > ema8_val:
            score_total += 5
        elif ema3_val < ema8_val:
            score_total -= 5

    # --- 8. Contexte daily (si disponible) ---
    if df_daily is not None and len(df_daily) >= 20:
        daily_close = df_daily['Close']
        daily_rsi = compute_rsi(daily_close)
        d_rsi = float(daily_rsi.iloc[-1]) if not np.isnan(daily_rsi.iloc[-1]) else 50
        sma20_d = float(compute_sma(daily_close, 20).iloc[-1])
        if price > sma20_d and d_rsi < 70:
            score_total += 5
            raisons.append(f"Contexte daily favorable (RSI:{d_rsi:.0f}, > SMA20)")
        elif price < sma20_d and d_rsi > 30:
            score_total -= 5
            raisons.append(f"Contexte daily defavorable (RSI:{d_rsi:.0f}, < SMA20)")

    # --- Calcul du score final ---
    score_total = max(-100, min(100, score_total))

    # --- Volatilite intraday (ATR 5min) ---
    if n >= 5:
        tr_vals = []
        for i in range(-min(14, n-1), 0):
            hl = float(high.iloc[i] - low.iloc[i])
            hc = abs(float(high.iloc[i] - close.iloc[i-1]))
            lc = abs(float(low.iloc[i] - close.iloc[i-1]))
            tr_vals.append(max(hl, hc, lc))
        atr_5min = np.mean(tr_vals) if tr_vals else price * 0.001
    else:
        atr_5min = price * 0.001

    vol_per_bar = atr_5min / price

    # --- Bias directionnel par bar ---
    bias_per_bar = (score_total / 100) * vol_per_bar * 1.5

    # --- Generer predictions sur 6 intervalles (5 a 30 min) ---
    intervals = [1, 2, 3, 4, 5, 6]  # en barres de 5 min
    minutes = [5, 10, 15, 20, 25, 30]
    prix_predit, prix_haut, prix_bas = [], [], []
    prix_extreme_haut, prix_extreme_bas = [], []

    for bars in intervals:
        decay = 0.92 ** bars
        predicted = price * (1 + bias_per_bar * decay * bars)
        spread_1s = atr_5min * np.sqrt(bars)
        spread_2s = spread_1s * 1.96

        prix_predit.append(round(predicted, 4))
        prix_haut.append(round(predicted + spread_1s, 4))
        prix_bas.append(round(predicted - spread_1s, 4))
        prix_extreme_haut.append(round(predicted + spread_2s, 4))
        prix_extreme_bas.append(round(predicted - spread_2s, 4))

    # --- Direction et signal ---
    if score_total > 25:
        direction = "HAUSSE"
        signal_scalping = "ACHAT IMMEDIAT"
    elif score_total > 10:
        direction = "HAUSSE"
        signal_scalping = "ACHAT IMMEDIAT" if score_total > 15 else "ATTENTE"
    elif score_total < -25:
        direction = "BAISSE"
        signal_scalping = "VENTE IMMEDIATE"
    elif score_total < -10:
        direction = "BAISSE"
        signal_scalping = "VENTE IMMEDIATE" if score_total < -15 else "ATTENTE"
    else:
        direction = "LATERAL"
        signal_scalping = "ATTENTE"

    # --- Stop-loss / Take-profit ---
    if direction == "HAUSSE":
        stop_loss = round(price - atr_5min * 2, 4)
        take_profit = round(prix_predit[5] + atr_5min, 4)  # objectif 30min + marge
    elif direction == "BAISSE":
        stop_loss = round(price + atr_5min * 2, 4)
        take_profit = round(prix_predit[5] - atr_5min, 4)
    else:
        stop_loss = round(price - atr_5min * 1.5, 4)
        take_profit = round(price + atr_5min * 1.5, 4)

    force = min(100, abs(score_total) * 1.2)

    # Confiance basee sur accord des signaux
    nb_signaux = len(raisons)
    positifs = sum(1 for r in raisons if any(w in r.upper() for w in ['HAUSS', 'ACHET', 'REBOND', 'DESSUS', 'SURVENDU']))
    negatifs = sum(1 for r in raisons if any(w in r.upper() for w in ['BAISS', 'VEND', 'CORRECT', 'DESSOUS', 'SURACHET']))
    if nb_signaux > 0:
        agreement = max(positifs, negatifs) / nb_signaux
        confiance = min(92, agreement * 70 + abs(score_total) * 0.3)
    else:
        confiance = 30

    obj_5 = prix_predit[0]   # 5 min
    obj_15 = prix_predit[2]  # 15 min
    obj_30 = prix_predit[5]  # 30 min

    return IntradayPrediction(
        intervals=minutes,
        prix_predit=prix_predit,
        prix_haut=prix_haut,
        prix_bas=prix_bas,
        prix_extreme_haut=prix_extreme_haut,
        prix_extreme_bas=prix_extreme_bas,
        direction=direction,
        force=round(force, 1),
        objectif_5min=round(obj_5, 4),
        objectif_15min=round(obj_15, 4),
        objectif_30min=round(obj_30, 4),
        variation_5min_pct=round(((obj_5 / price) - 1) * 100, 4),
        variation_15min_pct=round(((obj_15 / price) - 1) * 100, 4),
        variation_30min_pct=round(((obj_30 / price) - 1) * 100, 4),
        signal_scalping=signal_scalping,
        stop_loss=stop_loss,
        take_profit=take_profit,
        confiance=round(confiance, 1),
        raisons=raisons,
    )


# === Analyse complete IA ===

def analyze_stock(df: pd.DataFrame) -> AnalysisResult:
    required_cols = {'Open', 'High', 'Low', 'Close', 'Volume'}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes dans le DataFrame: {missing}")
    if len(df) < 26:
        raise ValueError("Pas assez de donnees (minimum 26 jours)")

    close = df['Close']
    price = close.iloc[-1]

    rsi = compute_rsi(close)
    macd_line, signal_line, histogram = compute_macd(close)
    upper, middle, lower = compute_bollinger_bands(close)
    sma20 = compute_sma(close, 20)
    sma50 = compute_sma(close, 50)
    sma200 = compute_sma(close, 200) if len(close) >= 200 else pd.Series([np.nan])
    stoch_k, stoch_d = compute_stochastic(df)

    current_rsi = rsi.iloc[-1]
    current_macd = macd_line.iloc[-1]
    current_signal = signal_line.iloc[-1]
    current_hist = histogram.iloc[-1]
    prev_hist = histogram.iloc[-2] if len(histogram) >= 2 else 0
    current_upper = upper.iloc[-1]
    current_middle = middle.iloc[-1]
    current_lower = lower.iloc[-1]
    current_sma20 = sma20.iloc[-1]
    current_sma50 = sma50.iloc[-1] if len(sma50) >= 50 else price
    current_sma200 = sma200.iloc[-1] if len(sma200) >= 200 else None
    current_stoch_k = stoch_k.iloc[-1] if not np.isnan(stoch_k.iloc[-1]) else 50
    current_stoch_d = stoch_d.iloc[-1] if not np.isnan(stoch_d.iloc[-1]) else 50

    rsi_score, rsi_desc = analyze_rsi(current_rsi, rsi, close)
    macd_score, macd_desc = analyze_macd(current_macd, current_signal, current_hist, prev_hist)
    ma_score, ma_desc = analyze_moving_averages(price, current_sma20, current_sma50, current_sma200)
    boll_score, boll_desc = analyze_bollinger(price, current_upper, current_middle, current_lower)
    vol_score, vol_desc = analyze_volume(df)
    trend_score, trend_desc = detect_trend(close)
    stoch_score, stoch_desc = analyze_stochastic(current_stoch_k, current_stoch_d)
    mom_score, mom_desc = compute_momentum(close)
    supports, resistances = find_support_resistance(df)

    # Nouveaux indicateurs (ADX, OBV, Ichimoku)
    adx = compute_adx(df)
    current_adx = adx.iloc[-1] if not adx.empty and not np.isnan(adx.iloc[-1]) else 0
    adx_score, adx_desc = analyze_adx(current_adx)

    obv = compute_obv(df)
    obv_score, obv_desc = analyze_obv(obv, close)

    tenkan, kijun, senkou_a, senkou_b = compute_ichimoku(df)
    t_val = tenkan.iloc[-1] if not np.isnan(tenkan.iloc[-1]) else np.nan
    k_val = kijun.iloc[-1] if not np.isnan(kijun.iloc[-1]) else np.nan
    sa_val = senkou_a.iloc[-1] if len(senkou_a) > 0 and not np.isnan(senkou_a.iloc[-1]) else np.nan
    sb_val = senkou_b.iloc[-1] if len(senkou_b) > 0 and not np.isnan(senkou_b.iloc[-1]) else np.nan
    ichi_score, ichi_desc = analyze_ichimoku(price, t_val, k_val, sa_val, sb_val)

    # 11 indicateurs ponderes
    raw_score = (
        rsi_score * 0.12 +
        macd_score * 0.15 +
        ma_score * 0.12 +
        boll_score * 0.08 +
        stoch_score * 0.08 +
        vol_score * 0.05 +
        trend_score * 0.12 +
        mom_score * 0.08 +
        adx_score * 0.07 +
        obv_score * 0.06 +
        ichi_score * 0.07
    )
    total_score = max(-100, min(100, raw_score * 3.0))

    if total_score >= 35: signal = Signal.ACHAT_FORT
    elif total_score >= 12: signal = Signal.ACHAT
    elif total_score <= -35: signal = Signal.VENTE_FORTE
    elif total_score <= -12: signal = Signal.VENTE
    else: signal = Signal.NEUTRE

    all_scores = [rsi_score, macd_score, ma_score, boll_score, stoch_score, trend_score, mom_score, vol_score, adx_score, obv_score, ichi_score]
    positive = sum(1 for s in all_scores if s > 2)
    negative = sum(1 for s in all_scores if s < -2)
    agreement = max(positive, negative) / len(all_scores)
    confidence = min(95, agreement * 100 + abs(total_score) * 0.2)

    prediction = predict_future(df)

    n_ind = len(all_scores)
    if signal == Signal.ACHAT_FORT:
        summary = f"ACHAT FORT - {positive}/{n_ind} haussiers. Objectif 5j: {prediction.objectif_5j:.2f} EUR ({prediction.variation_5j_pct:+.1f}%)"
    elif signal == Signal.ACHAT:
        summary = f"Achat - {positive}/{n_ind} positifs. Objectif 5j: {prediction.objectif_5j:.2f} EUR ({prediction.variation_5j_pct:+.1f}%)"
    elif signal == Signal.VENTE_FORTE:
        summary = f"VENTE FORTE - {negative}/{n_ind} baissiers. Objectif 5j: {prediction.objectif_5j:.2f} EUR ({prediction.variation_5j_pct:+.1f}%)"
    elif signal == Signal.VENTE:
        summary = f"Vente - {negative}/{n_ind} negatifs. Objectif 5j: {prediction.objectif_5j:.2f} EUR ({prediction.variation_5j_pct:+.1f}%)"
    else:
        summary = f"Neutre - Attendre confirmation. Objectif 5j: {prediction.objectif_5j:.2f} EUR ({prediction.variation_5j_pct:+.1f}%)"

    return AnalysisResult(
        signal=signal, score=round(total_score, 1), confidence=round(confidence, 1),
        price=round(price, 2), rsi=round(current_rsi, 1),
        macd_signal=macd_desc, ma_signal=ma_desc,
        bollinger_signal=boll_desc, volume_signal=vol_desc,
        summary=summary,
        details={
            "rsi": {"value": round(current_rsi, 1), "score": rsi_score, "desc": rsi_desc},
            "macd": {"score": macd_score, "desc": macd_desc},
            "moyennes_mobiles": {"score": ma_score, "desc": ma_desc},
            "bollinger": {"score": boll_score, "desc": boll_desc},
            "stochastique": {"score": stoch_score, "desc": stoch_desc},
            "volume": {"score": vol_score, "desc": vol_desc},
            "tendance": {"score": trend_score, "desc": trend_desc},
            "momentum": {"score": mom_score, "desc": mom_desc},
            "adx": {"value": round(current_adx, 1), "score": adx_score, "desc": adx_desc},
            "obv": {"score": obv_score, "desc": obv_desc},
            "ichimoku": {"score": ichi_score, "desc": ichi_desc},
            "sma20": round(current_sma20, 2) if not np.isnan(current_sma20) else None,
            "sma50": round(current_sma50, 2) if not np.isnan(current_sma50) else None,
            "sma200": round(current_sma200, 2) if current_sma200 and not np.isnan(current_sma200) else None,
            "stoch_k": round(current_stoch_k, 1),
            "stoch_d": round(current_stoch_d, 1),
            "supports": supports,
            "resistances": resistances,
        },
        prediction=prediction,
    )


def quick_check(df: pd.DataFrame) -> tuple:
    result = analyze_stock(df)
    return result.signal.value, result.score
