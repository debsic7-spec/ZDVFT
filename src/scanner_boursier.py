"""
Scanner de marche — Module importable + CLI
Utilise les 11 indicateurs de analyzer.py pour scanner une liste de tickers.
"""

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


# Liste des symboles par defaut
SYMBOLES = {
    "AAPL":  "Apple",
    "MSFT":  "Microsoft",
    "NVDA":  "NVIDIA",
    "GOOGL": "Alphabet",
    "META":  "Meta",
    "AMZN":  "Amazon",
    "TSLA":  "Tesla",
    "INTC":  "Intel",
    "AMD":   "AMD",
    "IWDA.AS": "iShares MSCI World (EUR)",
    "CSPX.AS": "iShares S&P 500 (EUR)",
    "EEM":     "iShares MSCI Emerging Markets",
    "LQQ.PA":  "Lyxor Nasdaq 100 (EUR)",
    "SX5T.DE": "EURO STOXX 50 (DE)",
    "XLK":   "SPDR Tech Sector",
    "XLF":   "SPDR Financial Sector",
    "GLD":   "SPDR Gold Trust",
    "TLT":   "iShares 20+ Year Treasury",
}


def scan_single(ticker: str, name: str):
    """Analyse un ticker avec les 11 indicateurs. Retourne un dict ou None si erreur."""
    try:
        from data_fetcher import fetch_stock_data
        from analyzer import analyze_stock
        df = fetch_stock_data(ticker, period="3mo", interval="1d")
        if df is None or len(df) < 26:
            return None
        result = analyze_stock(df)
        return {
            "ticker": ticker,
            "name": name,
            "signal": result.signal.value,
            "score": result.score,
            "confidence": result.confidence,
            "price": result.price,
            "rsi": result.rsi,
            "prediction_5j": result.prediction.objectif_5j if result.prediction else None,
            "variation_5j_pct": result.prediction.variation_5j_pct if result.prediction else None,
        }
    except Exception as e:
        return {"ticker": ticker, "name": name, "error": str(e)}


def scan_market(symbols: dict = None, max_workers: int = 4) -> list:
    """
    Scanne une liste de tickers en parallele avec les 11 indicateurs IA.

    Args:
        symbols: dict {ticker: name}. Utilise SYMBOLES par defaut.
        max_workers: nombre de threads paralleles.

    Returns:
        Liste de dicts avec resultats d'analyse, triee par score decroissant.
    """
    if symbols is None:
        symbols = SYMBOLES

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(scan_single, t, n): t for t, n in symbols.items()}
        for fut in as_completed(futures):
            r = fut.result()
            if r and "error" not in r:
                results.append(r)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def main():
    """CLI: affiche les resultats du scan dans le terminal."""
    print("\n" + "=" * 60)
    print("  SCANNER DE MARCHE — 11 Indicateurs IA")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60)
    print(f"\n  Analyse de {len(SYMBOLES)} instruments...\n")

    results = scan_market()

    if results:
        # Signaux d'achat
        achats = [r for r in results if r["score"] >= 12]
        ventes = [r for r in results if r["score"] <= -12]
        neutres = [r for r in results if -12 < r["score"] < 12]

        if achats:
            print(f"\n  SIGNAUX ACHAT ({len(achats)}):")
            for r in achats:
                v5 = f"{r['variation_5j_pct']:+.1f}%" if r['variation_5j_pct'] else "N/A"
                print(f"    {r['signal']:12s} | {r['ticker']:10s} | Score: {r['score']:+6.1f} | RSI: {r['rsi']:5.1f} | J+5: {v5}")

        if ventes:
            print(f"\n  SIGNAUX VENTE ({len(ventes)}):")
            for r in ventes:
                v5 = f"{r['variation_5j_pct']:+.1f}%" if r['variation_5j_pct'] else "N/A"
                print(f"    {r['signal']:12s} | {r['ticker']:10s} | Score: {r['score']:+6.1f} | RSI: {r['rsi']:5.1f} | J+5: {v5}")

        if neutres:
            print(f"\n  NEUTRES ({len(neutres)}):")
            for r in neutres:
                print(f"    {r['ticker']:10s} | Score: {r['score']:+6.1f} | RSI: {r['rsi']:5.1f}")
    else:
        print("  Aucun resultat (erreurs reseau?).")

    print("\n" + "-" * 60)
    print("  Ces signaux sont informatifs et ne constituent pas un conseil.")
    print("-" * 60 + "\n")


if __name__ == "__main__":
    main()
