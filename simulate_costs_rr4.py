"""
simulate_costs_rr4.py
---------------------
Impatto dei costi reali su V1 BASE vs Bloomberg V2 a R:R 4:1.

Costi modellati (da Symbol Info AAPL.xnas su FP Markets cTrader):
  - Commissione: $2/lato minimo -> $4 round-trip -> ~3.70 EUR
  - Swap long:   -8.5%/anno sul valore posizione

Confronto 4 scenari:
  1. V1 BASE         senza costi (backtest puro)
  2. V1 BASE         con costi reali
  3. Bloomberg V2    senza costi (backtest puro)
  4. Bloomberg V2    con costi reali

Ottimizzazione: salva i dati scaricati in market_data.pkl per evitare
re-download nelle run successive (cancella il file per forzare aggiornamento).

Uso:
    python simulate_costs_rr4.py
"""

import os
import pickle
import pandas as pd
import yfinance as yf
from datetime import datetime
from analyzer import compute_indicators, score_stock
from config import WATCHLIST_USA, WATCHLIST_EUROPE

# ---------------------------------------------------------------------------
# Parametri strategia
# ---------------------------------------------------------------------------

CAPITAL    = 5_000
TRADE_SIZE = 500
SL_MULT    = 1.5
RR         = 4.0
SAFETY_CAP = 52
MIN_BARS   = 26
PRE_FILTER_N = 20

BT_START = "2020-01-01"
BT_END   = "2026-04-30"

# ---------------------------------------------------------------------------
# Costi reali FP Markets (da screenshot Symbol Info AAPL.xnas, 2026-05-24)
# ---------------------------------------------------------------------------

EUR_USD        = 1.08
COMMISSION_EUR = 4.0 / EUR_USD      # $4 round-trip (~3.70 EUR)
SWAP_ANNUAL    = 0.085              # -8.5% annuo long
SWAP_WEEKLY    = SWAP_ANNUAL / 52   # per barra settimanale (~0.163%)

CACHE_FILE = os.path.join(os.path.dirname(__file__), "market_data.pkl")


# ---------------------------------------------------------------------------
# Bloomberg score
# ---------------------------------------------------------------------------

def bloomberg_enhanced_score(ind: dict) -> float:
    base   = score_stock(ind)
    rsi    = ind.get("rsi_14") or 0
    vol    = ind.get("volume_ratio") or 0
    change = ind.get("weekly_change_pct") or 0
    sma50  = ind.get("above_sma50") or False

    bonus = 0.0
    if vol >= 1.5:          bonus += 2.0
    elif vol >= 1.2:        bonus += 0.5
    if 50 <= rsi <= 62:     bonus += 1.5
    elif 48 <= rsi < 50:    bonus += 0.5
    elif rsi > 65:          bonus -= 2.0
    if change >= 2.0:       bonus += 1.5
    elif change >= 1.0:     bonus += 0.5
    if sma50:               bonus += 1.0

    return base + bonus


# ---------------------------------------------------------------------------
# Download / cache
# ---------------------------------------------------------------------------

def download_all(tickers, dl_start, dl_end):
    data = {}
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        print(f"\r  Scaricando {i}/{total}: {ticker:<14}", end="", flush=True)
        try:
            df = yf.download(
                ticker, start=dl_start, end=dl_end,
                interval="1wk", progress=False, auto_adjust=True
            )
            if not df.empty:
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                data[ticker] = df
        except Exception:
            pass
    print()
    return data


def load_or_download(tickers):
    if os.path.exists(CACHE_FILE):
        age_days = (datetime.now().timestamp() - os.path.getmtime(CACHE_FILE)) / 86400
        if age_days < 7:
            print(f"  Caricamento dati da cache ({age_days:.1f} giorni fa)...")
            with open(CACHE_FILE, "rb") as f:
                data = pickle.load(f)
            print(f"  Asset in cache: {len(data)}/{len(tickers)}\n")
            return data
        else:
            print(f"  Cache scaduta ({age_days:.1f} giorni), re-download...")

    print(f"  Download dati WEEKLY {BT_START} -> {BT_END}")
    print(f"  Ticker: {len(tickers)}")
    dl_start = "1999-01-01"
    dl_end   = datetime.today().strftime("%Y-%m-%d")
    data = download_all(tickers, dl_start, dl_end)
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(data, f)
    print(f"  Asset scaricati: {len(data)}/{len(tickers)} (salvati in cache)\n")
    return data


