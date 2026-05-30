"""
simulate_bloomberg.py
---------------------
Confronto diretto tra due strategie sullo stesso periodo e watchlist:

  - V1 BASE    : filtro tecnico standard (score_stock > 0, MACD > 0)
  - BLOOMBERG  : filtro tecnico + regole proxy del layer qualitativo Claude.ai

Regole proxy Bloomberg (approssimano cio che Claude.ai controlla):
  1. volume_ratio  >= 1.5   -> segnale di catalyst istituzionale
  2. RSI           48-62    -> momentum confermato, non ipercomprato (piu stretto di v1: 40-65)
  3. weekly_change >= 1.0%  -> il titolo sta gia muovendo
  4. score         >= 7.0   -> solo setup tecnici di alta qualita (v1 usa > 0)
  5. above_sma50   = True   -> trend primario rialzista obbligatorio

NON modifica nessun file esistente. Output:
  - Console: tabella comparativa completa con sweep RR 3:1 / 4:1 / 5:1
  - backtest_v1_rr<N>_results.csv: trade V1 per ciascun RR
  - backtest_bloomberg_v2_rr<N>_results.csv: trade Bloomberg V2 per ciascun RR

Uso:
    python simulate_bloomberg.py

Tempo stimato: 15-25 min (download dati + 6 backtests)
"""

import pandas as pd
import yfinance as yf
from datetime import datetime
from analyzer import compute_indicators, score_stock
from config import WATCHLIST_USA, WATCHLIST_EUROPE

# ---------------------------------------------------------------------------
# Parametri condivisi
# ---------------------------------------------------------------------------

CAPITAL    = 5_000
TRADE_SIZE = 500
SL_MULT    = 1.5
SAFETY_CAP = 52      # max 52 settimane per trade
MIN_BARS   = 26

BT_START = "2020-01-01"
BT_END   = "2026-04-30"

RR_VALUES = [3, 4, 5]


# ---------------------------------------------------------------------------
# Filtro BLOOMBERG: regole proxy del layer qualitativo
# ---------------------------------------------------------------------------

def bloomberg_filter(ind: dict) -> bool:
    """
    Restituisce True solo se il titolo passa il filtro qualitativo proxy.
    Approssima i criteri che Claude.ai applica: catalyst istituzionale,
    momentum confermato, nessuna zona di rischio tecnico.
    """
    rsi    = ind.get("rsi_14") or 0
    vol    = ind.get("volume_ratio") or 0
    change = ind.get("weekly_change_pct") or 0
    score  = score_stock(ind)
    sma50  = ind.get("above_sma50") or False

    return (
        vol    >= 1.5   and   # catalyst istituzionale
        48 <= rsi <= 62 and   # momentum ok, non ipercomprato
        change >= 1.0   and   # titolo in movimento questa settimana
        score  >= 7.0   and   # solo setup tecnici di alta qualita
        sma50               # trend primario rialzista obbligatorio
    )


def bloomberg_enhanced_score(ind: dict) -> float:
    """
    Punteggio Bloomberg-enhanced: parte dal score tecnico base e aggiunge
    bonus per i criteri qualitativi proxy. Usato per ri-ordinare il top 20
    e garantire sempre 3 selezioni/settimana.
    """
    base   = score_stock(ind)
    rsi    = ind.get("rsi_14") or 0
    vol    = ind.get("volume_ratio") or 0
    change = ind.get("weekly_change_pct") or 0
    sma50  = ind.get("above_sma50") or False

    bonus = 0.0
    if vol >= 1.5:              bonus += 2.0   # catalyst istituzionale
    elif vol >= 1.2:            bonus += 0.5
    if 50 <= rsi <= 62:         bonus += 1.5   # zona RSI ideale
    elif 48 <= rsi < 50:        bonus += 0.5
    elif rsi > 65:              bonus -= 2.0   # ipercomprato: penalita
    if change >= 2.0:           bonus += 1.5   # forte momentum settimanale
    elif change >= 1.0:         bonus += 0.5
    if sma50:                   bonus += 1.0   # trend primario confermato

    return base + bonus


# ---------------------------------------------------------------------------
# Download dati
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


# ---------------------------------------------------------------------------
# Simulazione singolo trade
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
# Backtest -- mode: "v1" oppure "bloomberg_v2"
# ---------------------------------------------------------------------------

PRE_FILTER_N = 20   # top 20 tecnici, poi Bloomberg ri-ordina dentro quelli

