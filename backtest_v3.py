"""
backtest_v3.py
--------------
Confronto Bloomberg V2 + 13F (v1 attuale) vs Bloomberg V2 + 13F + Chandelier + VIX regime + Sizing dinamico (v3)
Periodo: 2020-01-01 → 2026-04-30 (6.33 anni) — stesso dataset di backtest_13f.py

Cosa viene backtestato:
  v1: SL fisso, TP fisso, sempre attivo, 500 EUR per trade
  v3: Chandelier Exit (no TP), VIX regime filter, sizing dinamico 40 EUR rischio fisso

NON backtestabile: earnings filter (mancano dati storici), analyst consensus LLM
"""

import os
import pickle
import numpy as np
import pandas as pd
import yfinance as yf

from analyzer import compute_indicators, score_stock
from config import WATCHLIST_USA

# ---------------------------------------------------------------------------
# Parametri condivisi
# ---------------------------------------------------------------------------

CAPITAL       = 20_000
BT_START      = "2020-01-01"
BT_END        = "2026-04-30"
SL_MULT       = 2.0
SAFETY_CAP    = 52       # max settimane per trade
MIN_BARS      = 26
PRE_FILTER_N  = 20
TOP_N_BASE    = 3        # v1 sempre 3 posizioni
COMMISSION_EUR = 2.0

# v1
TRADE_SIZE_V1 = 500.0
RR_V1         = 2.0      # TP = entry + RR * SL = entry + 4xATR

# v3 sizing
RISK_TARGET   = 40.0
MAX_SIZE      = 1500.0
MIN_SIZE      = 100.0

# v3 regime
VIX_RISKOFF   = 30.0
VIX_CAUTIOUS  = 20.0

CACHE_PRICE = os.path.join(os.path.dirname(__file__), "market_data.pkl")
CACHE_13F   = os.path.join(os.path.dirname(__file__), "inst13f_cache.pkl")
CACHE_VIX   = os.path.join(os.path.dirname(__file__), "vix_cache.pkl")


# ---------------------------------------------------------------------------
# Bloomberg V2 score (identico alla produzione)
# ---------------------------------------------------------------------------

def bloomberg_enhanced_score(ind: dict, inst_bonus: float = 0.0) -> float:
    base   = score_stock(ind)
    rsi    = ind.get("rsi_14") or 0
    vol    = ind.get("volume_ratio") or 0
    change = ind.get("weekly_change_pct") or 0
    sma50  = ind.get("above_sma50") or False
    bonus  = 0.0
    if vol >= 1.5:       bonus += 2.0
    elif vol >= 1.2:     bonus += 0.5
    if 50 <= rsi <= 62:  bonus += 1.5
    elif 48 <= rsi < 50: bonus += 0.5
    elif rsi > 65:       bonus -= 2.0
    if change >= 2.0:    bonus += 1.5
    elif change >= 1.0:  bonus += 0.5
    if sma50:            bonus += 1.0
    return base + bonus + inst_bonus


# ---------------------------------------------------------------------------
# 13F inst score lookup
# ---------------------------------------------------------------------------

def get_inst_score(ticker: str, signal_date, inst_df: pd.DataFrame) -> float:
    if inst_df is None or inst_df.empty:
        return 0.0
    mask = (inst_df["ticker"] == ticker) & (inst_df["available_from"] <= signal_date)
    available = inst_df[mask]
    if available.empty:
        return 0.0
    return float(available.sort_values("quarter_end").iloc[-1]["inst_score"])


# ---------------------------------------------------------------------------
# VIX storico
# ---------------------------------------------------------------------------

def load_vix_history() -> pd.Series:
    if os.path.exists(CACHE_VIX):
        with open(CACHE_VIX, "rb") as f:
            return pickle.load(f)
    print("Scaricamento VIX storico da yfinance...")
    df = yf.download("^VIX", start="2019-01-01", end="2026-05-31",
                     interval="1wk", progress=False, auto_adjust=True)
    if df.empty:
        return pd.Series(dtype=float)
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    series = df["Close"].squeeze()
    with open(CACHE_VIX, "wb") as f:
        pickle.dump(series, f)
    return series


def get_vix_at(vix_series: pd.Series, date) -> float:
    if vix_series.empty:
        return 18.0
    available = vix_series[vix_series.index <= date]
    return float(available.iloc[-1]) if not available.empty else 18.0


