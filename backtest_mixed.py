"""
backtest_mixed.py
-----------------
Bloomberg V2 — Approccio MISTO: 2 Large Cap + 1 Mid Cap per settimana.
Config ottimale: SL=2.0xATR  R:R 1:2

Confronto a 3 vie:
  A) Pure Large Cap  (Top 3 S&P500)
  B) Pure Mid Cap    (Top 3 S&P400)
  C) Mixed           (Top 2 Large + Top 1 Mid)

Usa le cache esistenti (market_data.pkl e market_data_midcap.pkl).
"""

import os
import pickle
import pandas as pd
import numpy as np
from datetime import datetime
import yfinance as yf
from analyzer import compute_indicators, score_stock

# ---------------------------------------------------------------------------
# Parametri
# ---------------------------------------------------------------------------

CAPITAL    = 20_000
TRADE_SIZE = 500
SAFETY_CAP = 52
MIN_BARS   = 26
PRE_FILTER_N = 20

BT_START = "2020-01-01"
BT_END   = "2026-04-30"

SL_MULT = 2.0
RR      = 2.0

COMMISSION_EUR = 2.0

CACHE_LARGE = os.path.join(os.path.dirname(__file__), "market_data.pkl")
CACHE_MID   = os.path.join(os.path.dirname(__file__), "market_data_midcap.pkl")


# ---------------------------------------------------------------------------
# Bloomberg V2 score
# ---------------------------------------------------------------------------

def bloomberg_enhanced_score(ind: dict) -> float:
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
# Cache loader
# ---------------------------------------------------------------------------

def load_cache(cache_file, label):
    if not os.path.exists(cache_file):
        print(f"  ERRORE: cache {label} non trovata ({cache_file})")
        return {}
    age_days = (datetime.now().timestamp() - os.path.getmtime(cache_file)) / 86400
    with open(cache_file, "rb") as f:
        data = pickle.load(f)
    print(f"  Cache {label}: {len(data)} ticker ({age_days:.1f}gg fa)")
    return data


# ---------------------------------------------------------------------------
# Selezione candidati da un dataset
# ---------------------------------------------------------------------------

def get_top_candidates(all_data, sig_date, top_n):
    """Restituisce i top_n candidati Bloomberg V2 per una data settimana."""
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
    if n:
        return "OPEN", float(future["Close"].iloc[-1]), n
    return "OPEN", entry, 0


def process_signal(ticker, ind, all_data, sig_date, category):
    entry = ind["price"]
    atr   = ind.get("atr_14") or (entry * 0.02)
    sl    = round(entry - SL_MULT * atr, 4)
    tp    = round(entry + RR * SL_MULT * atr, 4)

    future = all_data[ticker][all_data[ticker].index > sig_date]
    if future.empty:
        return None

    outcome, exit_price, bars_held = simulate_trade(future, entry, sl, tp)
    pnl_pct = (exit_price - entry) / entry * 100
    comm_pct = COMMISSION_EUR / TRADE_SIZE * 100 if outcome != "OPEN" else 0.0

    return {
        "date":      sig_date.strftime("%Y-%m-%d"),
        "year":      sig_date.year,
        "ticker":    ticker,
        "category":  category,
        "entry":     round(entry, 4),
        "sl":        round(sl, 4),
        "tp":        round(tp, 4),
        "outcome":   outcome,
        "bars_held": bars_held,
        "pnl_pct":   round(pnl_pct - comm_pct, 4),
    }


# ---------------------------------------------------------------------------
# Backtest per configurazione
# ---------------------------------------------------------------------------

def run_backtest_pure(all_data, top_n, category_label):
    """Pure strategy: top_n segnali dallo stesso dataset."""
    signal_dates = pd.date_range(BT_START, BT_END, freq="W-FRI")
    trades = []
    for sig_date in signal_dates:
        top = get_top_candidates(all_data, sig_date, top_n)
        for ticker, ind, _ in top:
            rec = process_signal(ticker, ind, all_data, sig_date, category_label)
            if rec:
                trades.append(rec)
    return pd.DataFrame(trades)


def run_backtest_mixed(data_large, data_mid, n_large=2, n_mid=1):
    """Mixed strategy: n_large da large cap + n_mid da mid cap."""
    signal_dates = pd.date_range(BT_START, BT_END, freq="W-FRI")
    trades = []
    for sig_date in signal_dates:
        top_large = get_top_candidates(data_large, sig_date, n_large)
        top_mid   = get_top_candidates(data_mid,   sig_date, n_mid)

        for ticker, ind, _ in top_large:
            rec = process_signal(ticker, ind, data_large, sig_date, "LARGE")
            if rec:
                trades.append(rec)

        for ticker, ind, _ in top_mid:
            rec = process_signal(ticker, ind, data_mid, sig_date, "MID")
            if rec:
                trades.append(rec)

    return pd.DataFrame(trades)


# ---------------------------------------------------------------------------
# Statistiche
# ---------------------------------------------------------------------------

