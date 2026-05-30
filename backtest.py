"""
Backtest su barre DAILY, senza limite temporale.
Segnali generati ogni lunedi', verifica SL/TP su barre giornaliere successive.
Safety cap: 365 giorni lavorativi.

SL = 1.5x ATR14 daily
TP = 4.5x ATR14 daily  (R:R 3:1 -> break-even 25%)
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from analyzer import compute_indicators, score_stock
from config import WATCHLIST_USA, WATCHLIST_EUROPE, WATCHLIST_INDICES

BACKTEST_START = "2022-01-01"
BACKTEST_END   = "2024-12-31"
TOP_N          = 3
MIN_BARS       = 60        # ~3 mesi di dati daily
SL_MULT        = 1.5
RR             = 3.0
SAFETY_CAP     = 365       # giorni lavorativi massimi


# ---------------------------------------------------------------------------
# Download giornaliero
# ---------------------------------------------------------------------------

def download_all(tickers, dl_start, dl_end):
    data = {}
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        print(f"\r  {i}/{total}: {ticker:<14}", end="", flush=True)
        try:
            df = yf.download(ticker, start=dl_start, end=dl_end,
                             interval="1d", progress=False, auto_adjust=True)
            if not df.empty:
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                data[ticker] = df
        except Exception:
            pass
    print()
    return data


# ---------------------------------------------------------------------------
# Simulazione senza limite temporale (daily)
# ---------------------------------------------------------------------------

def simulate_trade(future, entry, sl, tp):
    """
    Scorre le barre giornaliere fino a SL o TP.
    Conservativo: se High e Low della stessa barra toccano entrambi, vince SL.
    """
    for i, (_, row) in enumerate(future.iterrows()):
        if i >= SAFETY_CAP:
            close = float(future["Close"].iloc[i - 1])
            return "TIMEOUT", round((close - entry) / entry * 100, 2), i
        low  = float(row["Low"])
        high = float(row["High"])
        if low <= sl:
            return "LOSS", round((sl - entry) / entry * 100, 2), i + 1
        if high >= tp:
            return "WIN",  round((tp - entry) / entry * 100, 2), i + 1
    if len(future) > 0:
        close = float(future["Close"].iloc[-1])
        return "OPEN", round((close - entry) / entry * 100, 2), len(future)
    return "OPEN", 0.0, 0


# ---------------------------------------------------------------------------
# Backtest principale — segnali ogni lunedi'
# ---------------------------------------------------------------------------

def run_backtest(all_data):
    mondays = pd.date_range(start=BACKTEST_START, end=BACKTEST_END, freq="W-MON")
    results = []

    for monday in mondays:
        candidates = []

        for ticker, df in all_data.items():
            if ticker.startswith("^"):
                continue
            hist = df[df.index <= monday]
            if len(hist) < MIN_BARS:
                continue
            try:
                ind   = compute_indicators(hist)
                score = score_stock(ind)
                if score > 0 and (ind.get("macd_hist") or 0) > 0:
                    candidates.append((ticker, ind, score))
            except Exception:
                continue

        candidates.sort(key=lambda x: x[2], reverse=True)

        for ticker, ind, _ in candidates[:TOP_N]:
            entry = ind["price"]
            atr   = ind.get("atr_14") or (entry * 0.015)
            sl    = round(entry - SL_MULT * atr, 4)
            tp    = round(entry + RR * SL_MULT * atr, 4)

            future = all_data[ticker]
            future = future[future.index > monday]
            if future.empty:
                continue

            outcome, pnl, days_held = simulate_trade(future, entry, sl, tp)

            results.append({
                "entry_date": monday.strftime("%Y-%m-%d"),
                "year":       monday.year,
                "ticker":     ticker,
                "entry":      entry,
                "sl":         sl,
                "tp":         tp,
                "atr":        round(atr, 4),
                "sl_pct":     round((entry - sl) / entry * 100, 2),
                "tp_pct":     round((tp - entry) / entry * 100, 2),
                "outcome":    outcome,
                "pnl_pct":    pnl,
                "days_held":  days_held,
            })

    return results


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(results):
    if not results:
        print("Nessun risultato.")
        return

    df = pd.DataFrame(results)
    closed = df[df["outcome"].isin(["WIN", "LOSS", "TIMEOUT"])]

    total   = len(closed)
    wins    = (closed["outcome"] == "WIN").sum()
    losses  = (closed["outcome"] == "LOSS").sum()
    timeout = (closed["outcome"] == "TIMEOUT").sum()
    open_n  = (df["outcome"] == "OPEN").sum()

    wr       = wins / total * 100 if total > 0 else 0
    ev       = closed["pnl_pct"].mean()
    avg_win  = closed[closed["outcome"] == "WIN"]["pnl_pct"].mean()
    avg_lss  = closed[closed["outcome"] == "LOSS"]["pnl_pct"].mean()
    avg_days = closed["days_held"].mean()
    pnl_tot  = (closed["pnl_pct"] / 100 * 1000).sum()

    avg_sl_pct = closed["sl_pct"].mean()
    avg_tp_pct = closed["tp_pct"].mean()

    max_cl = curr = 0
    for o in closed["outcome"]:
        if o == "LOSS":
            curr += 1
            max_cl = max(max_cl, curr)
        else:
            curr = 0

    sep = "=" * 60
    print(f"\n{sep}")
    print("  BACKTEST DAILY — no time limit — 2022-2024")
    print(f"  SL=1.5x ATR daily | TP=4.5x ATR daily | R:R 3:1")
    print(sep)
    print(f"  SL medio:                {avg_sl_pct:.1f}% sotto entry")
    print(f"  TP medio:                {avg_tp_pct:.1f}% sopra entry")
    print(sep)
    print(f"  Trade chiusi:            {total}")
    print(f"  WIN:                     {wins}  ({wr:.1f}%)")
    print(f"  LOSS:                    {losses}  ({losses/total*100:.1f}%)")
    print(f"  TIMEOUT (365gg):         {timeout}  ({timeout/total*100:.1f}%)")
    print(f"  OPEN (fine backtest):    {open_n}")
    print(sep)
    print(f"  Guadagno medio WIN:      +{avg_win:.1f}%")
    print(f"  Perdita media LOSS:       {avg_lss:.1f}%")
    print(f"  Durata media trade:      {avg_days:.0f} giorni")
    print(f"  Valore atteso (EV):      {ev:+.2f}% per trade")
    print(sep)
    print(f"  Break-even WR (R:R 3:1): 25.0%")
    flag = "OK sopra break-even" if wr >= 25.0 else "!! sotto break-even"
    print(f"  Win rate ottenuto:        {wr:.1f}%  [{flag}]")
    print(sep)
    print(f"  Max perdite consecutive: {max_cl}")
    print(f"  P&L totale (1000EUR/t):  {pnl_tot:+.0f} EUR")
    print(sep)

    print("\n  P&L per anno:")
    for year, grp in closed.groupby("year"):
        yr_wins = (grp["outcome"] == "WIN").sum()
        yr_tot  = len(grp)
        yr_wr   = yr_wins / yr_tot * 100 if yr_tot else 0
        yr_ev   = grp["pnl_pct"].mean()
        yr_pnl  = (grp["pnl_pct"] / 100 * 1000).sum()
        print(f"    {year}: {yr_tot:>3} trade | WR {yr_wr:.1f}% | EV {yr_ev:+.2f}% | P&L {yr_pnl:+.0f} EUR")

    cols = ["entry_date", "ticker", "entry", "sl_pct", "tp_pct", "outcome", "pnl_pct", "days_held"]
    print("\n  TOP 5 MIGLIORI TRADE:")
    print(closed.nlargest(5, "pnl_pct")[cols].to_string(index=False))
    print("\n  TOP 5 PEGGIORI TRADE:")
    print(closed.nsmallest(5, "pnl_pct")[cols].to_string(index=False))

    df.to_csv("backtest_results.csv", index=False)
    print(f"\n  Risultati completi -> backtest_results.csv")
    print(sep)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    all_tickers = WATCHLIST_USA + WATCHLIST_EUROPE + list(WATCHLIST_INDICES.keys())

    dl_start = (datetime.strptime(BACKTEST_START, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")
    dl_end   = (datetime.strptime(BACKTEST_END,   "%Y-%m-%d") + timedelta(days=SAFETY_CAP + 30)).strftime("%Y-%m-%d")

    print(f"Download dati daily {dl_start} -> {dl_end} per {len(all_tickers)} asset...")
    all_data = download_all(all_tickers, dl_start, dl_end)
    print(f"Asset scaricati: {len(all_data)}/{len(all_tickers)}\n")

    print("Simulazione in corso...")
    results = run_backtest(all_data)
    print(f"Trade generati: {len(results)}\n")
    print_report(results)
