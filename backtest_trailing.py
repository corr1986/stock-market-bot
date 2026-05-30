"""
backtest_trailing.py
--------------------
Testa le 3 configurazioni ottimali con trailing SL e/o rimozione cap temporale.

Per ogni config (SL=2.0xATR R:R 1:2 / SL=2.5xATR R:R 1:2 / SL=1.5xATR R:R 1:3):
  A. Base           (nessuna modifica)
  B. +Trailing SL   (SL sale di 5% ogni 5% di guadagno)
  C. +No cap        (nessun limite temporale)
  D. +Trail+NoCap   (entrambe le modifiche)

Trailing SL: SL = max(SL_iniziale, max_high - 5% dell'entry)
  - a +5%  dal entry  -> SL sale a breakeven
  - a +10%            -> SL sale a +5%
  - a +15%            -> SL sale a +10%  ... e cosi via

No cap: le trade girano senza limite di settimane finche non toccano SL o TP.
        Le trade ancora aperte a fine dati sono escluse dalle statistiche.

Uso: python backtest_trailing.py
"""

import os
import pickle
import pandas as pd
from datetime import datetime
from analyzer import compute_indicators, score_stock
from config import WATCHLIST_USA, WATCHLIST_EUROPE
import yfinance as yf

# ---------------------------------------------------------------------------
# Parametri
# ---------------------------------------------------------------------------

CAPITAL    = 20_000
TRADE_SIZE = 500
MIN_BARS   = 26
PRE_FILTER_N = 20
TOP_N = 3

SAFETY_CAP = 52       # settimane (usato solo se no_cap=False)
TRAIL_PCT  = 0.05     # 5% di distanza dall'high

BT_START = "2020-01-01"
BT_END   = "2026-04-30"

COMMISSION_EUR = 2.0

CACHE_FILE = os.path.join(os.path.dirname(__file__), "market_data.pkl")

# ---------------------------------------------------------------------------
# Le 3 config x 4 varianti = 12 backtest
# (sl_mult, rr, label, use_trail, no_cap)
# ---------------------------------------------------------------------------

CONFIGS = [
    # ---- Config 1: SL=2.0xATR R:R 1:2 ----
    (2.0, 2.0, "SL=2.0xATR R:R 1:2  base        ", False, False),
    (2.0, 2.0, "SL=2.0xATR R:R 1:2  +trail       ", True,  False),
    (2.0, 2.0, "SL=2.0xATR R:R 1:2  +nocap       ", False, True),
    (2.0, 2.0, "SL=2.0xATR R:R 1:2  +trail+nocap ", True,  True),
    # ---- Config 2: SL=2.5xATR R:R 1:2 ----
    (2.5, 2.0, "SL=2.5xATR R:R 1:2  base        ", False, False),
    (2.5, 2.0, "SL=2.5xATR R:R 1:2  +trail       ", True,  False),
    (2.5, 2.0, "SL=2.5xATR R:R 1:2  +nocap       ", False, True),
    (2.5, 2.0, "SL=2.5xATR R:R 1:2  +trail+nocap ", True,  True),
    # ---- Config 3: SL=1.5xATR R:R 1:3 ----
    (1.5, 3.0, "SL=1.5xATR R:R 1:3  base        ", False, False),
    (1.5, 3.0, "SL=1.5xATR R:R 1:3  +trail       ", True,  False),
    (1.5, 3.0, "SL=1.5xATR R:R 1:3  +nocap       ", False, True),
    (1.5, 3.0, "SL=1.5xATR R:R 1:3  +trail+nocap ", True,  True),
]


# ---------------------------------------------------------------------------
# Bloomberg V2 score
# ---------------------------------------------------------------------------

def bloomberg_enhanced_score(ind):
    base   = score_stock(ind)
    rsi    = ind.get("rsi_14") or 0
    vol    = ind.get("volume_ratio") or 0
    change = ind.get("weekly_change_pct") or 0
    sma50  = ind.get("above_sma50") or False
    bonus  = 0.0
    if vol >= 1.5:        bonus += 2.0
    elif vol >= 1.2:      bonus += 0.5
    if 50 <= rsi <= 62:   bonus += 1.5
    elif 48 <= rsi < 50:  bonus += 0.5
    elif rsi > 65:        bonus -= 2.0
    if change >= 2.0:     bonus += 1.5
    elif change >= 1.0:   bonus += 0.5
    if sma50:             bonus += 1.0
    return base + bonus


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def load_cache(tickers):
    if os.path.exists(CACHE_FILE):
        age = (datetime.now().timestamp() - os.path.getmtime(CACHE_FILE)) / 86400
        if age < 7:
            print(f"Cache caricata ({age:.1f} gg fa)")
            with open(CACHE_FILE, "rb") as f:
                data = pickle.load(f)
            print(f"Asset: {len(data)}/{len(tickers)}\n")
            return data
    print("Download dati WEEKLY...")
    data = {}
    for i, t in enumerate(tickers, 1):
        print(f"\r  {i}/{len(tickers)}: {t:<14}", end="", flush=True)
        try:
            df = yf.download(t, start="1999-01-01",
                             end=datetime.today().strftime("%Y-%m-%d"),
                             interval="1wk", progress=False, auto_adjust=True)
            if not df.empty:
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                data[t] = df
        except Exception:
            pass
    print()
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(data, f)
    return data


