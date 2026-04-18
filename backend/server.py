import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pywebpush import webpush, WebPushException
import yfinance as yf
import pandas as pd
import ta
from typing import Optional, List, Dict
import asyncio
import json
import os
from pathlib import Path

app = FastAPI(title="PEA Screener Tracker AI v2")

# Dossier frontend (parent du dossier backend)
FRONTEND_DIR = Path(__file__).resolve().parent.parent

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ASSET_MAPPING = {
    'FR0013341781': ('2CRSI S.A.', 'AL2SI.PA'),
    'FR0000131104': ('BNP Paribas', 'BNP.PA'),
    'FR0000120271': ('TotalEnergies', 'TTE.PA'),
    'FR0000121014': ('LVMH', 'MC.PA'),
    'FR0000120578': ('Sanofi', 'SAN.PA'),
    'FR0000120073': ('Air Liquide', 'AI.PA'),
    'FR0000125007': ('Saint-Gobain', 'SGO.PA'),
    'FR0011550185': ('Amundi S&P 500', 'PE500.PA'),
    'FR0013412020': ('Amundi Nasdaq', 'PUST.PA'),
}

def compute_ai_signals(df_intraday: pd.DataFrame, df_long: pd.DataFrame, current_price: float):
    """Compute RSI, MACD and VWAP signals, return structured result."""
    result = {
        "ai_status": "GARDER",
        "ai_details": "Analyse insuffisante.",
        "rsi": 50.0,
        "macd": 0.0,
        "vwap_signal_pct": 50.0,
    }
    
    if len(df_long) < 30:
        return result

    # RSI
    rsi_series = ta.momentum.RSIIndicator(close=df_long['Close'], window=14).rsi()
    rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0
    
    # MACD
    macd_ind = ta.trend.MACD(close=df_long['Close'])
    macd_val = float(macd_ind.macd().iloc[-1])
    macd_sig = float(macd_ind.macd_signal().iloc[-1])
    macd_hist = macd_val - macd_sig   # Positive = bullish cross
    
    # VWAP signal
    if 'VWAP' in df_intraday.columns and not df_intraday.empty:
        vwap_latest = float(df_intraday['VWAP'].iloc[-1])
        vwap_pct = 65.0 if current_price > vwap_latest else 35.0
    else:
        vwap_pct = 50.0
        vwap_latest = current_price

    result["rsi"] = round(rsi, 1)
    result["macd"] = round(macd_val, 3)
    result["vwap_signal_pct"] = vwap_pct

    # Decision logic
    signals_buy = 0
    signals_sell = 0

    if rsi < 30: signals_buy += 2
    elif rsi < 40: signals_buy += 1
    elif rsi > 70: signals_sell += 2
    elif rsi > 60: signals_sell += 1

    if macd_hist > 0: signals_buy += 1
    else: signals_sell += 1

    if vwap_pct > 50: signals_buy += 1
    else: signals_sell += 1

    if signals_buy >= 3:
        result["ai_status"] = "ACHETER FORT"
        result["ai_details"] = f"RSI survendu ({rsi:.0f}). Signal MACD haussier avec rebond au-dessus du VWAP institutionnel."
    elif signals_sell >= 3:
        result["ai_status"] = "VENDRE"
        result["ai_details"] = f"RSI en surchauffe ({rsi:.0f}). Cours sous le VWAP avec pression baissière confirmée."
    elif signals_buy >= 2:
        result["ai_status"] = "ACHETER"
        result["ai_details"] = f"Configuration technique favorable. RSI : {rsi:.0f}, MACD positif."
    else:
        result["ai_status"] = "GARDER"
        result["ai_details"] = "Aucun signal technique fort. Consolidation en cours."

    return result


@app.get("/api/asset/{isin}")
def get_asset_data(isin: str):
    if isin not in ASSET_MAPPING:
        raise HTTPException(status_code=404, detail="Asset not found")

    try:
        return _get_asset_data_impl(isin)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")