# ---------------------------------------------------------------------------
# Simulazione trade — restituisce anche bars_held
# ---------------------------------------------------------------------------

def simulate_trade(future, entry, sl, tp):
    """Restituisce (outcome, exit_price, bars_held)."""
    for i, (_, row) in enumerate(future.iterrows()):
        if i >= SAFETY_CAP:
            return "TIMEOUT", float(future["Close"].iloc[i - 1]), i
        if float(row["Low"]) <= sl:
            return "LOSS", sl, i + 1
        if float(row["High"]) >= tp:
            return "WIN", tp, i + 1
    n = len(future)
    if n:
        return "OPEN", float(future["Close"].iloc[-1]), n
    return "OPEN", entry, 0


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def run_backtest(all_data, mode="v1", top_n=3, apply_costs=False):
    signal_dates = pd.date_range(BT_START, BT_END, freq="W-FRI")
    trades = []

    for sig_date in signal_dates:
        candidates = []

        for ticker, df in all_data.items():
            hist = df[df.index <= sig_date].tail(200)
            if len(hist) < MIN_BARS:
                continue
            try:
                ind   = compute_indicators(hist)
                score = score_stock(ind)
                if not (score > 0 and (ind.get("macd_hist") or 0) > 0):
                    continue
                candidates.append((ticker, ind, score))
            except Exception:
                continue

        candidates.sort(key=lambda x: x[2], reverse=True)

        if mode == "bloomberg_v2":
            top20 = candidates[:PRE_FILTER_N]
            final = sorted(top20, key=lambda x: bloomberg_enhanced_score(x[1]), reverse=True)
        else:
            final = candidates

        for ticker, ind, _ in final[:top_n]:
            entry = ind["price"]
            atr   = ind.get("atr_14") or (entry * 0.02)
            sl    = round(entry - SL_MULT * atr, 4)
            tp    = round(entry + RR * SL_MULT * atr, 4)

            future = all_data[ticker][all_data[ticker].index > sig_date]
            if future.empty:
                continue

            outcome, exit_price, bars_held = simulate_trade(future, entry, sl, tp)
            pnl_pct = (exit_price - entry) / entry * 100

            # Costi reali
            commission_pct = 0.0
            swap_pct       = 0.0
            if apply_costs and outcome != "OPEN":
                commission_pct = COMMISSION_EUR / TRADE_SIZE * 100
                swap_pct       = bars_held * SWAP_WEEKLY * 100

            trades.append({
                "date":           sig_date.strftime("%Y-%m-%d"),
                "year":           sig_date.year,
                "ticker":         ticker,
                "mode":           mode,
                "apply_costs":    apply_costs,
                "entry":          round(entry, 4),
                "sl_pct":         round((entry - sl) / entry * 100, 2),
                "tp_pct":         round((tp - entry) / entry * 100, 2),
                "outcome":        outcome,
                "bars_held":      bars_held,
                "pnl_pct_gross":  round(pnl_pct, 4),
                "commission_pct": round(commission_pct, 4),
                "swap_pct":       round(swap_pct, 4),
                "pnl_pct":        round(pnl_pct - commission_pct - swap_pct, 4),
            })

    return pd.DataFrame(trades)


# ---------------------------------------------------------------------------
# Statistiche
# ---------------------------------------------------------------------------

