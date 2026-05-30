# backtest_v3_insider.py
# V1 (attuale) vs V3 (V1 + insider signal da Form 4 SEC EDGAR)
#
# Segnale insider aggiunto solo per ticker USA.
# Ticker europei usano score V1 invariato.
#
# Prerequisito: eseguire sec_insider_fetcher.py per generare
#   sec_cache/insider_transactions.csv

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator
from ta.volatility import AverageTrueRange
import os

# ── Parametri ────────────────────────────────────────────────────────────────
CAPITAL    = 20_000
TRADE_SIZE = 500
SL_MULT    = 1.5
RR         = 3.0
TOP_N      = 3
MIN_BARS   = 26
SAFETY_CAP = 52
BT_START   = "2020-01-01"
BT_END     = datetime.today().strftime("%Y-%m-%d")
DL_START   = "2019-01-01"

INSIDER_CSV = r"C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot\sec_cache\insider_transactions.csv"
INSIDER_LOOKBACK_DAYS = 60   # finestra temporale per insider signal

# ── Watchlist (247 titoli) ────────────────────────────────────────────────────
WATCHLIST = [
    "AAPL","MSFT","NVDA","GOOGL","GOOG","META","AMZN","TSLA","AVGO",
    "AMD","QCOM","TXN","ADI","MU","AMAT","KLAC","SNPS","CDNS","NXPI","MRVL","INTC",
    "CRM","ADBE","NOW","PANW","INTU","ORCL","IBM","CSCO","FTNT",
    "DDOG","SNOW","OKTA","ZM","TWLO","DOCU","WDAY",
    "NFLX","DIS","SPOT","SHOP","MELI","BKNG","EBAY","UBER","TTD","SNAP","PINS","ROKU",
    "V","MA","PYPL","AXP",
    "LLY","ABBV","MRK","ABT","AMGN","GILD","VRTX","REGN","BMY","PFE","JNJ","MRNA",
    "BIIB","ILMN","UNH","TMO","DHR","ISRG","MDT","BSX","BDX","SYK","ELV","HUM","CI",
    "IDXX","DXCM","EW","CVS","A",
    "JPM","BAC","GS","MS","BLK","C","CB","SCHW","SPGI","MCO","CME","ICE","USB",
    "PGR","PRU","MET","AFL","TRV","PNC","COF","BK",
    "PG","KO","PEP","WMT","COST","PM","MCD","SBUX","KMB","CL","MDLZ","GIS","KR",
    "YUM","HSY","HD","LOW","TJX","NKE","RACE","MAR","HLT","EA","TTWO",
    "XOM","CVX","EOG","COP","OXY","DVN","HAL","SLB","VLO","MPC","PSX","WMB","OKE","KMI",
    "CAT","DE","GE","ETN","HON","ITW","EMR","WM","MMM","RTX","NOC","LMT","LHX",
    "FDX","UPS","CSX","UNP","GD","ROK","CMI",
    "SHW","DOW","DD","LYB","ECL","FCX","NEM","PPG",
    "NEE","DUK","SO","D","EXC","AEP","DTE","SRE",
    "PLD","EQIX","AMT","CCI","PSA","EQR","AVB","TSM",
    "ADS.DE","ALV.DE","BAS.DE","BAYN.DE","BEI.DE","BMW.DE","CON.DE","DBK.DE","DB1.DE",
    "EOAN.DE","FRE.DE","HEN3.DE","IFX.DE","MRK.DE","MTX.DE","MUV2.DE","RWE.DE","SAP.DE",
    "SIE.DE","SHL.DE","VNA.DE","VOW3.DE",
    "AGN.AS","ASM.AS","ASML.AS","HEIA.AS","IMCD.AS","NN.AS","PHIA.AS","RAND.AS","AD.AS","WKL.AS",
    "AI.PA","AIR.PA","BNP.PA","GLE.PA","KER.PA","MC.PA","OR.PA","PUB.PA","RMS.PA","SAN.PA","SU.PA","TTE.PA",
    "ACS.MC","ANA.MC","BBVA.MC","IBE.MC","ITX.MC","REP.MC","SAN.MC",
    "BARC.L","BP.L","GLEN.L","GSK.L","HSBA.L","LLOY.L","NWG.L","RIO.L","SHEL.L","STAN.L",
]

US_TICKERS = set(t for t in WATCHLIST if "." not in t)