def _get_asset_data_impl(isin: str):
    name, ticker = ASSET_MAPPING[isin]
    stock = yf.Ticker(ticker)

    # --- Single daily call for price/change/52w/indicators ---
    df_long = stock.history(period="1y", interval="1d")
    if isinstance(df_long.columns, pd.MultiIndex):
        df_long.columns = df_long.columns.get_level_values(0)
    if df_long.empty:
        raise HTTPException(status_code=400, detail="No daily data available")

    current_price = round(float(df_long['Close'].iloc[-1]), 2)
    prev_close = float(df_long['Close'].iloc[-2]) if len(df_long) > 1 else current_price
    change_pct = round((current_price - prev_close) / prev_close * 100, 2)
    high52 = round(float(df_long['High'].max()), 2)
    low52 = round(float(df_long['Low'].min()), 2)

    # --- Single intraday call ---
    df_intra = pd.DataFrame()
    use_daily = False

    try:
        df_intra = stock.history(period="5d", interval="5m")
        if isinstance(df_intra.columns, pd.MultiIndex):
            df_intra.columns = df_intra.columns.get_level_values(0)
        if not df_intra.empty:
            last_day = df_intra.index[-1].date()
            df_intra = df_intra[df_intra.index.date == last_day].copy()
    except Exception as e:
        print(f"Intraday 5m error for {ticker}: {e}")
        df_intra = pd.DataFrame()

    if df_intra.empty or len(df_intra) < 2:
        # Fallback: use last 30 daily candles
        use_daily = True
        df_intra = df_long.tail(30).copy()

    # --- VWAP ---
    if 'Volume' in df_intra.columns and df_intra['Volume'].sum() > 0:
        df_intra['Typical'] = (df_intra['High'] + df_intra['Low'] + df_intra['Close']) / 3
        df_intra['CumVP'] = (df_intra['Typical'] * df_intra['Volume']).cumsum()
        df_intra['CumV'] = df_intra['Volume'].cumsum()
        df_intra['VWAP'] = df_intra['CumVP'] / df_intra['CumV']
    else:
        df_intra['VWAP'] = df_intra['Close'].rolling(window=5, min_periods=1).mean()

    ai = compute_ai_signals(df_intra, df_long, current_price)

    # --- Labels ---
    if use_daily:
        labels = [idx.strftime("%d/%m") for idx in df_intra.index]
    else:
        labels = [idx.strftime("%Hh%M") for idx in df_intra.index]

    # --- Day OHLC from intraday candles ---
    day_open = round(float(df_intra['Open'].iloc[0]), 2)
    day_high = round(float(df_intra['High'].max()), 2)
    day_low = round(float(df_intra['Low'].min()), 2)

    return {
        "isin": isin,
        "name": name,
        "ticker": ticker,
        "price": round(current_price, 2),
        "change": change_pct,
        "trend": "up" if change_pct >= 0 else "down",
        "labels": labels,
        "dataseries": [round(float(v), 2) for v in df_intra['Close']],
        "highSeries": [round(float(v), 2) for v in df_intra['High']],
        "lowSeries": [round(float(v), 2) for v in df_intra['Low']],
        "openSeries": [round(float(v), 2) for v in df_intra['Open']],
        "vwapSeries": [round(float(v), 2) for v in df_intra['VWAP']],
        "volumeSeries": [int(v) for v in df_intra.get('Volume', pd.Series([0]*len(df_intra))).fillna(0)],
        "dayOpen": day_open,
        "dayHigh": day_high,
        "dayLow": day_low,
        "high52": high52,
        "low52": low52,
        **ai
    }



@app.get("/api/scan")
def scan_assets():
    """Scan all assets - returns price + basic AI signal."""
    tickers = [v[1] for v in ASSET_MAPPING.values()]
    isin_by_ticker = {v[1]: k for k, v in ASSET_MAPPING.items()}
    name_by_ticker = {v[1]: v[0] for k, v in ASSET_MAPPING.items()}

    data = yf.download(
        tickers, period="5d", interval="1d",
        group_by='ticker', threads=True, progress=False
    )

    results = []
    for ticker in tickers:
        try:
            df_t = data[ticker] if len(tickers) > 1 else data
            df_t = df_t.dropna(subset=['Close'])
            if len(df_t) < 2:
                continue

            cp = float(df_t['Close'].iloc[-1])
            pc = float(df_t['Close'].iloc[-2])
            pct = round((cp - pc) / pc * 100, 2)

            ai_status = "GARDER"
            rsi_val = None
            try:
                df_long = yf.Ticker(ticker).history(period="3mo", interval="1d")
                if len(df_long) > 20:
                    rsi_val = float(ta.momentum.RSIIndicator(close=df_long['Close'], window=14).rsi().iloc[-1])
                    if rsi_val < 35: ai_status = "ACHETER FORT"
                    elif rsi_val < 45: ai_status = "ACHETER"
                    elif rsi_val > 70: ai_status = "VENDRE"
            except Exception:
                pass

            results.append({
                "isin": isin_by_ticker[ticker],
                "name": name_by_ticker[ticker],
                "price": round(cp, 2),
                "change": pct,
                "trend": "up" if pct >= 0 else "down",
                "ai_status": ai_status,
                "rsi": round(rsi_val, 1) if rsi_val is not None else None,
            })
        except Exception as e:
            print(f"Skip {ticker}: {e}")

    results.sort(key=lambda x: abs(x['change']), reverse=True)
    return results


