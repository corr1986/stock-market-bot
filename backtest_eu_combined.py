"""
backtest_eu_combined.py
-----------------------
Confronto Bloomberg V2 ottimale (SL=2.0xATR, R:R 1:2):
  A) S&P500 Large Cap 247  (cache esistente market_data.pkl)  ← riferimento
  B) USA 150 + EU 100 TR   (download + cache market_data_tr_combined.pkl)

Top 3 segnali/settimana, 2020-2026 (6.33 anni).
"""

import os
import pickle
import pandas as pd
import numpy as np
from datetime import datetime
import yfinance as yf
from analyzer import compute_indicators, score_stock
from config import WATCHLIST_USA, WATCHLIST_EUROPE

# ---------------------------------------------------------------------------
# Parametri
# ---------------------------------------------------------------------------

CAPITAL      = 20_000
TRADE_SIZE   = 500
SAFETY_CAP   = 52
MIN_BARS     = 26
PRE_FILTER_N = 20
TOP_N        = 3

BT_START = "2020-01-01"
BT_END   = "2026-04-30"

SL_MULT        = 2.0
RR             = 2.0
COMMISSION_EUR = 2.0

CACHE_SP500   = os.path.join(os.path.dirname(__file__), "market_data.pkl")
CACHE_TR_COMB = os.path.join(os.path.dirname(__file__), "market_data_tr_combined.pkl")

TICKERS_TR = list(dict.fromkeys(WATCHLIST_USA + WATCHLIST_EUROPE))  # 150+100, no duplicati


# ---------------------------------------------------------------------------
# Bloomberg V2 score
# ---------------------------------------------------------------------------

def bloomberg_enhanced_score(ind: dict) -> float:
    from analyzer import score_stock
    base   = score_stock(ind)
    rsi    = ind.get("rsi_14") or 0
    vol    = ind.get("volume_ratio") or 0
    change = ind.get("weekly_change_pct") or 0
    sma50  = ind.get("above_sma50") or False

    bonus = 0.0
    if vol >= 1.5:       bonus += 2.0
    elif vol >= 1.2:     bonus += 0.5
    if 50 <= rsi <= 62:  bonus += 1.5
    elif 48 <= rsi < 50: bonus += 0.5
    elif rsi > 65:       bonus -= 2.0
    if change >= 2.0:    bonus += 1.5
    elif change >= 1.0:  bonus += 0.5
    if sma50:            bonus += 1.0

    return base + bonus


# ---------------------------------------------------------------------------
# Download e cache
# ---------------------------------------------------------------------------

def load_cache(path: str, label: str) -> dict:
    if not os.path.exists(path):
        return {}
    age = (datetime.now().timestamp() - os.path.getmtime(path)) / 86400
    with open(path, "rb") as f:
        data = pickle.load(f)
    print(f"  Cache {label}: {len(data)} ticker ({age:.1f}gg fa)")
    return data


def download_tickers(tickers: list, label: str, cache_path: str) -> dict:
    """Scarica dati weekly per la lista tickers, con cache."""
    cached = load_cache(cache_path, label)
    if cached:
        return cached

    print(f"Download dati WEEKLY {label} ({len(tickers)} ticker)...")
    data = {}
    for i, ticker in enumerate(tickers, 1):
        print(f"  {i}/{len(tickers)}: {ticker:<12}", end="", flush=True)
        try:
            df = yf.download(
                ticker,
                start="2019-01-01",
                end="2026-05-01",
                interval="1wk",
                progress=False,
                auto_adjust=True,
            )
            if df.empty or len(df) < MIN_BARS:
                print("skip")
                continue
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
            if len(df) >= MIN_BARS:
                data[ticker] = df
                print("ok")
            else:
                print("short")
        except Exception as e:
            print(f"ERR: {e}")

    print(f"Scaricati: {len(data)}/{len(tickers)}")
    with open(cache_path, "wb") as f:
        pickle.dump(data, f)
    print(f"Cache salvata: {cache_path}")
    return data


# ---------------------------------------------------------------------------
# Selezione candidati
# ---------------------------------------------------------------------------

def get_top_candidates(all_data: dict, sig_date, top_n: int) -> list:
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
    top20 = candidates[:PRE_FILTER_N]
    final = sorted(top20, key=lambda x: bloomberg_enhanced_score(x[1]), reverse=True)
    return final[:top_n]


# ---------------------------------------------------------------------------
# Simulazione trade
# ---------------------------------------------------------------------------

def simulate_trade(future, entry, sl, tp):
    for i, (_, row) in enumerate(future.iterrows()):
        if i >= SAFETY_CAP:
            return "TIMEOUT", float(future["Close"].iloc[i - 1]), i
        if float(row["Low"]) <= sl:
            return "LOSS", sl, i + 1
        if float(row["High"]) >= tp:
            return "WIN", tp, i + 1
    n = len(future)
    return ("OPEN", float(future["Close"].iloc[-1]), n) if n else ("OPEN", entry, 0)