# ---------------------------------------------------------------------------
# Simulazione trade con trailing SL opzionale e cap opzionale
# ---------------------------------------------------------------------------

def simulate_trade(future, entry, initial_sl, tp, use_trail, no_cap):
    sl            = initial_sl
    max_high      = entry
    trail_dist    = TRAIL_PCT * entry   # distanza fissa = 5% del prezzo entry
    cap           = 999999 if no_cap else SAFETY_CAP

    for i, (_, row) in enumerate(future.iterrows()):
        if i >= cap:
            # Timeout: chiudi all'ultimo close disponibile
            exit_price = float(future["Close"].iloc[i - 1])
            return "TIMEOUT", exit_price, i

        high = float(row["High"])
        low  = float(row["Low"])

        # Aggiorna trailing SL (solo in su, mai in giu)
        if use_trail and high > max_high:
            max_high = high
            new_sl = max_high - trail_dist
            if new_sl > sl:
                sl = new_sl

        # Check SL (usiamo il Low della candela)
        if low <= sl:
            # Distingui tra uscita in profitto (trail sopra entry) e perdita
            outcome = "WIN" if sl > entry else ("BE" if sl == entry else "LOSS")
            return outcome, sl, i + 1

        # Check TP
        if high >= tp:
            return "WIN", tp, i + 1

    # Fine dati senza hit
    n = len(future)
    return ("OPEN", float(future["Close"].iloc[-1]), n) if n else ("OPEN", entry, 0)


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def run_backtest(all_data, sl_mult, rr, use_trail, no_cap):
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
        final = sorted(candidates[:PRE_FILTER_N],
                       key=lambda x: bloomberg_enhanced_score(x[1]), reverse=True)

        for ticker, ind, _ in final[:TOP_N]:
            entry = ind["price"]
            atr   = ind.get("atr_14") or (entry * 0.02)
            sl    = round(entry - sl_mult * atr, 4)
            tp    = round(entry + rr * sl_mult * atr, 4)

            future = all_data[ticker][all_data[ticker].index > sig_date]
            if future.empty:
                continue

            outcome, exit_price, bars = simulate_trade(
                future, entry, sl, tp, use_trail, no_cap
            )
            pnl_pct = (exit_price - entry) / entry * 100
            comm_pct = COMMISSION_EUR / TRADE_SIZE * 100 if outcome != "OPEN" else 0.0

            trades.append({
                "date":     sig_date.strftime("%Y-%m-%d"),
                "year":     sig_date.year,
                "ticker":   ticker,
                "outcome":  outcome,
                "bars":     bars,
                "pnl_pct":  round(pnl_pct - comm_pct, 4),
            })

    return pd.DataFrame(trades)


# ---------------------------------------------------------------------------
# Statistiche
# ---------------------------------------------------------------------------