# ── Indicatori V1 ─────────────────────────────────────────────────────────────
def compute_indicators(df):
    close  = df["Close"].squeeze()
    high   = df["High"].squeeze()
    low    = df["Low"].squeeze()
    volume = df["Volume"].squeeze()

    rsi    = RSIIndicator(close, window=14).rsi()
    macd_o = MACD(close, window_slow=26, window_fast=12, window_sign=9)
    sma20  = SMAIndicator(close, window=20).sma_indicator()
    sma50  = SMAIndicator(close, window=50).sma_indicator()
    atr    = AverageTrueRange(high, low, close, window=14).average_true_range()

    last       = float(close.iloc[-1])
    prev       = float(close.iloc[-2]) if len(close) >= 2 else last
    weekly_chg = (last - prev) / prev * 100
    avg_vol    = float(volume.iloc[-20:].mean())
    vol_ratio  = float(volume.iloc[-1]) / avg_vol if avg_vol > 0 else 1.0

    return {
        "price":             last,
        "weekly_change_pct": weekly_chg,
        "rsi_14":            float(rsi.iloc[-1]),
        "macd_hist":         float(macd_o.macd_diff().iloc[-1]),
        "sma20":             float(sma20.iloc[-1]),
        "sma50":             float(sma50.iloc[-1]),
        "atr_14":            float(atr.iloc[-1]),
        "volume_ratio":      vol_ratio,
        "above_sma20":       last > float(sma20.iloc[-1]),
        "above_sma50":       last > float(sma50.iloc[-1]),
    }


# ── Score V1 ──────────────────────────────────────────────────────────────────
def score_v1(ind):
    score = 0.0
    rsi         = ind.get("rsi_14")
    macd_hist   = ind.get("macd_hist")
    above_sma20 = ind.get("above_sma20")
    above_sma50 = ind.get("above_sma50")
    vol_ratio   = ind.get("volume_ratio", 1.0)
    weekly_chg  = ind.get("weekly_change_pct", 0)

    if rsi is not None:
        if 40 <= rsi <= 65:  score += 2.0
        elif rsi < 40:       score += 0.5
        elif rsi > 70:       score -= 2.0

    if macd_hist is not None:
        score += 2.0 if macd_hist > 0 else -1.0

    if above_sma20: score += 1.0
    if above_sma50: score += 1.5

    if vol_ratio > 1.2:   score += 1.0
    elif vol_ratio > 1.0: score += 0.5

    if weekly_chg > 2:    score += 1.0
    elif weekly_chg > 0:  score += 0.5

    return score


# ── Insider score da Form 4 ───────────────────────────────────────────────────
def build_insider_index(insider_df):
    """
    Crea un dizionario ticker → DataFrame delle transazioni,
    con date come pd.Timestamp per lookup veloce.
    """
    idx = {}
    for ticker, grp in insider_df.groupby("ticker"):
        grp = grp.copy()
        grp["filed_date"] = pd.to_datetime(grp["filed_date"])
        # Usa solo transazioni open-market (P=purchase, S=sale)
        grp = grp[grp["is_open_market"] == True]
        idx[ticker] = grp.reset_index(drop=True)
    return idx


def compute_insider_score(ticker, signal_date, insider_idx, lookback_days=60):
    """
    Calcola il contributo insider allo score alla data del segnale.
    Usa solo filings disponibili PRIMA della signal_date (no look-ahead).
    """
    if ticker not in insider_idx:
        return 0.0

    grp = insider_idx[ticker]
    cutoff_start = signal_date - timedelta(days=lookback_days)

    # Filtra: filing arrivato PRIMA del segnale (no look-ahead)
    window = grp[(grp["filed_date"] >= cutoff_start) &
                 (grp["filed_date"] <  signal_date)]

    if window.empty:
        return 0.0

    buys  = window[window["transaction_code"] == "P"]
    sells = window[window["transaction_code"] == "S"]

    buy_count  = len(buys)
    sell_count = len(sells)

    # Ruoli pesati
    ceo_cfo_buy  = buys[buys["role"].isin(["CEO","CFO","PRESIDENT"])]
    ceo_cfo_sell = sells[sells["role"].isin(["CEO","CFO","PRESIDENT"])]

    score = 0.0

    # ── Segnali rialzisti ────────────────────────────────────────────────────
    if buy_count >= 3:
        score += 2.5   # cluster buying forte
    elif buy_count == 2:
        score += 1.5   # 2 insider comprano
    elif buy_count == 1:
        score += 1.0   # 1 insider compra

    if not ceo_cfo_buy.empty:
        score += 1.5   # CEO/CFO compra: segnale molto forte

    # Volume acquistato (bonus se > $500k)
    total_buy_value = (buys["shares"] * buys["price_per_share"]).sum()
    if total_buy_value > 500_000:
        score += 1.0
    elif total_buy_value > 100_000:
        score += 0.5

    # ── Segnali ribassisti ───────────────────────────────────────────────────
    if sell_count >= 3:
        score -= 1.5   # cluster selling (meno informativo, può essere diversificazione)
    elif sell_count >= 2:
        score -= 0.75

    if not ceo_cfo_sell.empty and ceo_cfo_buy.empty:
        score -= 1.0   # CEO/CFO vende senza comprare nulla

    return score