def process_signal(ticker, ind, all_data, sig_date):
    entry = ind["price"]
    atr   = ind.get("atr_14") or (entry * 0.02)
    sl    = round(entry - SL_MULT * atr, 4)
    tp    = round(entry + RR * SL_MULT * atr, 4)

    future = all_data[ticker][all_data[ticker].index > sig_date]
    if future.empty:
        return None

    outcome, exit_price, bars = simulate_trade(future, entry, sl, tp)
    pnl_pct  = (exit_price - entry) / entry * 100
    comm_pct = COMMISSION_EUR / TRADE_SIZE * 100 if outcome != "OPEN" else 0.0

    return {
        "date":      sig_date.strftime("%Y-%m-%d"),
        "year":      sig_date.year,
        "ticker":    ticker,
        "outcome":   outcome,
        "bars_held": bars,
        "pnl_pct":   round(pnl_pct - comm_pct, 4),
    }


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def run_backtest(all_data: dict, top_n: int = TOP_N) -> pd.DataFrame:
    signal_dates = pd.date_range(BT_START, BT_END, freq="W-FRI")
    trades = []
    for sig_date in signal_dates:
        top = get_top_candidates(all_data, sig_date, top_n)
        for ticker, ind, _ in top:
            rec = process_signal(ticker, ind, all_data, sig_date)
            if rec:
                trades.append(rec)
    return pd.DataFrame(trades)


# ---------------------------------------------------------------------------
# Statistiche
# ---------------------------------------------------------------------------

