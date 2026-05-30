# backtest_v2_adx_ema200.py — confronto V1 vs V2 (ADX14 + EMA200)
#
# V1 = scoring attuale (analyzer.py, in produzione — NON modificato)
# V2 = V1 + contributo ADX14 + contributo EMA200
#
# Scarica dati dal 2015-01-01 per garantire EMA200 disponibile
# dall'inizio del backtest (2020-01-01).

import pandas as pd
import yfinance as yf
from datetime import datetime
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator, ADXIndicator, EMAIndicator
from ta.volatility import AverageTrueRange

# ── Parametri backtest ────────────────────────────────────────────────────────
CAPITAL    = 20_000
TRADE_SIZE = 500
SL_MULT    = 1.5
RR         = 3.0
TOP_N      = 3
MIN_BARS   = 26
SAFETY_CAP = 52
BT_START   = "2020-01-01"
BT_END     = datetime.today().strftime("%Y-%m-%d")
DL_START   = "2015-01-01"   # download più lungo per EMA200

# ── Watchlist cTrader (247 titoli) ────────────────────────────────────────────
WATCHLIST = [
    "AAPL","MSFT","NVDA","GOOGL","GOOG","META","AMZN","TSLA","AVGO",
    "AMD","QCOM","TXN","ADI","MU","AMAT","KLAC","SNPS","CDNS","NXPI","MRVL","INTC",
    "CRM","ADBE","NOW","PANW","INTU","ORCL","IBM","CSCO","FTNT",
    "DDOG","SNOW","OKTA","ZM","TWLO","DOCU","WDAY",
    "NFLX","DIS","SPOT","SHOP","MELI","BKNG","EBAY","UBER","TTD","SNAP","PINS","ROKU",
    "V","MA","PYPL","AXP",
    "LLY","ABBV","MRK","ABT","AMGN","GILD","VRTX","REGN","BMY","PFE","JNJ","MRNA","BIIB","ILMN",
    "UNH","TMO","DHR","ISRG","MDT","BSX","BDX","SYK","ELV","HUM","CI","IDXX","DXCM","EW","CVS","A",
    "JPM","BAC","GS","MS","BLK","C","CB","SCHW","SPGI","MCO","CME","ICE","USB","PGR","PRU","MET",
    "AFL","TRV","PNC","COF","BK",
    "PG","KO","PEP","WMT","COST","PM","MCD","SBUX","KMB","CL","MDLZ","GIS","KR","YUM","HSY",
    "HD","LOW","TJX","NKE","RACE","MAR","HLT","EA","TTWO",
    "XOM","CVX","EOG","COP","OXY","DVN","HAL","SLB","VLO","MPC","PSX","WMB","OKE","KMI",
    "CAT","DE","GE","ETN","HON","ITW","EMR","WM","MMM","RTX","NOC","LMT","LHX","FDX","UPS","CSX","UNP","GD","ROK","CMI",
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


# ── Indicatori V1 (identico a analyzer.py — non importa per non sporcare produzione) ──
def compute_indicators_v1(df: pd.DataFrame) -> dict:
    close  = df["Close"].squeeze()
    high   = df["High"].squeeze()
    low    = df["Low"].squeeze()
    volume = df["Volume"].squeeze()

    rsi     = RSIIndicator(close, window=14).rsi()
    macd_o  = MACD(close, window_slow=26, window_fast=12, window_sign=9)
    sma20   = SMAIndicator(close, window=20).sma_indicator()
    sma50   = SMAIndicator(close, window=50).sma_indicator()
    atr     = AverageTrueRange(high, low, close, window=14).average_true_range()

    last         = float(close.iloc[-1])
    prev         = float(close.iloc[-2]) if len(close) >= 2 else last
    weekly_chg   = (last - prev) / prev * 100
    avg_vol      = float(volume.iloc[-20:].mean())
    vol_ratio    = float(volume.iloc[-1]) / avg_vol if avg_vol > 0 else 1.0

    return {
        "price":            last,
        "weekly_change_pct": weekly_chg,
        "rsi_14":           float(rsi.iloc[-1]),
        "macd_hist":        float(macd_o.macd_diff().iloc[-1]),
        "sma20":            float(sma20.iloc[-1]),
        "sma50":            float(sma50.iloc[-1]),
        "atr_14":           float(atr.iloc[-1]),
        "volume_ratio":     vol_ratio,
        "above_sma20":      last > float(sma20.iloc[-1]),
        "above_sma50":      last > float(sma50.iloc[-1]),
    }


# ── Indicatori V2 = V1 + ADX14 + EMA200 ──────────────────────────────────────
def compute_indicators_v2(df: pd.DataFrame) -> dict:
    ind = compute_indicators_v1(df)

    close = df["Close"].squeeze()
    high  = df["High"].squeeze()
    low   = df["Low"].squeeze()

    # ADX14
    adx_series = ADXIndicator(high, low, close, window=14).adx()
    adx_val    = float(adx_series.iloc[-1])
    ind["adx_14"] = adx_val if not pd.isna(adx_val) else None

    # EMA200 (richiede ~200 barre; se NaN, nessun contributo)
    ema200_series  = EMAIndicator(close, window=200).ema_indicator()
    ema200_val     = float(ema200_series.iloc[-1])
    if pd.isna(ema200_val):
        ind["ema200"]       = None
        ind["above_ema200"] = None
    else:
        ind["ema200"]       = ema200_val
        ind["above_ema200"] = ind["price"] > ema200_val

    return ind


# ── Score V1 (identico a analyzer.py) ─────────────────────────────────────────
def score_v1(ind: dict) -> float:
    score = 0.0
    rsi          = ind.get("rsi_14")
    macd_hist    = ind.get("macd_hist")
    above_sma20  = ind.get("above_sma20")
    above_sma50  = ind.get("above_sma50")
    vol_ratio    = ind.get("volume_ratio", 1.0)
    weekly_chg   = ind.get("weekly_change_pct", 0)

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


# ── Score V2 = V1 + ADX + EMA200 ─────────────────────────────────────────────
def score_v2(ind: dict) -> float:
    score = score_v1(ind)

    # ADX14: forza del trend
    adx = ind.get("adx_14")
    if adx is not None:
        if adx > 25:   score += 2.0   # trend forte
        elif adx > 20: score += 1.0   # trend moderato
        elif adx < 15: score -= 1.0   # mercato laterale, segnale debole

    # EMA200: filtro trend primario di lungo periodo
    above_ema200 = ind.get("above_ema200")
    if above_ema200 is True:
        score += 2.0   # sopra EMA200 = bull market strutturale
    elif above_ema200 is False:
        score -= 1.5   # sotto EMA200 = bear market, evitare Buy

    return score


# ── Download dati ─────────────────────────────────────────────────────────────
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
            return "TIMEOUT", float(future["Close"].iloc[i - 1])
        if float(row["Low"]) <= sl:
            return "LOSS", sl
        if float(row["High"]) >= tp:
            return "WIN", tp
    return ("OPEN", float(future["Close"].iloc[-1])) if len(future) else ("OPEN", entry)


# ── Backtest principale ───────────────────────────────────────────────────────
def run_backtest(all_data, score_fn, indicator_fn):
    signal_dates = pd.date_range(BT_START, BT_END, freq="W-FRI")
    trades = []
    wd = {0: 0, 1: 0, 2: 0, 3: 0}

    for sig_date in signal_dates:
        candidates = []
        for ticker, df in all_data.items():
            hist = df[df.index <= sig_date].tail(250)  # 250 per EMA200
            if len(hist) < MIN_BARS:
                continue
            try:
                ind   = indicator_fn(hist)
                score = score_fn(ind)
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
    closed = df[df["outcome"].isin(["WIN", "LOSS", "TIMEOUT"])].sort_values("date").reset_index(drop=True)
    balance = CAPITAL; peak = CAPITAL; max_dd = 0.0; yearly = {}
    for _, row in closed.iterrows():
        pnl = row["pnl_pct"] / 100 * TRADE_SIZE
        balance += pnl
        if balance > peak: peak = balance
        dd = peak - balance
        if dd > max_dd: max_dd = dd
        yr = int(row["year"])
        yearly[yr] = yearly.get(yr, 0) + pnl

    wins  = (closed["outcome"] == "WIN").sum()
    losses = (closed["outcome"] == "LOSS").sum()
    total  = len(closed)
    years  = (pd.Timestamp(BT_END) - pd.Timestamp(BT_START)).days / 365.25
    max_cl = curr = 0
    for o in closed["outcome"]:
        curr = curr + 1 if o == "LOSS" else 0
        max_cl = max(max_cl, curr)

    return {
        "trades":    total,
        "wins":      int(wins),
        "losses":    int(losses),
        "wr":        wins / total * 100 if total else 0,
        "ev":        closed["pnl_pct"].mean() if total else 0,
        "final_bal": round(balance, 0),
        "total_pnl": round(balance - CAPITAL, 0),
        "ann_ret":   round((balance / CAPITAL) ** (1 / years) * 100 - 100, 1) if years > 0 else 0,
        "max_dd_eur": round(max_dd, 0),
        "max_dd_pct": round(max_dd / peak * 100, 1),
        "max_consec": max_cl,
        "yearly":    yearly,
    }


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Download {len(WATCHLIST)} titoli (dal {DL_START} per EMA200)...")
    all_data = download_all(WATCHLIST, DL_START, BT_END)
    print(f"Scaricati: {len(all_data)}/{len(WATCHLIST)}")

    configs = {
        "V1 (attuale)": (score_v1, compute_indicators_v1),
        "V2 (ADX+EMA200)": (score_v2, compute_indicators_v2),
    }

    results = {}
    for label, (sfn, ifn) in configs.items():
        print(f"Backtest {label}...")
        trades, total_weeks, wd = run_backtest(all_data, sfn, ifn)
        sim = simulate_capital(trades)
        results[label] = (sim, wd, total_weeks)
        print(f"  trade={sim['trades']} | WR={sim['wr']:.1f}% | Finale={sim['final_bal']:,.0f} EUR")

    # ── Stampa tabella di confronto ──────────────────────────────────────────
    labels = list(results.keys())
    sep = "=" * 68
    print(f"\n{sep}")
    print(f"  CONFRONTO V1 vs V2 — Watchlist cTrader ({len(WATCHLIST)} titoli)")
    print(f"  Periodo: {BT_START} -> {BT_END} | Cap {CAPITAL:,}EUR | Trade {TRADE_SIZE}EUR | R:R 3:1")
    print(f"  V2 aggiunge: ADX14 (+2.0/>25, +1.0/>20, -1.0/<15) + EMA200 (+2.0/sopra, -1.5/sotto)")
    print(sep)

    def row(lbl, *vals):
        print(f"  {lbl:<32}" + "".join(f"{str(v):>17}" for v in vals))

    row("Metrica", *labels)
    print("  " + "-" * 66)
    for k, lbl in [("trades","Trade chiusi"),("wins","WIN"),("losses","LOSS")]:
        row(lbl, *[results[lb][0][k] for lb in labels])
    row("Win rate",        *[f"{results[lb][0]['wr']:.1f}%"       for lb in labels])
    row("EV medio/trade",  *[f"{results[lb][0]['ev']:+.2f}%"      for lb in labels])
    print("  " + "-" * 66)
    row("Capitale finale", *[f"{results[lb][0]['final_bal']:,.0f}" for lb in labels])
    row("P&L totale",      *[f"{results[lb][0]['total_pnl']:+,.0f}" for lb in labels])
    row("Rendimento annuo",*[f"{results[lb][0]['ann_ret']:.1f}%"   for lb in labels])
    print("  " + "-" * 66)
    row("Max drawdown EUR",*[f"-{results[lb][0]['max_dd_eur']:,.0f}" for lb in labels])
    row("Max drawdown %",  *[f"-{results[lb][0]['max_dd_pct']:.1f}%" for lb in labels])
    row("Max SL consec.",  *[results[lb][0]["max_consec"]           for lb in labels])
    print(sep)

    tw = results[labels[0]][2]
    print(f"\n  DISTRIBUZIONE SETTIMANE ({tw} totali)")
    row("", *labels)
    print("  " + "-" * 66)
    for n in [0, 1, 2, 3]:
        lbl  = f"{n} trade/settimana"
        vals = [f"{results[lb][1].get(n,0)} ({results[lb][1].get(n,0)/tw*100:.0f}%)" for lb in labels]
        row(lbl, *vals)
    print(sep)

    all_years = sorted(set(yr for lb in labels for yr in results[lb][0]["yearly"]))
    col_w = 18
    header = f"  {'Anno':<8}" + "".join(f"{lb:>{col_w}}" for lb in labels)
    print(f"\n{header}")
    print("  " + "-" * (8 + col_w * len(labels)))
    for yr in all_years:
        line = f"  {yr:<8}"
        for lb in labels:
            v = results[lb][0]["yearly"].get(yr, 0)
            line += f"{v:>+{col_w-4}.0f} EUR    "
        print(line)
    print(sep)

    # ── Verdetto ─────────────────────────────────────────────────────────────
    v1 = results["V1 (attuale)"][0]
    v2 = results["V2 (ADX+EMA200)"][0]
    pnl_diff = v2["total_pnl"] - v1["total_pnl"]
    dd_diff  = v2["max_dd_pct"] - v1["max_dd_pct"]

    print(f"\n  VERDETTO:")
    print(f"  P&L V2 vs V1:        {pnl_diff:+,.0f} EUR")
    print(f"  Ann. return V2 vs V1: {v2['ann_ret'] - v1['ann_ret']:+.1f}%")
    print(f"  Max DD V2 vs V1:      {dd_diff:+.1f}% (negativo = miglioramento)")
    print(f"  Trade V2 vs V1:       {v2['trades'] - v1['trades']:+d}")
    if v2["total_pnl"] > v1["total_pnl"] and v2["max_dd_pct"] <= v1["max_dd_pct"]:
        print(f"\n  >> V2 MIGLIORE: piu' redditizio E drawdown non peggiore. Consigliato.")
    elif v2["total_pnl"] > v1["total_pnl"]:
        print(f"\n  >> V2 PIU' REDDITIZIO ma drawdown maggiore. Valutare risk/reward.")
    elif v2["max_dd_pct"] < v1["max_dd_pct"]:
        print(f"\n  >> V2 MENO REDDITIZIO ma drawdown ridotto. Preferire V1 per rendimento.")
    else:
        print(f"\n  >> V1 MIGLIORE: mantenere configurazione attuale.")
    print(sep)