def get_regime(vix: float) -> dict:
    if vix > VIX_RISKOFF:
        return {"allow": False, "max_pos": 0}
    elif vix > VIX_CAUTIOUS:
        return {"allow": True,  "max_pos": 2}
    else:
        return {"allow": True,  "max_pos": TOP_N_BASE}


# ---------------------------------------------------------------------------
# Candidati (comune a v1 e v3)
# ---------------------------------------------------------------------------

def get_top_candidates(all_data, sig_date, top_n, inst_df) -> list:
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
    final = sorted(
        top20,
        key=lambda x: bloomberg_enhanced_score(x[1], inst_bonus=get_inst_score(x[0], sig_date, inst_df)),
        reverse=True
    )
    return final[:top_n]


# ---------------------------------------------------------------------------
# Simulazione v1 — SL/TP fissi
# ---------------------------------------------------------------------------

def simulate_v1(future, entry, sl, tp):
    for i, (_, row) in enumerate(future.iterrows()):
        if i >= SAFETY_CAP:
            return "TIMEOUT", float(row["Close"]), i
        if float(row["Low"]) <= sl:
            return "LOSS", sl, i + 1
        if float(row["High"]) >= tp:
            return "WIN", tp, i + 1
    n = len(future)
    return ("OPEN", float(future["Close"].iloc[-1]), n) if n else ("OPEN", entry, 0)


def process_v1(ticker, ind, all_data, sig_date):
    entry = ind["price"]
    atr   = ind.get("atr_14") or (entry * 0.02)
    sl    = entry - SL_MULT * atr
    tp    = entry + RR_V1 * SL_MULT * atr

    future = all_data[ticker][all_data[ticker].index > sig_date]
    if future.empty:
        return None

    outcome, exit_price, bars = simulate_v1(future, entry, sl, tp)
    pnl_pct  = (exit_price - entry) / entry * 100
    comm_pct = COMMISSION_EUR / TRADE_SIZE_V1 * 100 if outcome != "OPEN" else 0.0
    return {
        "date":     sig_date.strftime("%Y-%m-%d"),
        "year":     sig_date.year,
        "ticker":   ticker,
        "outcome":  outcome,
        "bars":     bars,
        "pnl_pct":  round(pnl_pct - comm_pct, 4),
        "size_eur": TRADE_SIZE_V1,
        "pnl_eur":  round((pnl_pct - comm_pct) / 100 * TRADE_SIZE_V1, 2),
    }


# ---------------------------------------------------------------------------
# Simulazione v3 — Chandelier Exit + sizing dinamico
# ---------------------------------------------------------------------------

def dynamic_size(entry, atr) -> float:
    sl_pct = (SL_MULT * atr) / entry
    if sl_pct <= 0:
        return MIN_SIZE
    return max(MIN_SIZE, min(RISK_TARGET / sl_pct, MAX_SIZE))


def simulate_chandelier(future, entry, atr_entry, initial_sl):
    max_high = entry
    for i, (_, row) in enumerate(future.iterrows()):
        h = float(row["High"])
        l = float(row["Low"])

        if h > max_high:
            max_high = h

        chandelier = max_high - SL_MULT * atr_entry
        stop = max(chandelier, initial_sl)

        if l <= stop:
            exit_price = max(stop, l)
            return "EXIT", exit_price, i + 1

        if i >= SAFETY_CAP:
            return "TIMEOUT", float(row["Close"]), i

    n = len(future)
    return ("OPEN", float(future["Close"].iloc[-1]), n) if n else ("OPEN", entry, 0)


def process_v3(ticker, ind, all_data, sig_date):
    entry = ind["price"]
    atr   = ind.get("atr_14") or (entry * 0.02)
    sl    = entry - SL_MULT * atr
    size  = dynamic_size(entry, atr)

    future = all_data[ticker][all_data[ticker].index > sig_date]
    if future.empty:
        return None

    outcome, exit_price, bars = simulate_chandelier(future, entry, atr, sl)
    pnl_pct  = (exit_price - entry) / entry * 100
    comm_pct = COMMISSION_EUR / size * 100 if outcome != "OPEN" else 0.0
    return {
        "date":     sig_date.strftime("%Y-%m-%d"),
        "year":     sig_date.year,
        "ticker":   ticker,
        "outcome":  outcome,
        "bars":     bars,
        "pnl_pct":  round(pnl_pct - comm_pct, 4),
        "size_eur": round(size, 2),
        "pnl_eur":  round((pnl_pct - comm_pct) / 100 * size, 2),
    }