@app.get("/api/opportunities")
def get_opportunities():
    """
    Automatic opportunity detection engine.
    Scores each asset 0-100 using multi-factor analysis:
    - RSI oversold zone (< 40)
    - Price near 52-week low (bottom fishing)
    - MACD bullish cross
    - Recent high volume (institutional accumulation signal)
    - Strong positive bounce after a drop
    """
    results = []

    for isin, (name, ticker) in ASSET_MAPPING.items():
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo", interval="1d")
            if len(df) < 30:
                continue

            current_price = float(df['Close'].iloc[-1])
            prev_close = float(df['Close'].iloc[-2])
            change_pct = round((current_price - prev_close) / prev_close * 100, 2)

            # ---- INDICATORS ----
            rsi = float(ta.momentum.RSIIndicator(close=df['Close'], window=14).rsi().iloc[-1])

            macd_ind = ta.trend.MACD(close=df['Close'])
            macd_val = float(macd_ind.macd().iloc[-1])
            macd_sig = float(macd_ind.macd_signal().iloc[-1])
            macd_hist = macd_val - macd_sig

            # 52-week range
            high_52 = float(df['High'].max())
            low_52 = float(df['Low'].min())
            range_52 = high_52 - low_52
            pct_from_low = ((current_price - low_52) / range_52 * 100) if range_52 > 0 else 50

            # Volume surge (today vs 20-day avg)
            vol_today = float(df['Volume'].iloc[-1])
            vol_avg = float(df['Volume'].tail(20).mean())
            vol_ratio = vol_today / vol_avg if vol_avg > 0 else 1.0

            # ---- SCORING ----
            score = 0
            reasons = []

            # RSI scoring (max 35 pts)
            if rsi < 25:
                score += 35
                reasons.append(f"RSI extrêmement survendu ({rsi:.0f})")
            elif rsi < 35:
                score += 25
                reasons.append(f"RSI survendu ({rsi:.0f})")
            elif rsi < 45:
                score += 10
                reasons.append(f"RSI en zone d'opportunité ({rsi:.0f})")

            # MACD (max 25 pts)
            if macd_hist > 0 and macd_val < 0:
                score += 25
                reasons.append("Croisement MACD haussier en territoire négatif")
            elif macd_hist > 0:
                score += 10
                reasons.append("MACD haussier")

            # Price near 52w low (max 25 pts)
            if pct_from_low < 10:
                score += 25
                reasons.append(f"Prix proche du plus bas 52 semaines ({pct_from_low:.0f}% au-dessus)")
            elif pct_from_low < 20:
                score += 15
                reasons.append(f"Prix dans la zone basse annuelle ({pct_from_low:.0f}% du creux)")

            # Volume surge (max 15 pts)
            if vol_ratio > 2.0:
                score += 15
                reasons.append(f"Volume ×{vol_ratio:.1f} (accumulation institutionnelle)")
            elif vol_ratio > 1.5:
                score += 8
                reasons.append(f"Volume ×{vol_ratio:.1f} au-dessus de la moyenne")

            score = min(score, 100)

            # Only return if score >= 20 (meaningful signal)
            if score >= 20:
                if score >= 70:
                    label = "FORTE OPPORTUNITÉ"
                elif score >= 45:
                    label = "OPPORTUNITÉ"
                else:
                    label = "À SURVEILLER"

                results.append({
                    "isin": isin,
                    "name": name,
                    "price": round(current_price, 2),
                    "change": change_pct,
                    "score": score,
                    "label": label,
                    "rsi": round(rsi, 1),
                    "reasons": reasons,
                    "high52": round(high_52, 2),
                    "low52": round(low_52, 2),
                })

        except Exception as e:
            print(f"Opportunity scan error for {ticker}: {e}")
            continue

    # Sort by opportunity score descending
    results.sort(key=lambda x: x['score'], reverse=True)
    return results

# ================= BACKGROUND PUSH NOTIFICATIONS ================= #
VAPID_PRIVATE_KEY = "qMjH3-qF-XKdxsL_rYcHlcL7CNiVJaDG526HjCqjheM"
VAPID_CLAIMS = {"sub": "mailto:admin@pea-app.com"}

class PushSubscription(BaseModel):
    endpoint: str
    keys: Dict[str, str]

@app.post("/api/subscribe")
def subscribe(sub: PushSubscription):
    subs = []
    if os.path.exists("subs.json"):
        with open("subs.json", "r") as f:
            try: subs = json.load(f)
            except: pass
    if not any(s['endpoint'] == sub.endpoint for s in subs):
        subs.append(sub.dict())
        with open("subs.json", "w") as f:
            json.dump(subs, f)
    return {"status": "ok"}

