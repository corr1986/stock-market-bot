"""
ibkr_open_signals.py
--------------------
Apre le 3 posizioni pending dal portfolio.json su IBKR paper.
Segnali: DXCM, ZM, D (2026-05-25)
SL = 1.5 x ATR  |  TP = 4.0 x SL  |  Trade size = 25.000 EUR
"""
import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import yfinance as yf
from ibkr_executor import place_orders

# Dati dal portfolio.json (entry_price calcolata live dall'executor)
PENDING = [
    {"ticker": "DXCM", "atr": 5.51},
    {"ticker": "ZM",   "atr": 8.64},
    {"ticker": "D",    "atr": 3.08},
]

SL_MULT = 2.0   # Bloomberg V2
RR      = 2.0   # Bloomberg V2

def build_signals():
    signals = []
    for p in PENDING:
        ticker = p["ticker"]
        atr    = p["atr"]
        try:
            hist = yf.Ticker(ticker).history(period="1d", interval="1m")
            entry = float(hist["Close"].iloc[-1]) if not hist.empty else None
        except Exception:
            entry = None

        if not entry:
            print(f"WARN: prezzo non disponibile per {ticker}, saltato")
            continue

        sl = round(entry - SL_MULT * atr, 4)
        tp = round(entry + RR * SL_MULT * atr, 4)

        print(f"  {ticker}: entry={entry:.4f}  SL={sl:.4f}  TP={tp:.4f}  ATR={atr}")
        signals.append({
            "ticker":      ticker,
            "entry_price": entry,
            "sl":          sl,
            "tp":          tp,
            "atr":         atr,
            "score":       0,
            "bl_score":    0,
            "category":    "USA",
        })
    return signals

if __name__ == "__main__":
    print("=== IBKR: apertura segnali Bloomberg V2 ===\n")
    signals = build_signals()
    if not signals:
        print("Nessun segnale da aprire.")
    else:
        print(f"\nPiazzo {len(signals)} ordini su IBKR paper...\n")
        results = place_orders(signals)
        print("\n=== RISULTATI ===")
        for r in results:
            print(f"  {r['ticker']}: {r['status']}  {r.get('qty', r.get('msg',''))}")