# ---------------------------------------------------------------------------
# Backtest loop
# ---------------------------------------------------------------------------

def run_backtest_v1(all_data, inst_df) -> pd.DataFrame:
    signal_dates = pd.date_range(BT_START, BT_END, freq="W-FRI")
    trades = []
    for sig_date in signal_dates:
        top = get_top_candidates(all_data, sig_date, TOP_N_BASE, inst_df)
        for ticker, ind, _ in top:
            rec = process_v1(ticker, ind, all_data, sig_date)
            if rec:
                trades.append(rec)
    return pd.DataFrame(trades)


def run_backtest_v3(all_data, inst_df, vix_series) -> pd.DataFrame:
    signal_dates = pd.date_range(BT_START, BT_END, freq="W-FRI")
    trades = []
    for sig_date in signal_dates:
        vix = get_vix_at(vix_series, sig_date)
        regime = get_regime(vix)
        if not regime["allow"]:
            continue
        max_pos = regime["max_pos"]
        top = get_top_candidates(all_data, sig_date, max_pos, inst_df)
        for ticker, ind, _ in top:
            rec = process_v3(ticker, ind, all_data, sig_date)
            if rec:
                trades.append(rec)
    return pd.DataFrame(trades)


# ---------------------------------------------------------------------------
# Statistiche
# ---------------------------------------------------------------------------

def compute_stats(df: pd.DataFrame, label: str) -> dict:
    closed = df[df["outcome"].isin(["EXIT", "WIN", "LOSS", "TIMEOUT"])].copy()
    if closed.empty:
        return None

    wins   = closed[closed["pnl_pct"] > 0]
    losses = closed[closed["pnl_pct"] <= 0]
    wr     = len(wins) / len(closed) * 100

    avg_win = wins["pnl_pct"].mean()   if not wins.empty   else 0
    avg_los = losses["pnl_pct"].mean() if not losses.empty else 0

    total_pnl  = closed["pnl_eur"].sum()
    net_profit = total_pnl - max(0, total_pnl * 0.26)
    ann_net    = net_profit / 6.33

    balance  = CAPITAL
    balances = []
    for _, row in closed.sort_values("date").iterrows():
        balance += row["pnl_eur"]
        balances.append(balance)
    bal_arr = np.array(balances) if balances else np.array([float(CAPITAL)])
    peak    = np.maximum.accumulate(bal_arr)
    max_dd  = ((bal_arr - peak) / peak * 100).min()

    yearly = {}
    for _, row in closed.sort_values("date").iterrows():
        yr = int(row["year"])
        yearly[yr] = round(yearly.get(yr, 0) + row["pnl_eur"], 0)

    p10 = np.percentile(closed["pnl_pct"], 10)
    med = np.percentile(closed["pnl_pct"], 50)
    p90 = np.percentile(closed["pnl_pct"], 90)

    avg_size = closed["size_eur"].mean()

    return {
        "label":       label,
        "trades":      len(closed),
        "win_rate":    round(wr, 1),
        "avg_win":     round(avg_win, 2),
        "avg_loss":    round(avg_los, 2),
        "ann_net_eur": round(ann_net, 0),
        "ann_pct":     round(ann_net / CAPITAL * 100, 1),
        "max_dd":      round(max_dd, 1),
        "avg_bars":    round(closed["bars"].mean(), 1),
        "avg_size":    round(avg_size, 0),
        "p10":         round(p10, 1),
        "median":      round(med, 1),
        "p90":         round(p90, 1),
        "yearly":      yearly,
    }


