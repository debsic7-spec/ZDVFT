import time
import sys
sys.path.insert(0, ".")
start = time.time()
from server import _build_asset_data
try:
    result = _build_asset_data("FR0013341781", "1d")
    elapsed = time.time() - start
    print(f"Temps: {elapsed:.1f}s")
    print(f"Prix: {result.get('price')} High52: {result.get('high52')} Low52: {result.get('low52')}")
    print(f"DayHigh: {result.get('dayHigh')} DayLow: {result.get('dayLow')} DayOpen: {result.get('dayOpen')}")
    print(f"Points: {len(result.get('dataseries', []))}")
    print(f"AI: {result.get('ai_status')}")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("ERROR:", e)
