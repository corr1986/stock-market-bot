"""
backtest_fixed_pct.py
---------------------
Bloomberg V2 con SL/TP a percentuale fissa invece di ATR.

Configurazioni testate:
  - SL -20% / TP +40%  (R:R 1:2)  <- richiesta utente
  + alcune varianti per contesto

Usa la stessa cache market_data.pkl del simulatore principale.

Uso:
    python backtest_fixed_pct.py
"""

import os
import pickle
import pandas as pd
from datetime import datetime
from analyzer import compute_indicators, score_stock
from config import WATCHLIST_USA, WATCHLIST_EUROPE
import yfinance as yf

# ---------------------------------------------------------------------------
# Parametri globali
# ---------------------------------------------------------------------------

CAPITAL    = 20_000
TRADE_SIZE = 500
SAFETY_CAP = 52
MIN_BARS   = 26
PRE_FILTER_N = 20
TOP_N = 3

BT_START = "2020-01-01"
BT_END   = "2026-04-30"

COMMISSION_EUR = 2.0   # TR: 1 EUR/ordine × 2

CACHE_FILE = os.path.join(os.path.dirname(__file__), "market_data.pkl")

# ---------------------------------------------------------------------------
# Configurazioni: (sl_pct, tp_pct, label)
# SL e TP come percentuale dell'entry (es. 0.20 = 20%)
# ---------------------------------------------------------------------------

CONFIGS = [
    # Richiesta principale
    (0.20, 0.40, "SL -20%  TP +40%  (R:R 1:2)"),
    # Varianti per confronto
    (0.15, 0.30, "SL -15%  TP +30%  (R:R 1:2)"),
    (0.10, 0.20, "SL -10%  TP +20%  (R:R 1:2)"),
    (0.20, 0.60, "SL -20%  TP +60%  (R:R 1:3)"),
    (0.15, 0.45, "SL -15%  TP +45%  (R:R 1:3)"),
]


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
# Cache
# ---------------------------------------------------------------------------

def load_cache(tickers):
    if os.path.exists(CACHE_FILE):
        age_days = (datetime.now().timestamp() - os.path.getmtime(CACHE_FILE)) / 86400
        if age_days < 7:
            print(f"Cache caricata ({age_days:.1f} giorni fa) — {len(tickers)} ticker attesi")
            with open(CACHE_FILE, "rb") as f:
                data = pickle.load(f)
            print(f"Asset disponibili: {len(data)}/{len(tickers)}\n")
            return data
        print(f"Cache scaduta ({age_days:.1f} giorni), re-download...")

    print("Download dati WEEKLY...")
    data = {}
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        print(f"\r  {i}/{total}: {ticker:<14}", end="", flush=True)
        try:
            df = yf.download(
                ticker, start="1999-01-01", end=datetime.today().strftime("%Y-%m-%d"),
                interval="1wk", progress=False, auto_adjust=True
            )
            if not df.empty:
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                data[ticker] = df
        except Exception:
            pass
    print()
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(data, f)
    print(f"Scaricati: {len(data)}/{len(tickers)}\n")
    return data


# ---------------------------------------------------------------------------
# Simulazione singolo trade
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


# ---------------------------------------------------------------------------
# Backtest Bloomberg V2 con SL/TP percentuale fissa
# ---------------------------------------------------------------------------

def run_backtest(all_data, sl_pct, tp_pct):
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
        top20 = candidates[:PRE_FILTER_N]
        final = sorted(top20, key=lambda x: bloomberg_enhanced_score(x[1]), reverse=True)

        for ticker, ind, _ in final[:TOP_N]:
            entry = ind["price"]
            sl    = round(entry * (1 - sl_pct), 4)
            tp    = round(entry * (1 + tp_pct), 4)

            future = all_data[ticker][all_data[ticker].index > sig_date]
            if future.empty:
                continue

            outcome, exit_price, bars_held = simulate_trade(future, entry, sl, tp)
            pnl_pct = (exit_price - entry) / entry * 100

            commission_pct = COMMISSION_EUR / TRADE_SIZE * 100 if outcome != "OPEN" else 0.0

            trades.append({
                "date":     sig_date.strftime("%Y-%m-%d"),
                "year":     sig_date.year,
                "ticker":   ticker,
                "entry":    round(entry, 4),
                "sl_pct":   round(sl_pct * 100, 1),
                "tp_pct":   round(tp_pct * 100, 1),
                "outcome":  outcome,
                "bars_held": bars_held,
                "pnl_pct":  round(pnl_pct - commission_pct, 4),
            })

    return pd.DataFrame(trades)