def compute_stats(df):
    closed = df[df["outcome"].isin(["WIN", "LOSS", "TIMEOUT"])].copy()
    if closed.empty:
        return {}

    wins    = closed[closed["outcome"] == "WIN"]
    losses  = closed[closed["outcome"] == "LOSS"]

    balance      = CAPITAL
    total_profit = 0.0
    min_balance  = CAPITAL
    yearly       = {}
    max_cl = curr = 0

    for _, row in closed.sort_values("date").iterrows():
        pnl_eur  = row["pnl_pct"] / 100 * TRADE_SIZE
        balance += pnl_eur
        min_balance = min(min_balance, balance)

        if balance > CAPITAL:
            withdrawn     = balance - CAPITAL
            total_profit += withdrawn
            yr = int(row["year"])
            yearly[yr]   = yearly.get(yr, 0) + withdrawn
            balance       = CAPITAL

        if row["outcome"] == "LOSS":
            curr += 1
            max_cl = max(max_cl, curr)
        else:
            curr = 0

    avg_bars = closed["bars_held"].mean() if "bars_held" in closed.columns else 0
    total_comm = (closed["commission_pct"] * TRADE_SIZE / 100).sum() if "commission_pct" in closed.columns else 0
    total_swap = (closed["swap_pct"]       * TRADE_SIZE / 100).sum() if "swap_pct"       in closed.columns else 0

    return {
        "total_trades": len(closed),
        "wins":         len(wins),
        "losses":       len(losses),
        "timeouts":     (closed["outcome"] == "TIMEOUT").sum(),
        "win_rate":     len(wins) / len(closed) * 100,
        "avg_pnl":      closed["pnl_pct"].mean(),
        "avg_win":      wins["pnl_pct"].mean() if not wins.empty else 0,
        "avg_loss":     losses["pnl_pct"].mean() if not losses.empty else 0,
        "total_profit": total_profit,
        "ann_profit":   total_profit / 6.33,
        "max_dd_pct":   (CAPITAL - min_balance) / CAPITAL * 100,
        "max_consec_l": max_cl,
        "yearly":       yearly,
        "avg_bars_held":round(avg_bars, 1),
        "total_commission": round(total_comm, 0),
        "total_swap":       round(total_swap, 0),
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_cost_comparison(r):
    """
    r = {
      "v1_gross":  stats,
      "v1_net":    stats,
      "bl_gross":  stats,
      "bl_net":    stats,
    }
    """
    sep  = "=" * 76
    sep2 = "-" * 72

    print(f"\n{sep}")
    print(f"  IMPATTO COSTI REALI  |  R:R 4:1  |  FP Markets cTrader")
    print(f"  Comm: $4 RT (~3.70 EUR)  |  Swap long: -8.5%/anno  |  Top 3/sett.")
    print(f"  Capitale {CAPITAL} EUR  |  Posizione {TRADE_SIZE} EUR  |  2020-2026")
    print(sep)

    print(f"\n  {'Metrica':<32} {'V1 LORDO':>10} {'V1 NETTO':>10} {'BL LORDO':>10} {'BL NETTO':>10}")
    print(f"  {sep2}")

    def row(label, keys, fmt=str):
        vals = [fmt(r[k].get(keys, "")) if isinstance(keys, str) else
                fmt(r[k][keys[0]]) for k in ["v1_gross","v1_net","bl_gross","bl_net"]]
        print(f"  {label:<32} {vals[0]:>10} {vals[1]:>10} {vals[2]:>10} {vals[3]:>10}")

    def rowf(label, key, fmtstr):
        vals = [fmtstr.format(r[k].get(key, 0)) for k in ["v1_gross","v1_net","bl_gross","bl_net"]]
        print(f"  {label:<32} {vals[0]:>10} {vals[1]:>10} {vals[2]:>10} {vals[3]:>10}")

    rowf("Trade chiusi",        "total_trades", "{:.0f}")
    rowf("WIN / LOSS",          "wins",         "{:.0f}")
    rowf("Win rate",            "win_rate",     "{:.1f}%")
    rowf("EV medio per trade",  "avg_pnl",      "{:+.2f}%")
    rowf("Media WIN",           "avg_win",      "{:+.1f}%")
    rowf("Media LOSS",          "avg_loss",     "{:+.1f}%")
    rowf("Durata media (sett)", "avg_bars_held","{:.1f}")
    print(f"  {sep2}")
    rowf("PROFITTO TOTALE",     "total_profit", "{:+.0f}EUR")
    rowf("Profitto annuo",      "ann_profit",   "{:+.0f}EUR")
    rowf("Rendimento annuo",    "ann_profit",   "{:.1f}%".replace("{:.1f}%", "{:.1f}%"))
    print(f"  {sep2}")
    rowf("Max drawdown",        "max_dd_pct",   "{:.1f}%")
    rowf("Max SL consecutivi",  "max_consec_l", "{:.0f}")
    print(f"  {sep2}")

    # Costi totali
    for label, key in [("Comm. totali (6 anni)", "v1_net"), ("Swap totali (6 anni)", "v1_net")]:
        pass  # handled below

    v1_comm  = r["v1_net"]["total_commission"]
    v1_swap  = r["v1_net"]["total_swap"]
    bl_comm  = r["bl_net"]["total_commission"]
    bl_swap  = r["bl_net"]["total_swap"]

    print(f"  {'Commissioni totali':<32} {'—':>10} {v1_comm:>+9.0f}E {'—':>10} {bl_comm:>+9.0f}E")
    print(f"  {'Swap totali':<32} {'—':>10} {v1_swap:>+9.0f}E {'—':>10} {bl_swap:>+9.0f}E")
    print(f"  {'Drag totale':<32} {'—':>10} {v1_comm+v1_swap:>+9.0f}E {'—':>10} {bl_comm+bl_swap:>+9.0f}E")
    print(sep)

    # Annuale
    all_years = set()
    for k in r:
        all_years.update(r[k]["yearly"].keys())

    print(f"\n  {'Anno':<8} {'V1 LORDO':>10} {'V1 NETTO':>10} {'BL LORDO':>10} {'BL NETTO':>10}")
    print(f"  {'-' * 50}")
    for yr in sorted(all_years):
        v = [r[k]["yearly"].get(yr, 0) for k in ["v1_gross","v1_net","bl_gross","bl_net"]]
        print(f"  {yr:<8} {v[0]:>+9.0f}E {v[1]:>+9.0f}E {v[2]:>+9.0f}E {v[3]:>+9.0f}E")
    print(sep)

    # Rendimento annuo (per stampa separata)
    v1g_ann = r["v1_gross"]["ann_profit"]
    v1n_ann = r["v1_net"]["ann_profit"]
    blg_ann = r["bl_gross"]["ann_profit"]
    bln_ann = r["bl_net"]["ann_profit"]

    print(f"\n  Rendimento annuo su 5.000 EUR:")
    print(f"  V1 LORDO   {v1g_ann/CAPITAL*100:+.1f}%/anno  ->  V1 NETTO   {v1n_ann/CAPITAL*100:+.1f}%/anno")
    print(f"  BL LORDO   {blg_ann/CAPITAL*100:+.1f}%/anno  ->  BL NETTO   {bln_ann/CAPITAL*100:+.1f}%/anno")
    print(f"\n  Rendimento annuo su 20.000 EUR (stessa posizione 500 EUR):")
    cap20 = 20_000
    print(f"  V1 LORDO   {v1g_ann/cap20*100:+.1f}%/anno  ->  V1 NETTO   {v1n_ann/cap20*100:+.1f}%/anno")
    print(f"  BL LORDO   {blg_ann/cap20*100:+.1f}%/anno  ->  BL NETTO   {bln_ann/cap20*100:+.1f}%/anno")
    print(sep)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    all_tickers = WATCHLIST_USA + WATCHLIST_EUROPE

    print("=" * 60)
    print(f"  simulate_costs_rr4.py  |  R:R {RR}:1")
    print(f"  Comm: ~{COMMISSION_EUR:.2f} EUR RT  |  Swap: {SWAP_ANNUAL*100:.1f}%/anno")
    print("=" * 60)
    print()

    all_data = load_or_download(all_tickers)

    scenarios = {
        "v1_gross": ("v1",           False),
        "v1_net":   ("v1",           True),
        "bl_gross": ("bloomberg_v2", False),
        "bl_net":   ("bloomberg_v2", True),
    }

    results = {}
    for name, (mode, costs) in scenarios.items():
        label = f"{mode.upper()} {'+ costi' if costs else '(lordo)'}"
        print(f"  Backtest {label}...")
        df = run_backtest(all_data, mode=mode, apply_costs=costs)
        df.to_csv(f"backtest_{name}_rr4.csv", index=False)
        stats = compute_stats(df)
        results[name] = stats
        print(f"    Trade chiusi: {stats['total_trades']}  "
              f"WR: {stats['win_rate']:.1f}%  "
              f"Profitto: {stats['total_profit']:+.0f}EUR  "
              f"Durata media: {stats['avg_bars_held']:.1f} sett.")

    print()
    print_cost_comparison(results)

    print("\nFile salvati:")
    for name in scenarios:
        print(f"  backtest_{name}_rr4.csv")