@app.post("/api/alert/sync")
def sync_alerts(alerts: List[Dict]):
    with open("alerts.json", "w") as f:
        json.dump(alerts, f)
    return {"status": "ok"}

async def run_bg_task():
    while True:
        try:
            await asyncio.sleep(60) # Vérifie toutes les minutes
            
            if not os.path.exists("alerts.json") or not os.path.exists("subs.json"):
                continue
                
            with open("alerts.json", "r") as f:
                alerts = json.load(f)
            with open("subs.json", "r") as f:
                subs = json.load(f)
                
            if not alerts or not subs:
                continue

            tickers = [v[1] for v in ASSET_MAPPING.values()]
            data = yf.download(tickers, period="5d", interval="1d", group_by='ticker', threads=True, progress=False)
            
            notifications_to_send = []
            for alert in alerts:
                if alert.get("triggered"): continue
                isin = alert['isin']
                if isin not in ASSET_MAPPING: continue
                ticker = ASSET_MAPPING[isin][1]
                name = ASSET_MAPPING[isin][0]
                try:
                    df_t = data[ticker] if len(tickers) > 1 else data
                    df_t = df_t.dropna(subset=['Close'])
                    current_price = float(df_t['Close'].iloc[-1])
                    
                    if alert['type'] == 'above' and current_price >= alert['price']:
                        notifications_to_send.append(f"Alerte : {name} a dépassé {alert['price']}€ (Actuel: {current_price:.2f}€)")
                        alert['triggered'] = True
                    elif alert['type'] == 'below' and current_price <= alert['price']:
                        notifications_to_send.append(f"Alerte : {name} est passé sous {alert['price']}€ (Actuel: {current_price:.2f}€)")
                        alert['triggered'] = True
                except: pass
                
            if notifications_to_send:
                with open("alerts.json", "w") as f:
                    json.dump(alerts, f)
                for msg in notifications_to_send:
                    for sub in subs:
                        try:
                            webpush(subscription_info=sub, data=json.dumps({"title": "Alerte PEAAI", "body": msg}), vapid_private_key=VAPID_PRIVATE_KEY, vapid_claims=VAPID_CLAIMS)
                        except Exception as e:
                            print(f"Push error: {e}")
                            
        except Exception as e:
            print("BG loop error:", e)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bg_task())

# ================= DEBUG ENDPOINT ================= #
@app.get("/api/debug/{isin}")
def debug_asset(isin: str):
    """Debug endpoint to diagnose data issues."""
    if isin not in ASSET_MAPPING:
        return {"error": "Unknown ISIN"}
    name, ticker = ASSET_MAPPING[isin]
    stock = yf.Ticker(ticker)
    result = {"ticker": ticker, "name": name}
    try:
        df5 = stock.history(period="5d", interval="5m")
        result["intra_5m_shape"] = str(df5.shape)
        result["intra_5m_cols"] = str(list(df5.columns))
        result["intra_5m_multiindex"] = isinstance(df5.columns, pd.MultiIndex)
        if not df5.empty:
            result["intra_5m_last_date"] = str(df5.index[-1])
            result["intra_5m_first_date"] = str(df5.index[0])
    except Exception as e:
        result["intra_5m_error"] = str(e)
    try:
        df15 = stock.history(period="5d", interval="15m")
        result["intra_15m_shape"] = str(df15.shape)
        result["intra_15m_multiindex"] = isinstance(df15.columns, pd.MultiIndex)
    except Exception as e:
        result["intra_15m_error"] = str(e)
    try:
        dfd = stock.history(period="10d", interval="1d")
        result["daily_shape"] = str(dfd.shape)
        result["daily_multiindex"] = isinstance(dfd.columns, pd.MultiIndex)
        if not dfd.empty:
            if isinstance(dfd.columns, pd.MultiIndex):
                dfd.columns = dfd.columns.get_level_values(0)
            result["daily_last_close"] = float(dfd['Close'].iloc[-1])
    except Exception as e:
        result["daily_error"] = str(e)
    return result

# ================= STATIC FILES (FRONTEND) ================= #
# Serve frontend files from parent directory
@app.get("/")
def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/{filename:path}")
def serve_static(filename: str):
    file_path = (FRONTEND_DIR / filename).resolve()
    # Security: ensure file is within FRONTEND_DIR
    if file_path.is_file() and str(file_path).startswith(str(FRONTEND_DIR)):
        return FileResponse(file_path)
    # Fallback to index.html for SPA routing
    return FileResponse(FRONTEND_DIR / "index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)