def compute_stats(df: pd.DataFrame, label: str) -> dict:
    closed = df[df["outcome"].isin(["WIN", "LOSS", "TIMEOUT"])].copy()
    if closed.empty:
        return None

    wins     = closed[closed["outcome"] == "WIN"]
    losses   = closed[closed["outcome"] == "LOSS"]
    timeouts = closed[closed["outcome"] == "TIMEOUT"]

    wr      = len(wins) / len(closed) * 100
    avg_win = wins["pnl_pct"].mean()   if not wins.empty   else 0
    avg_los = losses["pnl_pct"].mean() if not losses.empty else 0
    ev_pct  = (wr / 100) * avg_win + (1 - wr / 100) * avg_los

    total_pnl  = (closed["pnl_pct"] / 100 * TRADE_SIZE).sum()
    net_profit = total_pnl - max(0, total_pnl * 0.26)
    ann_net    = net_profit / 6.33

    # Max drawdown
    balance = CAPITAL
    min_bal = CAPITAL
    for _, row in closed.sort_values("date").iterrows():
        balance += row["pnl_pct"] / 100 * TRADE_SIZE
        min_bal  = min(min_bal, balance)
    max_dd = (CAPITAL - min_bal) / CAPITAL * 100

    # Max SL consecutivi
    max_cl = curr = 0
    for _, row in closed.sort_values("date").iterrows():
        if row["outcome"] == "LOSS":
            curr += 1; max_cl = max(max_cl, curr)
        else:
            curr = 0

    # Per anno
    yearly = {}
    for _, row in closed.sort_values("date").iterrows():
        yr = int(row["year"])
        yearly[yr] = yearly.get(yr, 0) + row["pnl_pct"] / 100 * TRADE_SIZE

    return {
        "label":        label,
        "trades":       len(closed),
        "wins":         len(wins),
        "losses":       len(losses),
        "timeouts":     len(timeouts),
        "win_rate":     round(wr, 1),
        "avg_win":      round(avg_win, 2),
        "avg_loss":     round(avg_los, 2),
        "ev_pct":       round(ev_pct, 3),
        "ev_eur":       round(ev_pct / 100 * TRADE_SIZE, 2),
        "ann_net_eur":  round(ann_net, 0),
        "ann_pct":      round(ann_net / CAPITAL * 100, 1),
        "max_dd":       round(max_dd, 1),
        "max_consec_l": max_cl,
        "avg_bars":     round(closed["bars_held"].mean(), 1),
        "yearly":       yearly,
        "pnl_series":   closed["pnl_pct"].values,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    SEP  = "=" * 96
    SEP2 = "-" * 92

    print(SEP)
    print("  BLOOMBERG V2 — S&P500 (247)  vs  USA 150 + EU 100 (combinato)")
    print(f"  SL={SL_MULT}xATR  R:R 1:{int(RR)}  |  Top {TOP_N}/sett.  |  2020-2026 (6.33 anni)")
    print(f"  Capitale {CAPITAL:,} EUR  |  Trade size {TRADE_SIZE} EUR  |  Tasse 26%  |  Comm 2EUR RT")
    print(SEP)

    # --- Caricamento dati ---
    print("\nCaricamento dati...")
    data_sp500 = load_cache(CACHE_SP500, "S&P500")
    if not data_sp500:
        print("ERRORE: cache S&P500 non trovata. Esegui prima backtest.py.")
        exit(1)

    print(f"  Trade Republic combined ({len(TICKERS_TR)} ticker)...")
    data_tr = download_tickers(TICKERS_TR, "USA+EU TR", CACHE_TR_COMB)
    if not data_tr:
        print("ERRORE: download fallito.")
        exit(1)

    # --- Backtest ---
    print(f"\n[1/2] S&P500 Large Cap (247 ticker)...")
    df_sp500 = run_backtest(data_sp500, TOP_N)
    s_sp500  = compute_stats(df_sp500, f"S&P500 247          (Top {TOP_N})")

    print(f"[2/2] USA 150 + EU 100 combinato ({len(data_tr)} ticker disponibili)...")
    df_tr    = run_backtest(data_tr, TOP_N)
    s_tr     = compute_stats(df_tr, f"USA+EU TR combined  (Top {TOP_N})")

    # --- Tabella comparativa ---
    print(f"\n\n{SEP}")
    print("  RISULTATI COMPARATIVI")
    print(SEP)
    hdr = (f"  {'Strategia':<28} {'Trade':>6} {'WR%':>6} {'AvgWIN':>8} {'AvgLSS':>8} "
           f"{'EV EUR':>8} {'AnnNet':>9} {'Ann%':>6} {'MaxDD':>7} {'MaxSL-':>7} {'AvgWks':>7}")
    print(hdr)
    print(f"  {SEP2}")

    for s in [s_sp500, s_tr]:
        if not s:
            continue
        marker = "  <-- COMBINATO" if "TR" in s["label"] else ""
        print(
            f"  {s['label']:<28} "
            f"{s['trades']:>6} "
            f"{s['win_rate']:>5.1f}% "
            f"{s['avg_win']:>+7.1f}% "
            f"{s['avg_loss']:>+7.1f}% "
            f"{s['ev_eur']:>+8.2f} "
            f"{s['ann_net_eur']:>+8.0f}E "
            f"{s['ann_pct']:>+5.1f}% "
            f"{s['max_dd']:>+6.1f}% "
            f"{s['max_consec_l']:>7} "
            f"{s['avg_bars']:>7.1f}"
            f"{marker}"
        )

    print(f"  {SEP2}")
    print(SEP)

    # --- Dettaglio annuale ---
    for s, df in [(s_sp500, df_sp500), (s_tr, df_tr)]:
        if not s:
            continue
        print(f"\n  Dettaglio annuale — {s['label'].strip()}")
        print(f"  {'Anno':<6} {'PnL lordo':>12} {'Tasse 26%':>12} {'PnL netto':>12}")
        print(f"  {'-'*46}")
        total = 0
        for yr in sorted(s["yearly"].keys()):
            gross = s["yearly"][yr]
            tax   = max(0, gross * 0.26)
            total += gross
            print(f"  {yr:<6} {gross:>+11.0f}E {-tax:>+11.0f}E {gross-tax:>+11.0f}E")
        tax_tot = max(0, total * 0.26)
        print(f"  {'-'*46}")
        print(f"  {'TOT':<6} {total:>+11.0f}E {-tax_tot:>+11.0f}E {total-tax_tot:>+11.0f}E")
        print(f"  {'ANNUO':<6} {total/6.33:>+11.0f}E {'':>12} {(total-tax_tot)/6.33:>+11.0f}E")

    print(f"\n{SEP}")
    print("  DISTRIBUZIONE PnL% per trade")
    print(f"  {'-'*72}")
    for s in [s_sp500, s_tr]:
        if not s:
            continue
        p = s["pnl_series"]
        print(f"  {s['label'][:20]:<20} "
              f"P10={np.percentile(p,10):+5.1f}%  "
              f"P25={np.percentile(p,25):+5.1f}%  "
              f"Med={np.percentile(p,50):+5.1f}%  "
              f"P75={np.percentile(p,75):+5.1f}%  "
              f"P90={np.percentile(p,90):+5.1f}%  "
              f"Std={p.std():5.2f}%  "
              f"MaxDD={s['max_dd']:.1f}%")
    print(SEP)

    # --- Salva ---
    df_tr.to_csv(
        os.path.join(os.path.dirname(__file__), "backtest_eu_combined_trades.csv"),
        index=False
    )
    print("\nRisultati salvati in: backtest_eu_combined_trades.csv")
    print(SEP)
