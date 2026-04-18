"""Test du moteur de prediction intraday 5 min."""
import sys, os
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_here), "src"))

from data_fetcher import fetch_stock_data, fetch_intraday_data
from analyzer import analyze_stock, predict_intraday

ticker = "FR0013341781"  # 2CRSI

# Donnees daily pour contexte
print("=== Fetch donnees daily ===")
df_daily = fetch_stock_data(ticker, period="3mo", interval="1d")
price_d = df_daily["Close"].iloc[-1]
print(f"Daily: {len(df_daily)} jours, dernier prix: {price_d:.2f} EUR")

# Donnees intraday 5 min
print("\n=== Fetch donnees intraday 5min ===")
try:
    df_intra = fetch_intraday_data(ticker)
    print(f"Intraday: {len(df_intra)} bougies de 5 min")
    print(f"Derniere bougie: {df_intra.index[-1]}")
    print(f"Prix actuel: {df_intra['Close'].iloc[-1]:.4f} EUR")
except Exception as e:
    print(f"Pas de donnees intraday (marche ferme?): {e}")
    print("-> Utilisation des donnees daily en mode 1h comme fallback")
    df_intra = fetch_stock_data(ticker, period="5d", interval="1h")
    print(f"Hourly fallback: {len(df_intra)} bougies")

# Prediction intraday
print("\n" + "=" * 55)
print("  PREDICTION INTRADAY - SCALPING 5 MIN")
print("=" * 55)
pred = predict_intraday(df_intra, df_daily)

print(f"\n  Direction:  {pred.direction} (force: {pred.force}/100)")
print(f"  Signal:     {pred.signal_scalping}")
print(f"  Confiance:  {pred.confiance}%")

print(f"\n  Objectifs:")
print(f"    5 min:  {pred.objectif_5min:.4f} EUR ({pred.variation_5min_pct:+.4f}%)")
print(f"   15 min:  {pred.objectif_15min:.4f} EUR ({pred.variation_15min_pct:+.4f}%)")
print(f"   30 min:  {pred.objectif_30min:.4f} EUR ({pred.variation_30min_pct:+.4f}%)")

print(f"\n  Stop-Loss:   {pred.stop_loss:.4f} EUR")
print(f"  Take-Profit: {pred.take_profit:.4f} EUR")

print(f"\n  Details par intervalle:")
for i, m in enumerate(pred.intervals):
    print(f"    {m:2d}min: {pred.prix_bas[i]:.4f} < [{pred.prix_predit[i]:.4f}] < {pred.prix_haut[i]:.4f}")

print(f"\n  Raisons ({len(pred.raisons)}):")
for r in pred.raisons:
    print(f"    -> {r}")

# Aussi tester l'analyse daily complete
print("\n" + "=" * 55)
print("  ANALYSE DAILY COMPLETE")
print("=" * 55)
result = analyze_stock(df_daily)
print(f"\n  Signal: {result.signal.value} | Score: {result.score:+.1f}")
print(f"  Prix: {result.price} | RSI: {result.rsi}")
print(f"  Prediction J+5: {result.prediction.objectif_5j:.2f} ({result.prediction.variation_5j_pct:+.1f}%)")
print(f"  Prediction J+20: {result.prediction.objectif_20j:.2f} ({result.prediction.variation_20j_pct:+.1f}%)")

print("\n  [OK] Test intraday complet!")
