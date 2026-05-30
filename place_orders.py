"""
place_orders.py
---------------
Legge signals.json (generato da main.py alle 13:30) e piazza gli ordini su IBKR.
Va eseguito a mercato aperto:
  - 14:05 Bali  -> azioni EU (XETRA, AEB, SBF, BM, LSE)
  - 21:35 Bali  -> azioni USA (SMART/USD) + eventuale EU rimasto

Task Scheduler: due task separati con questo script.
A mercato aperto i Market orders funzionano senza problemi di TIF/GTC.
"""

# Fix compatibilita Python 3.10+ con ib_insync
import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import sys
import json
import os
from datetime import datetime
from ibkr_executor import place_orders

SIGNALS_FILE = os.path.join(os.path.dirname(__file__), "signals.json")


def load_signals() -> list:
    if not os.path.exists(SIGNALS_FILE):
        print("ERRORE: signals.json non trovato. Esegui prima main.py.")
        return []
    with open(SIGNALS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    today = datetime.now().strftime("%Y-%m-%d")
    if data.get("date") != today:
        print(f"WARN: signals.json e' del {data.get('date')}, oggi e' {today}. Procedo comunque.")
    return data.get("signals", [])


EU_SUFFIXES = ('.DE', '.AS', '.PA', '.MC', '.MI', '.L')

def filter_signals(signals: list, market: str) -> list:
    if market == "EU":
        return [s for s in signals if any(s['ticker'].endswith(sfx) for sfx in EU_SUFFIXES)]
    elif market == "US":
        return [s for s in signals if not any(s['ticker'].endswith(sfx) for sfx in EU_SUFFIXES)
                and not s['ticker'].startswith('^')]
    return signals


if __name__ == "__main__":
    market = sys.argv[1].upper() if len(sys.argv) > 1 else "ALL"
    print(f"[{datetime.now().strftime('%d/%m/%Y %H:%M')}] place_orders.py avviato — mercato: {market}")

    signals = load_signals()
    if not signals:
        sys.exit(1)

    signals = filter_signals(signals, market)
    if not signals:
        print(f"Nessun segnale per mercato {market} questa settimana.")
        sys.exit(0)

    print(f"Segnali {market}: {[s['ticker'] for s in signals]}")
    results = place_orders(signals)

    ok  = [r for r in results if r["status"] == "OK"]
    skp = [r for r in results if r["status"] == "SKIP"]
    err = [r for r in results if r["status"] == "ERROR"]

    print(f"\nRiepilogo: {len(ok)} OK | {len(skp)} SKIP | {len(err)} ERRORE")
    for r in ok:
        print(f"  OK   {r['ticker']} — qty {r.get('qty')}")
    for r in skp:
        print(f"  SKIP {r['ticker']} — {r.get('msg')}")
    for r in err:
        print(f"  ERR  {r['ticker']} — {r.get('msg')}")
