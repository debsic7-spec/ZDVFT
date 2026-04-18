"""
test_rapide.py - Test rapide de toutes les fonctionnalites StockAnalyzer IA
Lance ce script pour verifier que tout marche en ~10 secondes.
Utilise plusieurs tickers en fallback si Yahoo rate-limite un symbole.
"""

import sys
import time
import os

# Ajouter le dossier src/ au path pour trouver les modules
_here = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(os.path.dirname(_here), "src")
sys.path.insert(0, _src)
os.chdir(_src)

PASS = "\033[92m[OK]\033[0m"
FAIL = "\033[91m[ECHEC]\033[0m"
total = 0
ok = 0

# Tickers de fallback : si le premier echoue (429 rate limit), on tente le suivant
FALLBACK_TICKERS = [
    ("FR0013341781", "AL2SI.PA", "2CRSI"),
    ("MC.PA",        "MC.PA",    "LVMH"),
    ("TTE.PA",       "TTE.PA",   "TotalEnergies"),
    ("AAPL",         "AAPL",     "Apple"),
    ("MSFT",         "MSFT",     "Microsoft"),
]


def test(name, func):
    global total, ok
    total += 1
    try:
        result = func()
        print(f"  {PASS} {name}")
        if result:
            print(f"       -> {result}")
        ok += 1
        return True
    except Exception as e:
        print(f"  {FAIL} {name}: {e}")
        return False


def _resolve_ticker():
    """Essaie chaque ticker en fallback jusqu'a en trouver un qui repond."""
    from data_fetcher import fetch_stock_data, isin_to_ticker
    for isin, expected_ticker, name in FALLBACK_TICKERS:
        try:
            resolved = isin_to_ticker(isin)
            df = fetch_stock_data(isin, period="3mo", interval="1d")
            if df is not None and len(df) >= 26:
                return isin, resolved, name, df
        except Exception:
            continue
    return None, None, None, None


def main():
    global total, ok
    start = time.time()
    print("=" * 55)
    print("  TEST RAPIDE - StockAnalyzer IA v2.1")
    print("=" * 55)

    # === 1. Imports ===
    print("\n[1/6] Imports...")

    test("Import analyzer", lambda: __import__('analyzer'))
    test("Import data_fetcher", lambda: __import__('data_fetcher'))
    test("Import chart_generator", lambda: __import__('chart_generator'))
    test("Import monitor", lambda: __import__('monitor'))

    # === 2. Resolution ticker (avec fallback) ===
    print("\n[2/6] Resolution ticker (fallback multi-tickers)...")

    isin_code = resolved_ticker = stock_name = None
    df = None

    def _resolve():
        nonlocal isin_code, resolved_ticker, stock_name, df
        isin_code, resolved_ticker, stock_name, df = _resolve_ticker()
        if df is None:
            raise Exception("Aucun ticker disponible (tous rate-limited)")
        return f"{isin_code} -> {resolved_ticker} ({stock_name}, {len(df)} jours)"

    test("Ticker avec fallback", _resolve)

    from data_fetcher import get_stock_name
    def _get_name():
        n = get_stock_name(isin_code)
        return n
    test(f"Nom {stock_name}", _get_name)

    # === 3. Donnees boursiere ===
    print("\n[3/6] Recuperation donnees...")

    from data_fetcher import fetch_realtime_price

    def _fetch_data():
        return f"{len(df)} jours, dernier prix: {df['Close'].iloc[-1]:.2f}"
    test(f"Fetch 3 mois {resolved_ticker}", _fetch_data)

    def _fetch_rt():
        info = fetch_realtime_price(isin_code)
        ccy = info.get('currency', '?')
        return f"Prix: {info.get('price', '?')} {ccy} | Change: {info.get('change_percent', '?')}%"
    test("Prix temps reel", _fetch_rt)

    # === 4. Analyse IA ===
    print("\n[4/6] Analyse IA...")

    from analyzer import analyze_stock
    result = None

    def _analyze():
        nonlocal result
        result = analyze_stock(df)
        return (f"Signal: {result.signal.value} | Score: {result.score:+.1f} | "
                f"Confiance: {result.confidence:.0f}% | RSI: {result.rsi:.0f}")
    test("Analyse 11 indicateurs", _analyze)

    def _check_details():
        d = result.details
        keys = ['rsi', 'macd', 'moyennes_mobiles', 'bollinger', 'stochastique', 'volume', 'tendance', 'momentum', 'adx', 'obv', 'ichimoku']
        for k in keys:
            assert k in d, f"Manque {k}"
        return f"11/11 indicateurs OK, supports: {d.get('supports', [])}"
    test("Details indicateurs", _check_details)

    # === 5. Prediction ===
    print("\n[5/6] Prediction IA...")

    def _check_pred():
        p = result.prediction
        assert p is not None, "Prediction manquante"
        assert len(p.days) == 20, f"Attendu 20 jours, got {len(p.days)}"
        assert len(p.scenario_haut) == 20, "Scenario haut manquant"
        assert len(p.scenario_bas) == 20, "Scenario bas manquant"
        assert p.pic_prix > 0, "Pic invalide"
        assert p.creux_prix > 0, "Creux invalide"
        return (f"J+5: {p.objectif_5j:.2f} ({p.variation_5j_pct:+.1f}%) | "
                f"J+10: {p.objectif_10j:.2f} | J+20: {p.objectif_20j:.2f}\n"
                f"       -> Pic: {p.pic_prix:.2f} a J+{p.pic_jour} | "
                f"Creux: {p.creux_prix:.2f} a J+{p.creux_jour} | "
                f"Tendance: {p.tendance}")
    test("Prediction 20 jours + scenarios", _check_pred)

    # === 6. Graphiques ===
    print("\n[6/6] Generation graphiques...")

    from chart_generator import (chart_prix, chart_rsi, chart_macd,
                                 chart_prediction, chart_analyse)

    def _chart(name, func):
        path = func()
        assert os.path.exists(path), f"Fichier non cree: {path}"
        size = os.path.getsize(path)
        return f"{os.path.basename(path)} ({size // 1024} KB)"

    test("Chart Prix", lambda: _chart("prix", lambda: chart_prix(df, resolved_ticker, stock_name, result)))
    test("Chart RSI", lambda: _chart("rsi", lambda: chart_rsi(df, resolved_ticker, stock_name)))
    test("Chart MACD", lambda: _chart("macd", lambda: chart_macd(df, resolved_ticker, stock_name)))
    test("Chart Prediction", lambda: _chart("pred", lambda: chart_prediction(df, result.prediction, resolved_ticker, stock_name, result)))
    test("Chart Score IA", lambda: _chart("analyse", lambda: chart_analyse(result)))

    # === Resume ===
    elapsed = time.time() - start
    print("\n" + "=" * 55)
    if ok == total:
        print(f"  {PASS} TOUS LES TESTS PASSES: {ok}/{total} en {elapsed:.1f}s")
    else:
        print(f"  {FAIL} {ok}/{total} tests passes en {elapsed:.1f}s")
        print(f"       {total - ok} test(s) en echec!")
    print("=" * 55)

    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