# ── Download dati OHLCV ───────────────────────────────────────────────────────
def download_all(tickers, start, end):
    data = {}
    for i, t in enumerate(tickers, 1):
        print(f"\r  {i}/{len(tickers)}: {t:<16}", end="", flush=True)
        try:
            df = yf.download(t, start=start, end=end, interval="1wk",
                             progress=False, auto_adjust=True)
            if not df.empty:
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                data[t] = df
        except Exception:
            pass
    print()
    return data


# ── Simulazione singolo trade ─────────────────────────────────────────────────
def simulate_trade(future, entry, sl, tp):
    for i, (_, row) in enumerate(future.iterrows()):
        if i >= SAFETY_CAP:
            return "TIMEOUT", float(future["Close"].iloc[i-1])
        if float(row["Low"]) <= sl:
            return "LOSS", sl
        if float(row["High"]) >= tp:
            return "WIN", tp
    return ("OPEN", float(future["Close"].iloc[-1])) if len(future) else ("OPEN", entry)


# ── Backtest ──────────────────────────────────────────────────────────────────
def run_backtest(all_data, score_fn, insider_idx=None):
    signal_dates = pd.date_range(BT_START, BT_END, freq="W-FRI")
    trades = []
    wd = {0: 0, 1: 0, 2: 0, 3: 0}

    for sig_date in signal_dates:
        candidates = []
        for ticker, df in all_data.items():
            hist = df[df.index <= sig_date].tail(200)
            if len(hist) < MIN_BARS:
                continue
            try:
                ind   = compute_indicators(hist)
                score = score_fn(ind)

                # Aggiungi segnale insider (solo per ticker USA)
                if insider_idx is not None and ticker in US_TICKERS:
                    score += compute_insider_score(ticker, sig_date.to_pydatetime(),
                                                   insider_idx, INSIDER_LOOKBACK_DAYS)

                if score > 0 and (ind.get("macd_hist") or 0) > 0:
                    candidates.append((ticker, ind, score))
            except Exception:
                continue

        candidates.sort(key=lambda x: x[2], reverse=True)
        selected = candidates[:TOP_N]
        wd[min(len(selected), 3)] += 1

        for ticker, ind, score in selected:
            entry  = ind["price"]
            atr    = ind.get("atr_14") or (entry * 0.02)
            sl     = round(entry - SL_MULT * atr, 4)
            tp     = round(entry + RR * SL_MULT * atr, 4)
            future = all_data[ticker][all_data[ticker].index > sig_date]
            if future.empty:
                continue
            outcome, exit_price = simulate_trade(future, entry, sl, tp)
            trades.append({
                "date":    sig_date,
                "year":    sig_date.year,
                "ticker":  ticker,
                "score":   round(score, 2),
                "outcome": outcome,
                "pnl_pct": round((exit_price - entry) / entry * 100, 2),
            })

    return pd.DataFrame(trades), len(signal_dates), wd


