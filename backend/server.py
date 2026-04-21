import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from pywebpush import webpush, WebPushException
import yfinance as yf
import pandas as pd
import numpy as np
import ta
from typing import Optional, List, Dict
import asyncio
import json
import os
import math
import time
from pathlib import Path
from collections import defaultdict

app = FastAPI(title="PEA Screener Tracker AI v3")

FRONTEND_DIR = Path(__file__).resolve().parent.parent

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= CONFIGURATION ================= #
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

TIMEFRAME_MAP = {
    '1d': ('5d', '5m', '%Hh%M'),
    '5d': ('5d', '15m', '%a %Hh'),
    '1mo': ('1mo', '1h', '%d/%m %Hh'),
    '6mo': ('6mo', '1d', '%d/%m'),
    '1y': ('1y', '1d', '%d/%m'),
}

# ================= CACHE ================= #
_cache: Dict[str, dict] = {}
CACHE_TTL = {'1d': 60, '5d': 120, '1mo': 300, '6mo': 600, '1y': 600}

def cache_get(key: str):
    if key in _cache:
        entry = _cache[key]
        if time.time() - entry['ts'] < entry['ttl']:
            return entry['data']
        del _cache[key]
    return None

def cache_set(key: str, data, ttl: int):
    _cache[key] = {'data': data, 'ts': time.time(), 'ttl': ttl}

# ================= RATE LIMITING ================= #
_rate_limits: Dict[str, list] = defaultdict(list)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        _rate_limits[ip] = [t for t in _rate_limits[ip] if now - t < 60]
        if len(_rate_limits[ip]) >= 60:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
        _rate_limits[ip].append(now)
    return await call_next(request)

# ================= HELPERS ================= #
def clean(v):
    f = float(v)
    return round(f, 4) if math.isfinite(f) else None

def clean2(v):
    f = float(v)
    return round(f, 2) if math.isfinite(f) else None

def clean_int(v):
    f = float(v)
    return int(f) if math.isfinite(f) else 0