def compute_stats(df, label, sl_mult, rr, use_trail, no_cap):
    # Chiusi = WIN (incluse trail wins) + BE + LOSS + TIMEOUT
    closed = df[df["outcome"].isin(["WIN", "BE", "LOSS", "TIMEOUT"])].copy()
    open_c = (df["outcome"] == "OPEN").sum()

    if closed.empty:
        return None

    # Per WR e EV: win = pnl > 0, loss = pnl <= 0
    profitable = closed[closed["pnl_pct"] > 0]
    unprofitable = closed[closed["pnl_pct"] <= 0]

    wr = len(profitable) / len(closed) * 100
    avg_win  = profitable["pnl_pct"].mean() if not profitable.empty else 0
    avg_loss = unprofitable["pnl_pct"].mean() if not unprofitable.empty else 0
    ev_pct   = (wr / 100) * avg_win + (1 - wr / 100) * avg_loss

    # TP wins separati dai trail wins
    tp_wins    = (closed["outcome"] == "WIN").sum()
    trail_wins = len(profitable[closed.loc[profitable.index, "outcome"] != "WIN"])
    # Semplificato: trail_win = profitable con outcome WIN ma pnl < rr*sl_pct
    losses     = (closed["outcome"] == "LOSS").sum()
    timeouts   = (closed["outcome"] == "TIMEOUT").sum()
    be_count   = (closed["outcome"] == "BE").sum()

    # PnL totale netto
    total_pnl = (closed["pnl_pct"] / 100 * TRADE_SIZE).sum()
    tax = max(0, total_pnl * 0.26)
    net = total_pnl - tax
    ann = net / 6.33

    # Max drawdown
    bal = CAPITAL
    min_bal = CAPITAL
    for _, row in closed.sort_values("date").iterrows():
        bal += row["pnl_pct"] / 100 * TRADE_SIZE
        min_bal = min(min_bal, bal)
    max_dd = (CAPITAL - min_bal) / CAPITAL * 100

    # Max SL consecutivi
    max_cl = curr = 0
    for _, row in closed.sort_values("date").iterrows():
        if row["pnl_pct"] <= 0:
            curr += 1
            max_cl = max(max_cl, curr)
        else:
            curr = 0

    return {
        "label":       label.strip(),
        "sl_mult":     sl_mult,
        "rr":          rr,
        "use_trail":   use_trail,
        "no_cap":      no_cap,
        "total":       len(closed),
        "open":        open_c,
        "profitable":  len(profitable),
        "losses":      len(unprofitable),
        "timeouts":    timeouts,
        "be":          be_count,
        "win_rate":    round(wr, 1),
        "avg_win":     round(avg_win, 2),
        "avg_loss":    round(avg_loss, 2),
        "ev_pct":      round(ev_pct, 3),
        "ev_eur":      round(ev_pct / 100 * TRADE_SIZE, 2),
        "ann_net":     round(ann, 0),
        "ann_pct":     round(ann / CAPITAL * 100, 1),
        "max_dd":      round(max_dd, 1),
        "max_cl":      max_cl,
        "avg_bars":    round(closed["bars"].mean(), 1),
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(all_stats):
    SEP  = "=" * 118
    SEP2 = "-" * 114

    print(f"\n{SEP}")
    print(f"  TRAILING SL + NO CAP  |  Bloomberg V2  |  Trade Republic (2 EUR RT, 26% tasse)")
    print(f"  Capitale {CAPITAL:,} EUR  |  Posizione {TRADE_SIZE} EUR  |  Top {TOP_N}/sett.  |  2020-2026")
    print(f"  Trailing: SL = max_high - 5% entry  |  NoCap: nessun limite temporale (OPEN esclusi)")
    print(SEP)

    hdr = (f"  {'Config':<36} {'Chius':>5} {'Open':>5} {'WR%':>6} "
           f"{'AvgWIN':>7} {'AvgLSS':>7} {'EV%':>7} {'EV EUR':>7} "
           f"{'AnnNet':>8} {'Ann%':>6} {'MaxDD':>7} {'MaxSL-':>7} {'AvgWks':>7} {'TO':>4} {'BE':>4}")
    print(hdr)
    print(f"  {SEP2}")

    # Raggruppa per config (ogni gruppo di 4)
    groups = [
        ("SL=2.0xATR R:R 1:2", [s for s in all_stats if s["sl_mult"]==2.0 and s["rr"]==2.0]),
        ("SL=2.5xATR R:R 1:2", [s for s in all_stats if s["sl_mult"]==2.5 and s["rr"]==2.0]),
        ("SL=1.5xATR R:R 1:3", [s for s in all_stats if s["sl_mult"]==1.5 and s["rr"]==3.0]),
    ]

    for group_name, group in groups:
        print(f"\n  --- {group_name} ---")
        base = group[0]
        for s in group:
            delta_ev  = s["ev_eur"]  - base["ev_eur"]
            delta_ann = s["ann_net"] - base["ann_net"]
            delta_wr  = s["win_rate"]- base["win_rate"]

            flag_ev  = f"({delta_ev:+.2f})" if s is not base else "        "
            flag_ann = f"({delta_ann:+.0f}E)" if s is not base else "        "
            flag_wr  = f"({delta_wr:+.1f}%)" if s is not base else "       "

            variant = ("BASE   " if not s["use_trail"] and not s["no_cap"] else
                       "+TRAIL " if s["use_trail"] and not s["no_cap"] else
                       "+NOCAP " if not s["use_trail"] and s["no_cap"] else
                       "+TR+NC ")

            print(
                f"  [{variant}] "
                f"{s['win_rate']:>5.1f}%{flag_wr:<9}"
                f"{s['avg_win']:>+6.1f}%"
                f"{s['avg_loss']:>+7.1f}%"
                f"{s['ev_pct']:>+7.3f}%"
                f"{s['ev_eur']:>+6.2f}{flag_ev:<10}"
                f"{s['ann_net']:>+7.0f}E{flag_ann:<10}"
                f"{s['ann_pct']:>+5.1f}%"
                f"{s['max_dd']:>+7.1f}%"
                f"{s['max_cl']:>7}"
                f"{s['avg_bars']:>7.1f}"
                f"{s['timeouts']:>5}"
                f"{s['be']:>5}"
                f"  open={s['open']}"
            )

    print(f"\n  {SEP2}")
    print(SEP)

    # Riepilogo: migliore variante per ogni config
    print(f"\n  RIEPILOGO — miglior variante per ogni config (per EV per trade):")
    print(f"  {'Config':<36} {'Variant':<12} {'WR':>6} {'EV EUR':>8} {'AnnNet':>9} {'MaxDD':>7} {'MaxSL-':>8}")
    print(f"  {'-' * 88}")

    for group_name, group in groups:
        best = max(group, key=lambda x: x["ev_eur"])
        v = ("BASE" if not best["use_trail"] and not best["no_cap"] else
             "+TRAIL" if best["use_trail"] and not best["no_cap"] else
             "+NOCAP" if not best["use_trail"] and best["no_cap"] else
             "+TR+NC")
        print(f"  {group_name:<36} {v:<12} {best['win_rate']:>5.1f}% {best['ev_eur']:>+8.2f} "
              f"{best['ann_net']:>+8.0f}E {best['max_dd']:>+7.1f}% {best['max_cl']:>8}")

    print()

    # Effetto isolated del trailing e del no_cap
    print(f"  IMPATTO MEDIO delle 2 modifiche (media sui 3 config):")
    deltas_trail_ev  = []
    deltas_trail_wr  = []
    deltas_trail_ann = []
    deltas_cap_ev    = []
    deltas_cap_wr    = []
    deltas_cap_ann   = []

    for _, group in groups:
        base  = group[0]  # base
        trail = group[1]  # +trail
        nocap = group[2]  # +nocap

        deltas_trail_ev.append(trail["ev_eur"]  - base["ev_eur"])
        deltas_trail_wr.append(trail["win_rate"] - base["win_rate"])
        deltas_trail_ann.append(trail["ann_net"] - base["ann_net"])

        deltas_cap_ev.append(nocap["ev_eur"]   - base["ev_eur"])
        deltas_cap_wr.append(nocap["win_rate"]  - base["win_rate"])
        deltas_cap_ann.append(nocap["ann_net"]  - base["ann_net"])

    def avg(lst): return sum(lst) / len(lst)

    print(f"  +Trailing SL 5%:  EV {avg(deltas_trail_ev):+.2f} EUR/trade  |  WR {avg(deltas_trail_wr):+.1f}%  |  AnnNet {avg(deltas_trail_ann):+.0f} EUR")
    print(f"  +No cap:          EV {avg(deltas_cap_ev):+.2f} EUR/trade  |  WR {avg(deltas_cap_wr):+.1f}%  |  AnnNet {avg(deltas_cap_ann):+.0f} EUR")
    print(SEP)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    all_tickers = WATCHLIST_USA + WATCHLIST_EUROPE

    print("=" * 60)
    print(f"  backtest_trailing.py  |  12 configurazioni")
    print(f"  3 config x 4 varianti (base/trail/nocap/entrambi)")
    print("=" * 60)
    print()

    all_data = load_cache(all_tickers)
    all_stats = []

    for i, (sl_mult, rr, label, use_trail, no_cap) in enumerate(CONFIGS, 1):
        mods = []
        if use_trail: mods.append("trail")
        if no_cap:    mods.append("nocap")
        mod_str = "+".join(mods) if mods else "base"
        print(f"  [{i:2d}/12] {label.strip()} ({mod_str})...", flush=True)

        df = run_backtest(all_data, sl_mult, rr, use_trail, no_cap)
        stats = compute_stats(df, label, sl_mult, rr, use_trail, no_cap)

        if stats:
            all_stats.append(stats)
            print(f"          Trade={stats['total']}  Open={stats['open']}  "
                  f"WR={stats['win_rate']:.1f}%  EV={stats['ev_eur']:+.2f}EUR  "
                  f"AnnNet={stats['ann_net']:+.0f}EUR  TO={stats['timeouts']}")

    print()
    print_report(all_stats)

    out = pd.DataFrame([{k: v for k, v in s.items()} for s in all_stats])
    out.to_csv(os.path.join(os.path.dirname(__file__), "backtest_trailing_results.csv"), index=False)
    print("\nRisultati salvati in: backtest_trailing_results.csv")
