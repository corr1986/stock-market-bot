"""
Simulazione WEEKLY — no time limit — R:R 3:1
Confronto TOP_N = 1, 2, 3 segnali per settimana
Periodo: 2022-01-01 -> 2026-04-30
Capitale: 5000EUR | Posizione: 500EUR/trade
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from analyzer import compute_indicators, score_stock
from config import WATCHLIST_USA, WATCHLIST_EUROPE, WATCHLIST_INDICES

CAPITAL    = 5_000
TRADE_SIZE = 500
SL_MULT    = 1.5
RR         = 3.0
SAFETY_CAP = 52        # settimane massime di holding
MIN_BARS   = 26

BT_START = "2000-01-01"
BT_END   = "2026-04-30"


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_all(tickers, dl_start, dl_end, interval):
    data = {}
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        print(f"\r  {i}/{total}: {ticker:<14}", end="", flush=True)
        try:
            df = yf.download(ticker, start=dl_start, end=dl_end,
                             interval=interval, progress=False, auto_adjust=True)
            if not df.empty:
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                data[ticker] = df
        except Exception:
            pass
    print()
    return data


# ---------------------------------------------------------------------------
# Simulazione singolo trade (barre weekly)
# ---------------------------------------------------------------------------

def simulate_trade(future, entry, sl, tp):
    for i, (_, row) in enumerate(future.iterrows()):
        if i >= SAFETY_CAP:
            return "TIMEOUT", float(future["Close"].iloc[i - 1])
        if float(row["Low"]) <= sl:
            return "LOSS", sl
        if float(row["High"]) >= tp:
            return "WIN", tp
    if len(future):
        return "OPEN", float(future["Close"].iloc[-1])
    return "OPEN", entry


# ---------------------------------------------------------------------------
# Backtest weekly con TOP_N variabile
# ---------------------------------------------------------------------------

def run_backtest(all_data, top_n):
    signal_dates = pd.date_range(BT_START, BT_END, freq="W-FRI")
    trades = []

    for sig_date in signal_dates:
        candidates = []
        for ticker, df in all_data.items():
            if ticker.startswith("^"):
                continue
            hist = df[df.index <= sig_date].tail(200)
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

        for ticker, ind, _ in candidates[:top_n]:
            entry = ind["price"]
            atr   = ind.get("atr_14") or (entry * 0.02)
            sl    = round(entry - SL_MULT * atr, 4)
            tp    = round(entry + RR * SL_MULT * atr, 4)
            future = all_data[ticker]
            future = future[future.index > sig_date]
            if future.empty:
                continue
            outcome, exit_price = simulate_trade(future, entry, sl, tp)
            pnl_pct = (exit_price - entry) / entry * 100
            trades.append({
                "date":    sig_date,
                "year":    sig_date.year,
                "ticker":  ticker,
                "entry":   entry,
                "sl_pct":  round((entry - sl) / entry * 100, 2),
                "tp_pct":  round((tp - entry) / entry * 100, 2),
                "outcome": outcome,
                "pnl_pct": round(pnl_pct, 2),
            })

    return pd.DataFrame(trades)


# ---------------------------------------------------------------------------
# Simulazione capitale
# ---------------------------------------------------------------------------

def simulate_capital(trades_df):
    closed = trades_df[trades_df["outcome"].isin(["WIN","LOSS","TIMEOUT"])].copy()
    closed = closed.sort_values("date").reset_index(drop=True)

    balance      = CAPITAL
    total_profit = 0.0
    min_balance  = CAPITAL
    yearly       = {}

    for _, row in closed.iterrows():
        pnl_eur  = row["pnl_pct"] / 100 * TRADE_SIZE
        balance += pnl_eur
        if balance < min_balance:
            min_balance = balance
        if balance > CAPITAL:
            withdrawn     = balance - CAPITAL
            total_profit += withdrawn
            yr = int(row["year"])
            yearly[yr]   = yearly.get(yr, 0) + withdrawn
            balance       = CAPITAL

    max_cl = curr = 0
    for o in closed["outcome"]:
        if o == "LOSS":
            curr += 1
            max_cl = max(max_cl, curr)
        else:
            curr = 0

    open_n = (trades_df["outcome"] == "OPEN").sum()

    return {
        "trades":       len(closed),
        "open":         open_n,
        "wins":         (closed["outcome"] == "WIN").sum(),
        "losses":       (closed["outcome"] == "LOSS").sum(),
        "wr":           (closed["outcome"] == "WIN").sum() / len(closed) * 100 if len(closed) else 0,
        "ev":           closed["pnl_pct"].mean() if len(closed) else 0,
        "avg_win_eur":  closed[closed["outcome"]=="WIN"]["pnl_pct"].mean() / 100 * TRADE_SIZE if (closed["outcome"]=="WIN").any() else 0,
        "avg_loss_eur": closed[closed["outcome"]=="LOSS"]["pnl_pct"].mean() / 100 * TRADE_SIZE if (closed["outcome"]=="LOSS").any() else 0,
        "total_profit": total_profit,
        "ann_profit":   total_profit / 4.33,   # ~4.33 anni (gen22->apr26)
        "max_dd_eur":   CAPITAL - min_balance,
        "max_dd_pct":   (CAPITAL - min_balance) / CAPITAL * 100,
        "max_consec_l": max_cl,
        "yearly":       yearly,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(results):
    sep  = "=" * 68
    sep2 = "-" * 64

    print(f"\n{sep}")
    print(f"  BACKTEST WEEKLY 2022-2026 (apr) | R:R 3:1 | SL=1.5x ATR weekly")
    print(f"  Capitale {CAPITAL}EUR | Posizione {TRADE_SIZE}EUR/trade | Prelievo profitti")
    print(sep)

    labels = {1: "TOP 1 / sett.", 2: "TOP 2 / sett.", 3: "TOP 3 / sett."}
    keys   = sorted(results.keys())

    header = f"  {'Metrica':<32}" + "".join(f"{labels[k]:>12}" for k in keys)
    print(header)
    print(f"  {sep2}")

    def row(label, fmt, *vals):
        cells = "".join(f"{v:>12}" for v in vals)
        print(f"  {label:<32}{cells}")

    r = {k: results[k] for k in keys}

    row("Trade chiusi",          "", *[r[k]["trades"]           for k in keys])
    row("Posizioni ancora aperte","",*[r[k]["open"]             for k in keys])
    row("WIN",                   "", *[r[k]["wins"]             for k in keys])
    row("LOSS",                  "", *[r[k]["losses"]           for k in keys])
    row("Win rate",              "", *[f"{r[k]['wr']:.1f}%"     for k in keys])
    row("EV medio per trade",    "", *[f"{r[k]['ev']:+.2f}%"    for k in keys])
    print(f"  {sep2}")
    row("Guadagno medio WIN",    "", *[f"{r[k]['avg_win_eur']:+.0f}EUR"  for k in keys])
    row("Perdita media LOSS",    "", *[f"{r[k]['avg_loss_eur']:+.0f}EUR" for k in keys])
    print(f"  {sep2}")
    row("PROFITTO TOTALE",       "", *[f"{r[k]['total_profit']:+.0f}EUR" for k in keys])
    row("Profitto medio annuo",  "", *[f"{r[k]['ann_profit']:+.0f}EUR"   for k in keys])
    row("Rendimento annuo",      "", *[f"{r[k]['ann_profit']/CAPITAL*100:.1f}%" for k in keys])
    print(f"  {sep2}")
    row("Max drawdown EUR",      "", *[f"{-r[k]['max_dd_eur']:+.0f}EUR"  for k in keys])
    row("Max drawdown %",        "", *[f"{-r[k]['max_dd_pct']:.1f}%"     for k in keys])
    row("Max SL consecutivi",    "", *[r[k]["max_consec_l"]     for k in keys])
    print(sep)

    all_years = sorted(set(yr for k in keys for yr in r[k]["yearly"]))
    print(f"\n  {'Anno':<8}" + "".join(f"{labels[k]:>12}" for k in keys))
    print(f"  {'-'*44}")
    for yr in all_years:
        vals = "".join(f"{r[k]['yearly'].get(yr,0):>+11.0f}EUR" for k in keys)
        print(f"  {yr:<8}{vals}")
    print(sep)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    all_tickers = WATCHLIST_USA + WATCHLIST_EUROPE + list(WATCHLIST_INDICES.keys())

    dl_start = "1999-01-01"
    dl_end   = datetime.today().strftime("%Y-%m-%d")   # dati fino a oggi

    print(f"Download dati WEEKLY {dl_start} -> {dl_end} per {len(all_tickers)} asset...")
    all_data = download_all(all_tickers, dl_start, dl_end, "1wk")
    print(f"Asset scaricati: {len(all_data)}/{len(all_tickers)}\n")

    results = {}
    for top_n in [3]:
        print(f"Backtest TOP_N={top_n}...", end=" ", flush=True)
        trades = run_backtest(all_data, top_n)
        sim    = simulate_capital(trades)
        results[top_n] = sim
        print(f"trade chiusi: {sim['trades']}  WR: {sim['wr']:.1f}%  profitto: {sim['total_profit']:+.0f}EUR")

    print_report(results)
