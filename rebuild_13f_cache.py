"""
rebuild_13f_cache.py
--------------------
Ricostruisce inst13f_cache.pkl scaricando i 13F filing da SEC EDGAR
per le 4 istituzioni configurate in backtest_13f.TOP_INSTITUTIONS.

Eseguire una volta per preparare il segnale live (durata ~5-15 min).
Il cache e' valido 90 giorni.
"""

import sys
import os

# Assicura che il path del bot sia nel sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest_13f import build_institutional_table, TOP_INSTITUTIONS, WATCHLIST_USA

print(f"Ricostruzione cache 13F per {len(TOP_INSTITUTIONS)} istituzioni:")
for name, cik in TOP_INSTITUTIONS.items():
    print(f"  - {name} (CIK {cik})")
print()

inst_df = build_institutional_table(WATCHLIST_USA)

if inst_df.empty:
    print("ERRORE: nessun dato scaricato.")
    sys.exit(1)

n_tickers = inst_df[inst_df["n_holders"] > 0]["ticker"].nunique()
n_q = inst_df["quarter"].nunique()
n_sig = (inst_df["inst_score"] > 0).sum()

print(f"\nCache costruito:")
print(f"  Trimestri coperti:      {n_q}")
print(f"  Ticker con coverage:    {n_tickers}/{len(WATCHLIST_USA)}")
print(f"  Segnali positivi:       {n_sig}")
print(f"\nPronto per lunedi. main.py usera' automaticamente questo cache.")