def run_backtest(all_data, mode="v1", top_n=3, rr=3.0):
    """
    mode = "v1"          -> top N per score tecnico (comportamento attuale del bot)
    mode = "bloomberg_v2"-> top 20 tecnici -> ri-ordina per bloomberg_enhanced_score
                           -> sempre top N (stesso volume di trade di V1, selezione diversa)
    """
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

                # --- Filtro V1 base: MACD positivo e score > 0 ---
                if not (score > 0 and (ind.get("macd_hist") or 0) > 0):
                    continue

                candidates.append((ticker, ind, score))

            except Exception:
                continue

        # Ordina per score tecnico
        candidates.sort(key=lambda x: x[2], reverse=True)

        if mode == "bloomberg_v2":
            # Re-ranking: top 20 tecnici -> ri-ordina per bloomberg_enhanced_score -> top N
            top20 = candidates[:PRE_FILTER_N]
            final = sorted(
                top20,
                key=lambda x: bloomberg_enhanced_score(x[1]),
                reverse=True
            )
        else:
            # V1 base: prende direttamente i top N tecnici
            final = candidates

        for ticker, ind, _ in final[:top_n]:
            entry = ind["price"]
            atr   = ind.get("atr_14") or (entry * 0.02)
            sl    = round(entry - SL_MULT * atr, 4)
            tp    = round(entry + rr * SL_MULT * atr, 4)

            future = all_data[ticker][all_data[ticker].index > sig_date]
            if future.empty:
                continue

            outcome, exit_price = simulate_trade(future, entry, sl, tp)
            pnl_pct = (exit_price - entry) / entry * 100

            trades.append({
                "date":    sig_date.strftime("%Y-%m-%d"),
                "year":    sig_date.year,
                "ticker":  ticker,
                "mode":    mode,
                "rr":      rr,
                "entry":   round(entry, 4),
                "sl_pct":  round((entry - sl) / entry * 100, 2),
                "tp_pct":  round((tp - entry) / entry * 100, 2),
                "outcome": outcome,
                "pnl_pct": round(pnl_pct, 2),
            })

    return pd.DataFrame(trades)


# ---------------------------------------------------------------------------
# Statistiche
# ---------------------------------------------------------------------------

def compute_stats(df):
    closed = df[df["outcome"].isin(["WIN", "LOSS", "TIMEOUT"])].copy()
    if closed.empty:
        return {}

    wins   = closed[closed["outcome"] == "WIN"]
    losses = closed[closed["outcome"] == "LOSS"]

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
        "ann_profit":   total_profit / 6.33,   # 2020-2026 ~ 6.33 anni
        "max_dd_pct":   (CAPITAL - min_balance) / CAPITAL * 100,
        "max_consec_l": max_cl,
        "yearly":       yearly,
    }


# ---------------------------------------------------------------------------
# Report parametrico (sweep RR)
# ---------------------------------------------------------------------------

