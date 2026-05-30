# backtest_minscore_all.py — confronto MIN_SCORE 0 / 6 / 8
import pandas as pd
import yfinance as yf
from datetime import datetime
from analyzer import compute_indicators, score_stock

CAPITAL    = 20_000
TRADE_SIZE = 500
SL_MULT    = 1.5
RR         = 3.0
TOP_N      = 3
MIN_BARS   = 26
SAFETY_CAP = 52
BT_START   = "2020-01-01"
BT_END     = datetime.today().strftime("%Y-%m-%d")

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


def simulate_trade(future, entry, sl, tp):
    for i, (_, row) in enumerate(future.iterrows()):
        if i >= SAFETY_CAP:
            return "TIMEOUT", float(future["Close"].iloc[i - 1])
        if float(row["Low"]) <= sl:
            return "LOSS", sl
        if float(row["High"]) >= tp:
            return "WIN", tp
    return ("OPEN", float(future["Close"].iloc[-1])) if len(future) else ("OPEN", entry)


def run_backtest(all_data, min_score):
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
                score = score_stock(ind)
                if score > min_score and (ind.get("macd_hist") or 0) > 0:
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
    wins   = (closed["outcome"] == "WIN").sum()
    losses = (closed["outcome"] == "LOSS").sum()
    total  = len(closed)
    years  = (pd.Timestamp(BT_END) - pd.Timestamp(BT_START)).days / 365.25
    max_cl = curr = 0
    for o in closed["outcome"]:
        curr = curr + 1 if o == "LOSS" else 0
        max_cl = max(max_cl, curr)
    return {
        "trades": total, "wins": int(wins), "losses": int(losses),
        "wr":  wins / total * 100 if total else 0,
        "ev":  closed["pnl_pct"].mean() if total else 0,
        "final_bal":  round(balance, 0),
        "total_pnl":  round(balance - CAPITAL, 0),
        "ann_ret":    round((balance / CAPITAL) ** (1 / years) * 100 - 100, 1) if years > 0 else 0,
        "max_dd_eur": round(max_dd, 0),
        "max_dd_pct": round(max_dd / peak * 100, 1),
        "max_consec": max_cl,
        "yearly":     yearly,
    }


if __name__ == "__main__":
    print(f"Download {len(WATCHLIST)} titoli...")
    all_data = download_all(WATCHLIST, "2019-01-01", BT_END)
    print(f"Scaricati: {len(all_data)}/{len(WATCHLIST)}")

    results = {}
    for ms in [0, 6, 8]:
        print(f"Backtest MIN_SCORE={ms}...")
        trades, total_weeks, wd = run_backtest(all_data, ms)
        sim = simulate_capital(trades)
        results[ms] = (sim, wd, total_weeks)
        print(f"  trade={sim['trades']} | WR={sim['wr']:.1f}% | Finale={sim['final_bal']:,.0f} EUR")

    sep = "=" * 68
    print(f"\n{sep}")
    print(f"  CONFRONTO MIN_SCORE 0 / 6 / 8 — Watchlist cTrader ({len(WATCHLIST)} titoli)")
    print(f"  Periodo: {BT_START} -> {BT_END} | Cap {CAPITAL:,}EUR | Trade {TRADE_SIZE}EUR | R:R 3:1")
    print(sep)

    def row(lbl, *vals):
        print(f"  {lbl:<30}" + "".join(f"{str(v):>12}" for v in vals))

    row("Metrica", "score>0", "score>6", "score>8")
    print("  " + "-" * 66)
    for k, lbl in [("trades","Trade chiusi"),("wins","WIN"),("losses","LOSS")]:
        row(lbl, *[results[ms][0][k] for ms in [0, 6, 8]])
    row("Win rate",        *[f"{results[ms][0]['wr']:.1f}%"       for ms in [0, 6, 8]])
    row("EV medio/trade",  *[f"{results[ms][0]['ev']:+.2f}%"      for ms in [0, 6, 8]])
    print("  " + "-" * 66)
    row("Capitale finale", *[f"{results[ms][0]['final_bal']:,.0f}" for ms in [0, 6, 8]])
    row("P&L totale",      *[f"{results[ms][0]['total_pnl']:+,.0f}" for ms in [0, 6, 8]])
    row("Rendimento annuo",*[f"{results[ms][0]['ann_ret']:.1f}%"   for ms in [0, 6, 8]])
    print("  " + "-" * 66)
    row("Max drawdown EUR",*[f"-{results[ms][0]['max_dd_eur']:,.0f}" for ms in [0, 6, 8]])
    row("Max drawdown %",  *[f"-{results[ms][0]['max_dd_pct']:.1f}%" for ms in [0, 6, 8]])
    row("Max SL consec.",  *[results[ms][0]["max_consec"]           for ms in [0, 6, 8]])
    print(sep)

    tw = results[0][2]
    print(f"\n  DISTRIBUZIONE SETTIMANE ({tw} totali)")
    row("", "score>0", "score>6", "score>8")
    print("  " + "-" * 66)
    for n in [0, 1, 2, 3]:
        lbl = f"{n} trade/settimana"
        vals = [f"{results[ms][1].get(n,0)} ({results[ms][1].get(n,0)/tw*100:.0f}%)" for ms in [0, 6, 8]]
        row(lbl, *vals)
    print(sep)

    all_years = sorted(set(yr for ms in [0, 6, 8] for yr in results[ms][0]["yearly"]))
    print(f"\n  Anno       score>0      score>6      score>8")
    print("  " + "-" * 50)
    for yr in all_years:
        vals = [results[ms][0]["yearly"].get(yr, 0) for ms in [0, 6, 8]]
        print(f"  {yr}  {vals[0]:>+9.0f} EUR  {vals[1]:>+9.0f} EUR  {vals[2]:>+9.0f} EUR")
    print(sep)