# ---------------------------------------------------------------------------
# Statistiche
# ---------------------------------------------------------------------------

def compute_stats(df, sl_pct, tp_pct, label):
    closed = df[df["outcome"].isin(["WIN", "LOSS", "TIMEOUT"])].copy()
    if closed.empty:
        return None

    wins     = closed[closed["outcome"] == "WIN"]
    losses   = closed[closed["outcome"] == "LOSS"]
    timeouts = closed[closed["outcome"] == "TIMEOUT"]

    wr = len(wins) / len(closed) * 100

    avg_win_pct  = wins["pnl_pct"].mean() if not wins.empty else 0
    avg_loss_pct = losses["pnl_pct"].mean() if not losses.empty else 0
    ev_pct = (wr / 100) * avg_win_pct + (1 - wr / 100) * avg_loss_pct

    # PnL netto Trade Republic (solo WIN/LOSS/TIMEOUT, 26% tasse)
    total_pnl_eur = (closed["pnl_pct"] / 100 * TRADE_SIZE).sum()
    tax = max(0, total_pnl_eur * 0.26)
    net_profit = total_pnl_eur - tax
    ann_profit = net_profit / 6.33

    # Max drawdown
    balance = CAPITAL
    min_balance = CAPITAL
    for _, row in closed.sort_values("date").iterrows():
        balance += row["pnl_pct"] / 100 * TRADE_SIZE
        min_balance = min(min_balance, balance)
    max_dd = (CAPITAL - min_balance) / CAPITAL * 100

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
        pnl_eur = row["pnl_pct"] / 100 * TRADE_SIZE
        yearly[yr] = yearly.get(yr, 0) + pnl_eur

    return {
        "label":         label,
        "sl_pct":        sl_pct * 100,
        "tp_pct":        tp_pct * 100,
        "trades":        len(closed),
        "wins":          len(wins),
        "losses":        len(losses),
        "timeouts":      len(timeouts),
        "win_rate":      round(wr, 1),
        "avg_win_pct":   round(avg_win_pct, 2),
        "avg_loss_pct":  round(avg_loss_pct, 2),
        "ev_pct":        round(ev_pct, 3),
        "ev_eur":        round(ev_pct / 100 * TRADE_SIZE, 2),
        "total_pnl_eur": round(total_pnl_eur, 0),
        "net_after_tax": round(net_profit, 0),
        "ann_net_eur":   round(ann_profit, 0),
        "ann_pct":       round(ann_profit / CAPITAL * 100, 1),
        "max_dd_pct":    round(max_dd, 1),
        "max_consec_l":  max_cl,
        "avg_bars":      round(closed["bars_held"].mean(), 1),
        "yearly":        yearly,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(all_stats):
    SEP  = "=" * 112
    SEP2 = "-" * 108

    print(f"\n{SEP}")
    print(f"  SL/TP PERCENTUALE FISSO  |  Bloomberg V2  |  Trade Republic (2 EUR RT, 26% tasse)")
    print(f"  Capitale {CAPITAL:,} EUR  |  Posizione {TRADE_SIZE} EUR  |  Top {TOP_N}/sett.  |  2020-2026 (6.33 anni)")
    print(SEP)

    hdr = (f"  {'Config':<32} {'Trade':>6} {'WIN':>5} {'LSS':>5} {'TO':>5} "
           f"{'WR%':>6} {'AvgWIN':>7} {'AvgLSS':>7} {'EV%':>7} {'EV EUR':>7} "
           f"{'AnnNet':>8} {'Ann%':>6} {'MaxDD':>7} {'MaxSL-':>7} {'AvgWks':>7}")
    print(hdr)
    print(f"  {SEP2}")

    for s in all_stats:
        print(
            f"  {s['label']:<32} "
            f"{s['trades']:>6} "
            f"{s['wins']:>5} "
            f"{s['losses']:>5} "
            f"{s['timeouts']:>5} "
            f"{s['win_rate']:>5.1f}%"
            f"{s['avg_win_pct']:>+7.1f}%"
            f"{s['avg_loss_pct']:>+7.1f}%"
            f"{s['ev_pct']:>+7.3f}%"
            f"{s['ev_eur']:>+7.2f}"
            f"{s['ann_net_eur']:>+8.0f}E"
            f"{s['ann_pct']:>+6.1f}%"
            f"{s['max_dd_pct']:>+7.1f}%"
            f"{s['max_consec_l']:>7}"
            f"{s['avg_bars']:>7.1f}"
        )

    print(f"  {SEP2}")
    print(SEP)

    # Dettaglio annuale per SL -20% / TP +40%
    target = next((s for s in all_stats if s["sl_pct"] == 20.0 and s["tp_pct"] == 40.0), None)
    if target:
        print(f"\n  Dettaglio annuale — {target['label']}")
        print(f"  {'Anno':<8} {'PnL lordo':>12} {'Tasse 26%':>12} {'PnL netto':>12}")
        print(f"  {'-' * 48}")
        total_gross = 0
        for yr in sorted(target["yearly"].keys()):
            gross = target["yearly"][yr]
            tax   = max(0, gross * 0.26)
            net   = gross - tax
            total_gross += gross
            print(f"  {yr:<8} {gross:>+11.0f}E {-tax:>+11.0f}E {net:>+11.0f}E")
        total_tax = max(0, total_gross * 0.26)
        print(f"  {'-' * 48}")
        print(f"  {'TOTALE':<8} {total_gross:>+11.0f}E {-total_tax:>+11.0f}E {total_gross-total_tax:>+11.0f}E")
        print(f"  {'ANNUO':<8} {total_gross/6.33:>+11.0f}E {'':>12} {(total_gross-total_tax)/6.33:>+11.0f}E")
    print(SEP)

    # Confronto diretto con ATR baseline
    print(f"\n  CONFRONTO vs Bloomberg V2 ATR baseline (SL=1.5xATR, R:R 1:4):")
    print(f"  {'':32} {'WR':>6} {'EV EUR':>8} {'AnnNet':>9} {'MaxDD':>7} {'MaxSL-':>8}")
    print(f"  {'-' * 74}")
    print(f"  {'ATR baseline  SL=1.5x  R:R 1:4':<32} {'28.4%':>6} {'+22.54':>8} {'+4077E':>9} {'1.4%':>7} {'20':>8}")
    for s in all_stats:
        print(f"  {s['label']:<32} {s['win_rate']:>5.1f}% {s['ev_eur']:>+8.2f} {s['ann_net_eur']:>+8.0f}E {s['max_dd_pct']:>+7.1f}% {s['max_consec_l']:>8}")
    print(SEP)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    all_tickers = WATCHLIST_USA + WATCHLIST_EUROPE

    print("=" * 60)
    print(f"  backtest_fixed_pct.py  |  SL/TP % fisso  |  {len(CONFIGS)} config")
    print("=" * 60)
    print()

    all_data = load_cache(all_tickers)

    all_stats = []
    for i, (sl_pct, tp_pct, label) in enumerate(CONFIGS, 1):
        print(f"  [{i}/{len(CONFIGS)}] {label}...", flush=True)
        df = run_backtest(all_data, sl_pct=sl_pct, tp_pct=tp_pct)
        stats = compute_stats(df, sl_pct, tp_pct, label)
        if stats:
            all_stats.append(stats)
            print(f"         Trade={stats['trades']}  WR={stats['win_rate']:.1f}%  "
                  f"EV={stats['ev_eur']:+.2f}EUR  AnnNet={stats['ann_net_eur']:+.0f}EUR  "
                  f"TIMEOUT={stats['timeouts']}")
            fname = f"backtest_pct_sl{int(sl_pct*100)}_tp{int(tp_pct*100)}.csv"
            df.to_csv(os.path.join(os.path.dirname(__file__), fname), index=False)

    print()
    print_report(all_stats)

    pd.DataFrame(all_stats).drop(columns=["yearly"]).to_csv(
        os.path.join(os.path.dirname(__file__), "backtest_fixed_pct_results.csv"), index=False
    )
    print("\nRisultati salvati in: backtest_fixed_pct_results.csv")
