import time
import sys
sys.path.insert(0, ".")
start = time.time()
from server import _get_asset_data_impl
result = _get_asset_data_impl("FR0013341781")
elapsed = time.time() - start
print(f"Temps: {elapsed:.1f}s")
print(f"Prix: {result['price']} High52: {result['high52']} Low52: {result['low52']}")
print(f"DayHigh: {result['dayHigh']} DayLow: {result['dayLow']} DayOpen: {result['dayOpen']}")
print(f"Points: {len(result['dataseries'])}")
print(f"AI: {result['ai_status']}")