def compute_stats(df, label):
    closed = df[df["outcome"].isin(["WIN", "LOSS", "TIMEOUT"])].copy()
    if closed.empty:
        return None

    wins     = closed[closed["outcome"] == "WIN"]
    losses   = closed[closed["outcome"] == "LOSS"]
    timeouts = closed[closed["outcome"] == "TIMEOUT"]

    wr      = len(wins) / len(closed) * 100
    avg_win = wins["pnl_pct"].mean() if not wins.empty else 0
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
            curr += 1
            max_cl = max(max_cl, curr)
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
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    SEP  = "=" * 96
    SEP2 = "-" * 92

    print(SEP)
    print("  BLOOMBERG V2 — MIXED 2 LARGE + 1 MID  vs  Pure Large  vs  Pure Mid")
    print(f"  SL={SL_MULT}xATR  R:R 1:{int(RR)}  |  2020-2026 (6.33 anni)")
    print(f"  Capitale {CAPITAL:,} EUR  |  Trade size {TRADE_SIZE} EUR  |  Tasse 26%  |  TR 2EUR RT")
    print(SEP)

    print("\nCaricamento cache...")
    data_large = load_cache(CACHE_LARGE, "Large Cap")
    data_mid   = load_cache(CACHE_MID,   "Mid Cap")

    if not data_large or not data_mid:
        print("Errore: eseguire prima backtest_midcap.py per generare le cache.")
        exit(1)

    # --- Run backtest ---
    print("\n[1/3] Pure Large Cap (Top 3)...")
    df_large = run_backtest_pure(data_large, 3, "LARGE")
    s_large  = compute_stats(df_large, "Pure Large Cap  (Top 3)")

    print("[2/3] Pure Mid Cap   (Top 3)...")
    df_mid   = run_backtest_pure(data_mid, 3, "MID")
    s_mid    = compute_stats(df_mid, "Pure Mid Cap    (Top 3)")

    print("[3/3] MIXED          (2 Large + 1 Mid)...")
    df_mix   = run_backtest_mixed(data_large, data_mid, n_large=2, n_mid=1)
    s_mix    = compute_stats(df_mix, "MIXED 2L+1M     (Top 2+1)")

    # --- Tabella comparativa ---
    print(f"\n\n{SEP}")
    print(f"  RISULTATI COMPARATIVI")
    print(SEP)

    hdr = (f"  {'Strategia':<28} {'Trade':>6} {'WR%':>6} {'AvgWIN':>8} {'AvgLSS':>8} "
           f"{'EV EUR':>8} {'AnnNet':>9} {'Ann%':>6} {'MaxDD':>7} {'MaxSL-':>7} {'AvgWks':>7}")
    print(hdr)
    print(f"  {SEP2}")

    for s in [s_large, s_mid, s_mix]:
        if not s:
            continue
        marker = "  <-- MIXED" if "MIXED" in s["label"] else ""
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

    # --- Dettaglio annuale MIXED ---
    print(f"\n  Dettaglio annuale — {s_mix['label']}")
    print(f"  {'Anno':<6} {'PnL lordo':>12} {'Tasse 26%':>12} {'PnL netto':>12}  "
          f"{'Large annuo':>12}  {'Mid annuo':>12}")
    print(f"  {'-'*72}")

    # PnL annuale per categoria nel mixed
    mix_by_cat = {}
    mix_closed = df_mix[df_mix["outcome"].isin(["WIN", "LOSS", "TIMEOUT"])]
    for _, row in mix_closed.iterrows():
        yr  = int(row["year"])
        cat = row["category"]
        pnl = row["pnl_pct"] / 100 * TRADE_SIZE
        mix_by_cat.setdefault(yr, {"LARGE": 0, "MID": 0})
        mix_by_cat[yr][cat] = mix_by_cat[yr].get(cat, 0) + pnl

    total_gross = 0
    for yr in sorted(s_mix["yearly"].keys()):
        gross = s_mix["yearly"][yr]
        tax   = max(0, gross * 0.26)
        net   = gross - tax
        total_gross += gross
        lg = mix_by_cat.get(yr, {}).get("LARGE", 0)
        md = mix_by_cat.get(yr, {}).get("MID", 0)
        print(f"  {yr:<6} {gross:>+11.0f}E {-tax:>+11.0f}E {net:>+11.0f}E  "
              f"{lg:>+11.0f}E  {md:>+11.0f}E")

    total_tax = max(0, total_gross * 0.26)
    print(f"  {'-'*72}")
    print(f"  {'TOT':<6} {total_gross:>+11.0f}E {-total_tax:>+11.0f}E "
          f"{total_gross-total_tax:>+11.0f}E")
    print(f"  {'ANNUO':<6} {total_gross/6.33:>+11.0f}E {'':>12} "
          f"{(total_gross-total_tax)/6.33:>+11.0f}E")
    print(SEP)

    # --- Distribuzione PnL ---
    print(f"\n  DISTRIBUZIONE PnL% per trade")
    print(f"  {'-'*72}")
    for label, df in [("Pure Large", df_large), ("Pure Mid", df_mid), ("MIXED 2L+1M", df_mix)]:
        closed = df[df["outcome"].isin(["WIN", "LOSS", "TIMEOUT"])]
        p = closed["pnl_pct"]
        print(f"  {label:<14} "
              f"P10={np.percentile(p,10):+5.1f}%  "
              f"P25={np.percentile(p,25):+5.1f}%  "
              f"Med={np.percentile(p,50):+5.1f}%  "
              f"P75={np.percentile(p,75):+5.1f}%  "
              f"P90={np.percentile(p,90):+5.1f}%  "
              f"Std={p.std():5.2f}%  "
              f"MaxDD={s_large['max_dd'] if 'Large' in label else s_mid['max_dd'] if 'Mid' in label else s_mix['max_dd']:.1f}%")
    print(SEP)

    # Salva
    df_mix.to_csv(os.path.join(os.path.dirname(__file__), "backtest_mixed_trades.csv"), index=False)
    print("\nRisultati salvati in: backtest_mixed_trades.csv")
    print(SEP)