def fix_columns(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

# ================= AI SIGNALS ================= #
def compute_ai_signals(df_intraday, df_long, current_price):
    result = {
        "ai_status": "GARDER", "ai_details": "Analyse insuffisante.",
        "rsi": 50.0, "macd": 0.0, "macd_signal": 0.0, "macd_hist": 0.0,
        "vwap_signal_pct": 50.0,
    }
    if len(df_long) < 30:
        return result

    rsi_series = ta.momentum.RSIIndicator(close=df_long['Close'], window=14).rsi()
    rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty and pd.notna(rsi_series.iloc[-1]) else 50.0

    macd_ind = ta.trend.MACD(close=df_long['Close'])
    macd_val = float(macd_ind.macd().iloc[-1]) if pd.notna(macd_ind.macd().iloc[-1]) else 0.0
    macd_sig = float(macd_ind.macd_signal().iloc[-1]) if pd.notna(macd_ind.macd_signal().iloc[-1]) else 0.0
    macd_hist = macd_val - macd_sig

    if 'VWAP' in df_intraday.columns and not df_intraday.empty:
        vwap_latest = float(df_intraday['VWAP'].iloc[-1])
        vwap_pct = 65.0 if current_price > vwap_latest else 35.0
    else:
        vwap_pct = 50.0

    result.update({"rsi": round(rsi, 1), "macd": round(macd_val, 4),
                    "macd_signal": round(macd_sig, 4), "macd_hist": round(macd_hist, 4),
                    "vwap_signal_pct": vwap_pct})

    signals_buy = signals_sell = 0
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
        result["ai_details"] = f"RSI survendu ({rsi:.0f}). Signal MACD haussier avec rebond VWAP."
    elif signals_sell >= 3:
        result["ai_status"] = "VENDRE"
        result["ai_details"] = f"RSI surchauffe ({rsi:.0f}). Pression baissiÃ¨re confirmÃ©e."
    elif signals_buy >= 2:
        result["ai_status"] = "ACHETER"
        result["ai_details"] = f"Configuration favorable. RSI : {rsi:.0f}, MACD positif."
    else:
        result["ai_status"] = "GARDER"
        result["ai_details"] = "Aucun signal fort. Consolidation en cours."
    return result


# ================= ASSET ENDPOINT ================= #
@app.get("/api/asset/{isin}")
def get_asset_data(isin: str, period: str = "1d", force: bool = False):
    if isin not in ASSET_MAPPING:
        raise HTTPException(status_code=404, detail="Asset not found")
    if period not in TIMEFRAME_MAP:
        period = "1d"

    cache_key = f"asset:{isin}:{period}"
    if not force:
        cached = cache_get(cache_key)
        if cached:
            return cached

    try:
        result = _build_asset_data(isin, period)
        cache_set(cache_key, result, CACHE_TTL.get(period, 60))
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


def _build_asset_data(isin: str, period: str):
    name, ticker = ASSET_MAPPING[isin]
    stock = yf.Ticker(ticker)
    yf_period, yf_interval, label_fmt = TIMEFRAME_MAP[period]

    # 1y daily for 52w range + long indicators
    df_long = fix_columns(stock.history(period="1y", interval="1d"))
    if df_long.empty:
        raise HTTPException(status_code=400, detail="No daily data")
    high52 = round(float(df_long['High'].max()), 2)
    low52 = round(float(df_long['Low'].min()), 2)

    # Timeframe data
    df_tf = pd.DataFrame()
    try:
        df_tf = fix_columns(stock.history(period=yf_period, interval=yf_interval))
        if period == '1d' and not df_tf.empty:
            last_day = df_tf.index[-1].date()
            df_tf = df_tf[df_tf.index.date == last_day].copy()
    except Exception as e:
        print(f"TF {period} error {ticker}: {e}")

    # Prefer intraday series for the current price when available (reduces perceived delay)
    if not df_tf.empty and 'Close' in df_tf.columns:
        current_price = round(float(df_tf['Close'].iloc[-1]), 2)
        if len(df_tf) > 1:
            prev_close = float(df_tf['Close'].iloc[-2])
        else:
            prev_close = float(df_long['Close'].iloc[-2]) if len(df_long) > 1 else current_price
    else:
        current_price = round(float(df_long['Close'].iloc[-1]), 2)
        prev_close = float(df_long['Close'].iloc[-2]) if len(df_long) > 1 else current_price
    change_pct = round((current_price - prev_close) / prev_close * 100, 2) if prev_close != 0 else 0.0

    # Expose interval minutes so frontend can compute 1h forecast points
    try:
        if yf_interval.endswith('m'):
            interval_minutes = int(yf_interval[:-1])
        elif yf_interval.endswith('h'):
            interval_minutes = int(yf_interval[:-1]) * 60
        elif yf_interval.endswith('d'):
            interval_minutes = 1440
        else:
            interval_minutes = 0
    except Exception:
        interval_minutes = 0

    if df_tf.empty or len(df_tf) < 2:
        df_tf = df_long.tail(30).copy()
        label_fmt = '%d/%m'

    # VWAP (intraday only)
    if period in ('1d', '5d') and 'Volume' in df_tf.columns and df_tf['Volume'].sum() > 0:
        tp = (df_tf['High'] + df_tf['Low'] + df_tf['Close']) / 3
        df_tf['VWAP'] = (tp * df_tf['Volume']).cumsum() / df_tf['Volume'].cumsum()
    else:
        df_tf['VWAP'] = df_tf['Close'].rolling(window=min(20, len(df_tf)), min_periods=1).mean()

    # SMA
    sma20 = df_tf['Close'].rolling(20, min_periods=1).mean()
    sma50 = df_tf['Close'].rolling(50, min_periods=1).mean()

    # Bollinger
    bb_sma = df_tf['Close'].rolling(20, min_periods=1).mean()
    bb_std = df_tf['Close'].rolling(20, min_periods=1).std().fillna(0)
    bb_upper = bb_sma + 2 * bb_std
    bb_lower = bb_sma - 2 * bb_std

    # RSI series
    src_rsi = df_tf['Close'] if len(df_tf) >= 30 else df_long['Close']
    rsi_full = ta.momentum.RSIIndicator(close=src_rsi, window=14).rsi()
    rsi_chart = rsi_full if len(src_rsi) == len(df_tf) else rsi_full.tail(len(df_tf))

    # MACD series
    src_macd = df_tf['Close'] if len(df_tf) >= 35 else df_long['Close']
    mi = ta.trend.MACD(close=src_macd)
    ml, ms, mh = mi.macd(), mi.macd_signal(), mi.macd_diff()
    if len(src_macd) != len(df_tf):
        ml, ms, mh = ml.tail(len(df_tf)), ms.tail(len(df_tf)), mh.tail(len(df_tf))

    ai = compute_ai_signals(df_tf, df_long, current_price)
    labels = [idx.strftime(label_fmt) for idx in df_tf.index]

    return {
        "isin": isin, "name": name, "ticker": ticker,
        "price": current_price, "change": change_pct,
        "trend": "up" if change_pct >= 0 else "down",
        "period": period,
        "labels": labels,
        "dataseries": [clean(v) for v in df_tf['Close']],
        "highSeries": [clean(v) for v in df_tf['High']],
        "lowSeries": [clean(v) for v in df_tf['Low']],
        "openSeries": [clean(v) for v in df_tf['Open']],
        "vwapSeries": [clean(v) for v in df_tf['VWAP']],
        "volumeSeries": [clean_int(v) for v in df_tf.get('Volume', pd.Series([0]*len(df_tf))).fillna(0)],
        "sma20": [clean(v) for v in sma20],
        "sma50": [clean(v) for v in sma50],
        "bbUpper": [clean(v) for v in bb_upper],
        "bbLower": [clean(v) for v in bb_lower],
        "bbMiddle": [clean(v) for v in bb_sma],
        "rsiSeries": [clean(v) for v in rsi_chart],
        "macdSeries": [clean(v) for v in ml],
        "macdSignalSeries": [clean(v) for v in ms],
        "macdHistSeries": [clean(v) for v in mh],
        "dayOpen": clean2(df_tf['Open'].iloc[0]),
        "dayHigh": clean2(df_tf['High'].max()),
        "dayLow": clean2(df_tf['Low'].min()),
        "high52": high52, "low52": low52,
        "interval_minutes": interval_minutes,
        **ai
    }


# ================= SCAN ================= #
@app.get("/api/scan")
def scan_assets(force: bool = False):
    if not force:
        cached = cache_get("scan:all")
        if cached: return cached

    tickers = [v[1] for v in ASSET_MAPPING.values()]
    isin_by_ticker = {v[1]: k for k, v in ASSET_MAPPING.items()}
    name_by_ticker = {v[1]: v[0] for k, v in ASSET_MAPPING.items()}
    data = yf.download(tickers, period="5d", interval="1d", group_by='ticker', threads=True, progress=False)

    results = []
    for ticker in tickers:
        try:
            df_t = data[ticker] if len(tickers) > 1 else data
            df_t = df_t.dropna(subset=['Close'])
            if len(df_t) < 2: continue
            cp = float(df_t['Close'].iloc[-1])
            pc = float(df_t['Close'].iloc[-2])
            pct = round((cp - pc) / pc * 100, 2)

            ai_status = "GARDER"
            rsi_val = None
            try:
                dl = yf.Ticker(ticker).history(period="3mo", interval="1d")
                if len(dl) > 20:
                    rsi_val = float(ta.momentum.RSIIndicator(close=dl['Close'], window=14).rsi().iloc[-1])
                    if rsi_val < 35: ai_status = "ACHETER FORT"
                    elif rsi_val < 45: ai_status = "ACHETER"
                    elif rsi_val > 70: ai_status = "VENDRE"
            except: pass

            results.append({
                "isin": isin_by_ticker[ticker], "name": name_by_ticker[ticker],
                "price": round(cp, 2), "change": pct,
                "trend": "up" if pct >= 0 else "down",
                "ai_status": ai_status,
                "rsi": round(rsi_val, 1) if rsi_val is not None else None,
            })
        except Exception as e:
            print(f"Skip {ticker}: {e}")

    results.sort(key=lambda x: abs(x['change']), reverse=True)
    cache_set("scan:all", results, 60)
    return results


# ================= OPPORTUNITIES ================= #
@app.get("/api/opportunities")
def get_opportunities(force: bool = False):
    if not force:
        cached = cache_get("opportunities:all")
        if cached: return cached

    results = []
    for isin, (name, ticker) in ASSET_MAPPING.items():
        try:
            df = yf.Ticker(ticker).history(period="6mo", interval="1d")
            if len(df) < 30: continue
            cp = float(df['Close'].iloc[-1])
            pc = float(df['Close'].iloc[-2])
            chg = round((cp - pc) / pc * 100, 2)

            rsi = float(ta.momentum.RSIIndicator(close=df['Close'], window=14).rsi().iloc[-1])
            mi = ta.trend.MACD(close=df['Close'])
            mh = float(mi.macd().iloc[-1]) - float(mi.macd_signal().iloc[-1])
            mv = float(mi.macd().iloc[-1])

            h52, l52 = float(df['High'].max()), float(df['Low'].min())
            r52 = h52 - l52
            pfl = ((cp - l52) / r52 * 100) if r52 > 0 else 50

            vt = float(df['Volume'].iloc[-1])
            va = float(df['Volume'].tail(20).mean())
            vr = vt / va if va > 0 else 1.0

            score, reasons = 0, []
            if rsi < 25: score += 35; reasons.append(f"RSI extrÃªmement survendu ({rsi:.0f})")
            elif rsi < 35: score += 25; reasons.append(f"RSI survendu ({rsi:.0f})")
            elif rsi < 45: score += 10; reasons.append(f"RSI zone opportunitÃ© ({rsi:.0f})")
            if mh > 0 and mv < 0: score += 25; reasons.append("Croisement MACD haussier nÃ©gatif")
            elif mh > 0: score += 10; reasons.append("MACD haussier")
            if pfl < 10: score += 25; reasons.append(f"Proche bas 52s ({pfl:.0f}%)")
            elif pfl < 20: score += 15; reasons.append(f"Zone basse annuelle ({pfl:.0f}%)")
            if vr > 2.0: score += 15; reasons.append(f"Volume Ã—{vr:.1f}")
            elif vr > 1.5: score += 8; reasons.append(f"Volume Ã—{vr:.1f}")

            score = min(score, 100)
            if score >= 20:
                label = "FORTE OPPORTUNITÃ‰" if score >= 70 else "OPPORTUNITÃ‰" if score >= 45 else "Ã€ SURVEILLER"
                results.append({"isin": isin, "name": name, "price": round(cp, 2), "change": chg,
                                "score": score, "label": label, "rsi": round(rsi, 1),
                                "reasons": reasons, "high52": round(h52, 2), "low52": round(l52, 2)})
        except Exception as e:
            print(f"Opp error {ticker}: {e}")

    results.sort(key=lambda x: x['score'], reverse=True)
    cache_set("opportunities:all", results, 300)
    return results


# ================= HEALTH + MARKET STATUS ================= #
@app.get("/api/health")
def health():
    return {"status": "ok", "cache_entries": len(_cache), "assets": len(ASSET_MAPPING)}

@app.get("/api/market-status")
def market_status():
    from datetime import datetime, timezone, timedelta
    cet = timezone(timedelta(hours=2))
    now = datetime.now(cet)
    is_open = now.weekday() < 5 and 9.0 <= (now.hour + now.minute / 60.0) <= 17.5
    return {"open": is_open, "time_cet": now.strftime("%H:%M"), "day": now.strftime("%A")}


# ================= PUSH NOTIFICATIONS ================= #
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "qMjH3-qF-XKdxsL_rYcHlcL7CNiVJaDG526HjCqjheM")
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
            await asyncio.sleep(60)
            if not os.path.exists("alerts.json") or not os.path.exists("subs.json"): continue
            with open("alerts.json") as f: alerts = json.load(f)
            with open("subs.json") as f: subs = json.load(f)
            if not alerts or not subs: continue

            tickers = [v[1] for v in ASSET_MAPPING.values()]
            data = yf.download(tickers, period="5d", interval="1d", group_by='ticker', threads=True, progress=False)
            notifs = []
            for alert in alerts:
                if alert.get("triggered"): continue
                isin = alert['isin']
                if isin not in ASSET_MAPPING: continue
                tk = ASSET_MAPPING[isin][1]; nm = ASSET_MAPPING[isin][0]
                try:
                    df_t = data[tk] if len(tickers) > 1 else data
                    df_t = df_t.dropna(subset=['Close'])
                    cp = float(df_t['Close'].iloc[-1])
                    if alert['type'] == 'above' and cp >= alert['price']:
                        notifs.append(f"{nm} > {alert['price']}â‚¬ (Act: {cp:.2f}â‚¬)"); alert['triggered'] = True
                    elif alert['type'] == 'below' and cp <= alert['price']:
                        notifs.append(f"{nm} < {alert['price']}â‚¬ (Act: {cp:.2f}â‚¬)"); alert['triggered'] = True
                except: pass
            if notifs:
                with open("alerts.json", "w") as f: json.dump(alerts, f)
                for msg in notifs:
                    for sub in subs:
                        try: webpush(subscription_info=sub, data=json.dumps({"title": "Alerte PEA", "body": msg}), vapid_private_key=VAPID_PRIVATE_KEY, vapid_claims=VAPID_CLAIMS)
                        except: pass
        except Exception as e:
            print("BG error:", e)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bg_task())

# ================= DEBUG ================= #
@app.get("/api/debug/{isin}")
def debug_asset(isin: str):
    if isin not in ASSET_MAPPING: return {"error": "Unknown"}
    name, ticker = ASSET_MAPPING[isin]
    r = {"ticker": ticker}
    try:
        d = yf.Ticker(ticker).history(period="5d", interval="5m")
        r["shape_5m"] = str(d.shape)
    except Exception as e: r["err_5m"] = str(e)
    return r

# ================= STATIC ================= #
@app.get("/")
def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/{filename:path}")
def serve_static(filename: str):
    # Don't catch API routes
    if filename.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    fp = (FRONTEND_DIR / filename).resolve()
    if fp.is_file() and str(fp).startswith(str(FRONTEND_DIR)):
        return FileResponse(fp)
    return FileResponse(FRONTEND_DIR / "index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)