def print_results(s1: dict, s2: dict):
    SEP  = "=" * 96
    SEP2 = "-" * 92
    print(f"\n{SEP}")
    print(f"  V1 (Bloomberg + 13F)  vs  V3 (+ Chandelier + VIX regime + Sizing dinamico)")
    print(f"  Periodo: {BT_START} -> {BT_END} (6.33 anni) | Capitale: {CAPITAL:,}EUR")
    print(SEP)
    print(f"  {'Strategia':<38} {'Trade':>6} {'WR%':>6} {'AvgWIN':>7} {'AvgLSS':>7} "
          f"{'AnnNet€':>8} {'Ann%':>6} {'MaxDD':>7} {'AvgWks':>7} {'AvgSize':>8}")
    print(f"  {SEP2}")
    for s in [s1, s2]:
        print(f"  {s['label']:<38} {s['trades']:>6} {s['win_rate']:>5.1f}% "
              f"{s['avg_win']:>+6.1f}% {s['avg_loss']:>+6.1f}% "
              f"{s['ann_net_eur']:>+8.0f}€ {s['ann_pct']:>+5.1f}% "
              f"{s['max_dd']:>+6.1f}% {s['avg_bars']:>7.1f} {s['avg_size']:>8.0f}€")
    print(f"  {SEP2}")

    print(f"\n  Anno-per-anno: V1 vs V3")
    print(f"  {'Anno':<8} {'V1 lordo':>12} {'V3 lordo':>12} {'Delta':>12}")
    print(f"  {'-'*46}")
    all_years = sorted(set(list(s1["yearly"].keys()) + list(s2["yearly"].keys())))
    for yr in all_years:
        v1 = s1["yearly"].get(yr, 0)
        v3 = s2["yearly"].get(yr, 0)
        delta = v3 - v1
        sign = "+" if delta >= 0 else ""
        print(f"  {yr:<8} {v1:>+12.0f}€ {v3:>+12.0f}€ {sign}{delta:>10.0f}€ "
              f"{'✓' if delta > 0 else '✗'}")

    print(f"\n  Distribuzione PnL% per trade")
    print(f"  {'-'*60}")
    for s in [s1, s2]:
        print(f"  {s['label']:<38} P10={s['p10']:+.1f}%  Med={s['median']:+.1f}%  P90={s['p90']:+.1f}%")
    print(SEP)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 96)
    print("  BACKTEST V3 — Bloomberg V2 + 13F  vs  V3 (Chandelier + VIX regime + Sizing)")
    print("=" * 96)

    # Carica price data
    print("\nCaricamento price data dalla cache...")
    with open(CACHE_PRICE, "rb") as f:
        all_data_raw = pickle.load(f)
    usa_data = {t: df for t, df in all_data_raw.items() if t in WATCHLIST_USA}
    print(f"Ticker USA: {len(usa_data)}")

    # Carica 13F cache
    print("Caricamento 13F cache...")
    inst_df = None
    if os.path.exists(CACHE_13F):
        with open(CACHE_13F, "rb") as f:
            inst_df = pickle.load(f)
        print(f"13F cache: {len(inst_df)} record")
    else:
        print("WARN: inst13f_cache.pkl non trovato — backtest senza segnale 13F")
        inst_df = pd.DataFrame()

    # Carica VIX storico
    print("Caricamento VIX storico...")
    vix_series = load_vix_history()
    print(f"VIX data: {len(vix_series)} settimane")

    # Analisi regime VIX
    signal_dates = pd.date_range(BT_START, BT_END, freq="W-FRI")
    riskoff_weeks  = sum(1 for d in signal_dates if get_vix_at(vix_series, d) > VIX_RISKOFF)
    cautious_weeks = sum(1 for d in signal_dates if VIX_CAUTIOUS < get_vix_at(vix_series, d) <= VIX_RISKOFF)
    print(f"\n  Regime VIX ({BT_START} -> {BT_END}):")
    print(f"  Risk-Off  (VIX>{VIX_RISKOFF}): {riskoff_weeks} settimane ({riskoff_weeks/len(signal_dates)*100:.1f}%)")
    print(f"  Cautious  (VIX {VIX_CAUTIOUS}-{VIX_RISKOFF}): {cautious_weeks} settimane ({cautious_weeks/len(signal_dates)*100:.1f}%)")

    # Run backtests
    print("\n[1/2] Simulazione V1 (Bloomberg + 13F)...")
    df_v1 = run_backtest_v1(usa_data, inst_df)
    print(f"  Trade generati: {len(df_v1)}")

    print("[2/2] Simulazione V3 (Chandelier + VIX regime + Sizing)...")
    df_v3 = run_backtest_v3(usa_data, inst_df, vix_series)
    print(f"  Trade generati: {len(df_v3)}")

    # Statistiche
    s1 = compute_stats(df_v1, "V1: Bloomberg+13F (TP fisso, 500€)")
    s2 = compute_stats(df_v3, "V3: Chandelier+VIX+Sizing (40€ risk)")

    if s1 and s2:
        print_results(s1, s2)

    # Salva CSV
    df_v1.to_csv("backtest_v3_v1_trades.csv", index=False)
    df_v3.to_csv("backtest_v3_v3_trades.csv", index=False)
    print("\nRisultati salvati: backtest_v3_v1_trades.csv, backtest_v3_v3_trades.csv")