def print_rr_sweep(results):
    """
    results = { rr: { "v1": stats_dict, "bloomberg_v2": stats_dict }, ... }
    Stampa una tabella comparativa per ogni RR testato.
    """
    sep  = "=" * 72
    sep2 = "-" * 68

    print(f"\n{sep}")
    print("  SWEEP R:R  2020-2026  |  TOP 3/sett.  |  Capitale 5000EUR")
    print(f"  Watchlist USA + Europa  |  SL = 1.5x ATR settimanale")
    print(sep)

    for rr in sorted(results.keys()):
        sv1 = results[rr]["v1"]
        sb2 = results[rr]["bloomberg_v2"]

        print(f"\n  *** R:R  {rr}:1  ***")
        print(f"  {'Metrica':<32} {'V1 BASE':>16} {'BLOOMBERG V2':>16}")
        print(f"  {sep2}")

        def row(label, v1_val, bl_val):
            print(f"  {label:<32} {str(v1_val):>16} {str(bl_val):>16}")

        row("Trade totali",         sv1["total_trades"],  sb2["total_trades"])
        row("WIN / LOSS / TIMEOUT",
            f"{sv1['wins']}/{sv1['losses']}/{sv1['timeouts']}",
            f"{sb2['wins']}/{sb2['losses']}/{sb2['timeouts']}")
        row("Win rate",
            f"{sv1['win_rate']:.1f}%",
            f"{sb2['win_rate']:.1f}%")
        row("EV medio per trade",
            f"{sv1['avg_pnl']:+.2f}%",
            f"{sb2['avg_pnl']:+.2f}%")
        row("Media WIN",
            f"{sv1['avg_win']:+.1f}%",
            f"{sb2['avg_win']:+.1f}%")
        row("Media LOSS",
            f"{sv1['avg_loss']:+.1f}%",
            f"{sb2['avg_loss']:+.1f}%")
        print(f"  {sep2}")
        row("PROFITTO TOTALE",
            f"{sv1['total_profit']:+.0f}EUR",
            f"{sb2['total_profit']:+.0f}EUR")
        row("Profitto medio annuo",
            f"{sv1['ann_profit']:+.0f}EUR",
            f"{sb2['ann_profit']:+.0f}EUR")
        row("Rendimento annuo",
            f"{sv1['ann_profit']/CAPITAL*100:.1f}%",
            f"{sb2['ann_profit']/CAPITAL*100:.1f}%")
        print(f"  {sep2}")
        row("Max drawdown",
            f"{sv1['max_dd_pct']:.1f}%",
            f"{sb2['max_dd_pct']:.1f}%")
        row("Max SL consecutivi",
            sv1["max_consec_l"],
            sb2["max_consec_l"])
        print(f"  {sep2}")

        # Vincitore per questo RR
        if sb2["total_profit"] > sv1["total_profit"]:
            delta = sb2["total_profit"] - sv1["total_profit"]
            print(f"  >> RR {rr}:1  BLOOMBERG V2 +{delta:.0f}EUR  "
                  f"(WR: {sb2['win_rate']:.1f}% vs {sv1['win_rate']:.1f}%)")
        elif sv1["total_profit"] > sb2["total_profit"]:
            delta = sv1["total_profit"] - sb2["total_profit"]
            print(f"  >> RR {rr}:1  V1 BASE +{delta:.0f}EUR  "
                  f"(WR: {sv1['win_rate']:.1f}% vs {sb2['win_rate']:.1f}%)")
        else:
            print(f"  >> RR {rr}:1  PAREGGIO")

    # Riepilogo annuale per ogni RR
    print(f"\n{sep}")
    print("  PROFITTO ANNUALE PER R:R")
    print(sep)

    all_rr = sorted(results.keys())
    # Header
    header = f"  {'Anno':<8}"
    for rr in all_rr:
        header += f"  {'V1 R'+str(rr):>10}  {'BL R'+str(rr):>10}"
    print(header)
    print(f"  {'-' * (8 + 24 * len(all_rr))}")

    # Raccogli tutti gli anni presenti
    all_years = set()
    for rr in all_rr:
        all_years.update(results[rr]["v1"]["yearly"].keys())
        all_years.update(results[rr]["bloomberg_v2"]["yearly"].keys())

    for yr in sorted(all_years):
        line = f"  {yr:<8}"
        for rr in all_rr:
            v = results[rr]["v1"]["yearly"].get(yr, 0)
            b = results[rr]["bloomberg_v2"]["yearly"].get(yr, 0)
            line += f"  {v:>+9.0f}E  {b:>+9.0f}E"
        print(line)

    print(sep)

    # Riepilogo totale
    print("\n  RIEPILOGO TOTALE")
    print(f"  {'R:R':<8} {'V1 Profit':>12} {'BL Profit':>12} {'Delta':>10} {'V1 DD':>8} {'BL DD':>8} {'V1 CL':>7} {'BL CL':>7}")
    print(f"  {'-' * 76}")
    for rr in all_rr:
        sv1 = results[rr]["v1"]
        sb2 = results[rr]["bloomberg_v2"]
        delta = sb2["total_profit"] - sv1["total_profit"]
        sign  = "+" if delta >= 0 else ""
        print(f"  {rr}:1     "
              f"  {sv1['total_profit']:>+10.0f}E"
              f"  {sb2['total_profit']:>+10.0f}E"
              f"  {sign}{delta:>8.0f}E"
              f"  {sv1['max_dd_pct']:>6.1f}%"
              f"  {sb2['max_dd_pct']:>6.1f}%"
              f"  {sv1['max_consec_l']:>6}"
              f"  {sb2['max_consec_l']:>6}")
    print(sep)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    all_tickers = WATCHLIST_USA + WATCHLIST_EUROPE

    dl_start = "1999-01-01"
    dl_end   = datetime.today().strftime("%Y-%m-%d")

    print(f"Download dati WEEKLY {BT_START} -> {BT_END}")
    print(f"Ticker: {len(all_tickers)} (USA + Europa, indici esclusi)")
    print(f"Sweep RR: {RR_VALUES}  ->  {len(RR_VALUES)*2} backtest totali")
    print("Tempo stimato: 15-25 minuti...\n")
    all_data = download_all(all_tickers, dl_start, dl_end)
    print(f"Asset scaricati: {len(all_data)}/{len(all_tickers)}\n")

    results = {}

    for rr in RR_VALUES:
        results[rr] = {}

        print(f"--- RR {rr}:1 ---")

        print(f"  Backtest V1 BASE (top 3/settimana, RR={rr})...")
        trades_v1 = run_backtest(all_data, mode="v1", top_n=3, rr=rr)
        trades_v1.to_csv(f"backtest_v1_rr{rr}_results.csv", index=False)
        stats_v1  = compute_stats(trades_v1)
        results[rr]["v1"] = stats_v1
        print(f"    Trade chiusi: {stats_v1['total_trades']}  "
              f"WR: {stats_v1['win_rate']:.1f}%  "
              f"Profitto: {stats_v1['total_profit']:+.0f}EUR")

        print(f"  Backtest BLOOMBERG V2 (top 20 -> re-rank -> top 3, RR={rr})...")
        trades_b2 = run_backtest(all_data, mode="bloomberg_v2", top_n=3, rr=rr)
        trades_b2.to_csv(f"backtest_bloomberg_v2_rr{rr}_results.csv", index=False)
        stats_b2  = compute_stats(trades_b2)
        results[rr]["bloomberg_v2"] = stats_b2
        print(f"    Trade chiusi: {stats_b2['total_trades']}  "
              f"WR: {stats_b2['win_rate']:.1f}%  "
              f"Profitto: {stats_b2['total_profit']:+.0f}EUR")
        print()

    print_rr_sweep(results)

    print("\nFile salvati:")
    for rr in RR_VALUES:
        print(f"  backtest_v1_rr{rr}_results.csv")
        print(f"  backtest_bloomberg_v2_rr{rr}_results.csv")