# ── Statistiche ───────────────────────────────────────────────────────────────
def simulate_capital(df):
    closed = df[df["outcome"].isin(["WIN","LOSS","TIMEOUT"])].sort_values("date").reset_index(drop=True)
    balance = CAPITAL; peak = CAPITAL; max_dd = 0.0; yearly = {}
    for _, row in closed.iterrows():
        pnl = row["pnl_pct"] / 100 * TRADE_SIZE
        balance += pnl
        if balance > peak: peak = balance
        dd = peak - balance
        if dd > max_dd: max_dd = dd
        yr = int(row["year"])
        yearly[yr] = yearly.get(yr, 0) + pnl

    wins   = (closed["outcome"] == "WIN").sum()
    losses = (closed["outcome"] == "LOSS").sum()
    total  = len(closed)
    years  = (pd.Timestamp(BT_END) - pd.Timestamp(BT_START)).days / 365.25
    max_cl = curr = 0
    for o in closed["outcome"]:
        curr = curr + 1 if o == "LOSS" else 0
        max_cl = max(max_cl, curr)

    return {
        "trades":     total,
        "wins":       int(wins),
        "losses":     int(losses),
        "wr":         wins / total * 100 if total else 0,
        "ev":         closed["pnl_pct"].mean() if total else 0,
        "final_bal":  round(balance, 0),
        "total_pnl":  round(balance - CAPITAL, 0),
        "ann_ret":    round((balance/CAPITAL)**(1/years)*100-100, 1) if years > 0 else 0,
        "max_dd_eur": round(max_dd, 0),
        "max_dd_pct": round(max_dd/peak*100, 1),
        "max_consec": max_cl,
        "yearly":     yearly,
    }


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Carica dati insider
    if not os.path.exists(INSIDER_CSV):
        print(f"ERRORE: file insider non trovato: {INSIDER_CSV}")
        print("Esegui prima: python sec_insider_fetcher.py")
        exit(1)

    print("Caricamento dati insider...")
    insider_raw = pd.read_csv(INSIDER_CSV)
    insider_idx = build_insider_index(insider_raw)
    print(f"  Ticker con dati insider: {len(insider_idx)}")
    print(f"  Transazioni totali (open market): "
          f"{sum(len(v) for v in insider_idx.values()):,}")

    print(f"\nDownload {len(WATCHLIST)} titoli (dal {DL_START})...")
    all_data = download_all(WATCHLIST, DL_START, BT_END)
    print(f"Scaricati: {len(all_data)}/{len(WATCHLIST)}")

    configs = {
        "V1 (attuale)":    (score_v1, None),
        "V3 (+Insider)":   (score_v1, insider_idx),
    }

    results = {}
    for label, (sfn, idx) in configs.items():
        print(f"Backtest {label}...")
        trades, total_weeks, wd = run_backtest(all_data, sfn, idx)
        sim = simulate_capital(trades)
        results[label] = (sim, wd, total_weeks)
        print(f"  trade={sim['trades']} | WR={sim['wr']:.1f}% | "
              f"Finale={sim['final_bal']:,.0f} EUR | Ann={sim['ann_ret']:.1f}%")

    # ── Tabella confronto ────────────────────────────────────────────────────
    labels = list(results.keys())
    sep = "=" * 68
    print(f"\n{sep}")
    print(f"  CONFRONTO V1 vs V3 (+Insider SEC) — {len(WATCHLIST)} titoli")
    print(f"  Periodo: {BT_START} -> {BT_END} | Cap {CAPITAL:,}EUR | R:R 3:1")
    print(f"  Insider: lookback {INSIDER_LOOKBACK_DAYS}gg | solo ticker USA ({len(US_TICKERS)})")
    print(sep)

    def row(lbl, *vals):
        print(f"  {lbl:<32}" + "".join(f"{str(v):>17}" for v in vals))

    row("Metrica", *labels)
    print("  " + "-"*66)
    for k, lbl in [("trades","Trade chiusi"),("wins","WIN"),("losses","LOSS")]:
        row(lbl, *[results[lb][0][k] for lb in labels])
    row("Win rate",        *[f"{results[lb][0]['wr']:.1f}%"        for lb in labels])
    row("EV medio/trade",  *[f"{results[lb][0]['ev']:+.2f}%"       for lb in labels])
    print("  " + "-"*66)
    row("Capitale finale", *[f"{results[lb][0]['final_bal']:,.0f}"  for lb in labels])
    row("P&L totale",      *[f"{results[lb][0]['total_pnl']:+,.0f}" for lb in labels])
    row("Rendimento annuo",*[f"{results[lb][0]['ann_ret']:.1f}%"    for lb in labels])
    print("  " + "-"*66)
    row("Max DD EUR",      *[f"-{results[lb][0]['max_dd_eur']:,.0f}" for lb in labels])
    row("Max DD %",        *[f"-{results[lb][0]['max_dd_pct']:.1f}%" for lb in labels])
    row("Max SL consec.",  *[results[lb][0]["max_consec"]            for lb in labels])
    print(sep)

    all_years = sorted(set(yr for lb in labels for yr in results[lb][0]["yearly"]))
    col_w = 18
    print(f"\n  {'Anno':<8}" + "".join(f"{lb:>{col_w}}" for lb in labels))
    print("  " + "-" * (8 + col_w * len(labels)))
    for yr in all_years:
        line = f"  {yr:<8}"
        for lb in labels:
            v = results[lb][0]["yearly"].get(yr, 0)
            line += f"{v:>+{col_w-4}.0f} EUR    "
        print(line)
    print(sep)

    # Verdetto
    v1 = results["V1 (attuale)"][0]
    v3 = results["V3 (+Insider)"][0]
    pnl_diff = v3["total_pnl"] - v1["total_pnl"]
    dd_diff  = v3["max_dd_pct"] - v1["max_dd_pct"]
    print(f"\n  VERDETTO:")
    print(f"  P&L V3 vs V1:         {pnl_diff:+,.0f} EUR")
    print(f"  Ann. return V3 vs V1: {v3['ann_ret'] - v1['ann_ret']:+.1f}%")
    print(f"  Max DD V3 vs V1:      {dd_diff:+.1f}% (neg = miglioramento)")

    if v3["total_pnl"] > v1["total_pnl"] and v3["max_dd_pct"] <= v1["max_dd_pct"]:
        print("  >> V3 MIGLIORE su entrambe le dimensioni. Valutare deploy.")
    elif v3["total_pnl"] > v1["total_pnl"]:
        print("  >> V3 piu redditizio ma DD maggiore. Valutare tradeoff.")
    else:
        print("  >> V1 rimane migliore. Segnale insider non aggiunge valore.")
    print(sep)
