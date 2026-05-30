# simulate_minscore_compare.py
# Confronto MIN_SCORE su watchlist cTrader (produzione attuale)
#   A = V1 attuale  — MIN_SCORE=0  (forza sempre top 3)
#   B = V1 filtrato — MIN_SCORE=6  (apre solo se score > 6)
# Periodo: 2020-01-01 -> oggi | Cap: 20.000EUR | Trade: 500EUR | R:R 3:1

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

BT_START = "2020-01-01"
BT_END   = datetime.today().strftime("%Y-%m-%d")

# Watchlist cTrader (produzione) — stessa di config.py aggiornato
WATCHLIST_CT_USA = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "META", "AMZN", "TSLA", "AVGO",
    "AMD", "QCOM", "TXN", "ADI", "MU", "AMAT", "KLAC", "SNPS", "CDNS",
    "NXPI", "MRVL", "INTC",
    "CRM", "ADBE", "NOW", "PANW", "INTU", "ORCL", "IBM", "CSCO", "FTNT",
    "DDOG", "SNOW", "OKTA", "ZM", "TWLO", "DOCU", "WDAY",
    "NFLX", "DIS", "SPOT", "SHOP", "MELI", "BKNG", "EBAY", "UBER",
    "TTD", "SNAP", "PINS", "ROKU",
    "V", "MA", "PYPL", "AXP",
    "LLY", "ABBV", "MRK", "ABT", "AMGN", "GILD", "VRTX", "REGN",
    "BMY", "PFE", "JNJ", "MRNA", "BIIB", "ILMN",
    "UNH", "TMO", "DHR", "ISRG", "MDT", "BSX", "BDX", "SYK",
    "ELV", "HUM", "CI", "IDXX", "DXCM", "EW", "CVS", "A",
    "JPM", "BAC", "GS", "MS", "BLK", "C", "CB", "SCHW",
    "SPGI", "MCO", "CME", "ICE", "USB", "PGR", "PRU", "MET",
    "AFL", "TRV", "PNC", "COF", "BK",
    "PG", "KO", "PEP", "WMT", "COST", "PM", "MCD", "SBUX",
    "KMB", "CL", "MDLZ", "GIS", "KR", "YUM", "HSY",
    "HD", "LOW", "TJX", "NKE", "RACE", "MAR", "HLT", "EA", "TTWO",
    "XOM", "CVX", "EOG", "COP", "OXY", "DVN", "HAL", "SLB",
    "VLO", "MPC", "PSX", "WMB", "OKE", "KMI",
    "CAT", "DE", "GE", "ETN", "HON", "ITW", "EMR", "WM", "MMM",
    "RTX", "NOC", "LMT", "LHX", "FDX", "UPS", "CSX", "UNP", "GD", "ROK", "CMI",
    "SHW", "DOW", "DD", "LYB", "ECL", "FCX", "NEM", "PPG",
    "NEE", "DUK", "SO", "D", "EXC", "AEP", "DTE", "SRE",
    "PLD", "EQIX", "AMT", "CCI", "PSA", "EQR", "AVB",
    "TSM",
]

WATCHLIST_CT_EUR = [
    "ADS.DE", "ALV.DE", "BAS.DE", "BAYN.DE", "BEI.DE", "BMW.DE",
    "CON.DE", "DBK.DE", "DB1.DE", "EOAN.DE", "FRE.DE", "HEN3.DE",
    "IFX.DE", "MRK.DE", "MTX.DE", "MUV2.DE", "RWE.DE", "SAP.DE",
    "SIE.DE", "SHL.DE", "VNA.DE", "VOW3.DE",
    "AGN.AS", "ASM.AS", "ASML.AS", "HEIA.AS", "IMCD.AS", "NN.AS",
    "PHIA.AS", "RAND.AS", "AD.AS", "WKL.AS",
    "AI.PA", "AIR.PA", "BNP.PA", "GLE.PA", "KER.PA", "MC.PA",
    "OR.PA", "PUB.PA", "RMS.PA", "SAN.PA", "SU.PA", "TTE.PA",
    "ACS.MC", "ANA.MC", "BBVA.MC", "IBE.MC", "ITX.MC", "REP.MC", "SAN.MC",
    "BARC.L", "BP.L", "GLEN.L", "GSK.L", "HSBA.L", "LLOY.L",
    "NWG.L", "RIO.L", "SHEL.L", "STAN.L",
]

WATCHLIST = WATCHLIST_CT_USA + WATCHLIST_CT_EUR


# ---------------------------------------------------------------------------
def download_all(tickers, start, end):
    data = {}
    for i, t in enumerate(tickers, 1):
        print(f"\r  {i}/{len(tickers)}: {t:<16}", end="", flush=True)
        try:
            df = yf.download(t, start=start, end=end,
                             interval="1wk", progress=False, auto_adjust=True)
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
    if len(future):
        return "OPEN", float(future["Close"].iloc[-1])
    return "OPEN", entry


def run_backtest(all_data, min_score=0.0):
    signal_dates = pd.date_range(BT_START, BT_END, freq="W-FRI")
    trades = []
    weeks_0 = weeks_1 = weeks_2 = weeks_3 = 0

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
        n = len(selected)
        if   n == 0: weeks_0 += 1
        elif n == 1: weeks_1 += 1
        elif n == 2: weeks_2 += 1
        else:        weeks_3 += 1

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

    total_weeks = len(signal_dates)
    week_dist = {
        "0 trade": weeks_0,
        "1 trade": weeks_1,
        "2 trade": weeks_2,
        "3 trade": weeks_3,
    }
    return pd.DataFrame(trades), total_weeks, week_dist


def simulate_capital(trades_df):
    closed = trades_df[trades_df["outcome"].isin(["WIN", "LOSS", "TIMEOUT"])].copy()
    closed = closed.sort_values("date").reset_index(drop=True)
    balance = CAPITAL
    peak    = CAPITAL
    max_dd  = 0.0
    yearly  = {}
    for _, row in closed.iterrows():
        pnl_eur  = row["pnl_pct"] / 100 * TRADE_SIZE
        balance += pnl_eur
        if balance > peak:
            peak = balance
        dd = peak - balance
        if dd > max_dd:
            max_dd = dd
        yr = int(row["year"])
        yearly[yr] = yearly.get(yr, 0) + pnl_eur

    wins   = (closed["outcome"] == "WIN").sum()
    losses = (closed["outcome"] == "LOSS").sum()
    total  = len(closed)
    years  = (pd.Timestamp(BT_END) - pd.Timestamp(BT_START)).days / 365.25

    max_cl = curr = 0
    for o in closed["outcome"]:
        if o == "LOSS":
            curr += 1; max_cl = max(max_cl, curr)
        else:
            curr = 0

    return {
        "trades":     total,
        "wins":       int(wins),
        "losses":     int(losses),
        "wr":         wins / total * 100 if total else 0,
        "ev":         closed["pnl_pct"].mean() if total else 0,
        "final_bal":  round(balance, 0),
        "total_pnl":  round(balance - CAPITAL, 0),
        "ann_ret":    round((balance / CAPITAL) ** (1 / years) * 100 - 100, 1) if years > 0 else 0,
        "max_dd_eur": round(max_dd, 0),
        "max_dd_pct": round(max_dd / peak * 100, 1),
        "max_consec": max_cl,
        "yearly":     yearly,
    }


def print_report(sim_a, sim_b, wd_a, wd_b, total_weeks):
    sep  = "=" * 64
    sep2 = "-" * 60
    la   = "V1 attuale (score>0)"
    lb   = "V1 filtrato (score>6)"
    print(f"\n{sep}")
    print(f"  CONFRONTO MIN_SCORE — Watchlist cTrader ({len(WATCHLIST)} titoli)")
    print(f"  Periodo: {BT_START} -> {BT_END}")
    print(f"  R:R 3:1 | SL=1.5xATR | Cap {CAPITAL:,}EUR | Trade {TRADE_SIZE}EUR")
    print(sep)

    def row(label, va, vb):
        print(f"  {label:<32}{str(va):>15}{str(vb):>15}")

    row("Trade chiusi",          sim_a["trades"],                  sim_b["trades"])
    row("Trade in meno (score6)","-",
        f"-{sim_a['trades']-sim_b['trades']}")
    row("WIN",                   sim_a["wins"],                    sim_b["wins"])
    row("LOSS",                  sim_a["losses"],                  sim_b["losses"])
    row("Win rate",              f"{sim_a['wr']:.1f}%",            f"{sim_b['wr']:.1f}%")
    row("EV medio/trade",        f"{sim_a['ev']:+.2f}%",           f"{sim_b['ev']:+.2f}%")
    print(f"  {sep2}")
    row("Capitale finale",       f"{sim_a['final_bal']:,.0f} EUR", f"{sim_b['final_bal']:,.0f} EUR")
    row("P&L totale",            f"{sim_a['total_pnl']:+,.0f} EUR",f"{sim_b['total_pnl']:+,.0f} EUR")
    row("Rendimento annuo",      f"{sim_a['ann_ret']:.1f}%",       f"{sim_b['ann_ret']:.1f}%")
    print(f"  {sep2}")
    row("Max drawdown EUR",      f"-{sim_a['max_dd_eur']:,.0f} EUR",f"-{sim_b['max_dd_eur']:,.0f} EUR")
    row("Max drawdown %",        f"-{sim_a['max_dd_pct']:.1f}%",   f"-{sim_b['max_dd_pct']:.1f}%")
    row("Max SL consecutivi",    sim_a["max_consec"],              sim_b["max_consec"])
    print(sep)

    # Distribuzione settimane per numero di trade
    print(f"\n  DISTRIBUZIONE SETTIMANE ({total_weeks} totali)")
    print(f"  {'':32}{'score>0':>15}{'score>6':>15}")
    print(f"  {sep2}")
    for k in ["0 trade", "1 trade", "2 trade", "3 trade"]:
        va = wd_a.get(k, 0)
        vb = wd_b.get(k, 0)
        pct_a = va / total_weeks * 100
        pct_b = vb / total_weeks * 100
        print(f"  {k:<32}{va:>8} ({pct_a:.0f}%){vb:>8} ({pct_b:.0f}%)")
    print(sep)

    # Anno per anno
    all_years = sorted(set(list(sim_a["yearly"]) + list(sim_b["yearly"])))
    print(f"\n  {'Anno':<8}{'score>0':>15}{'score>6':>15}{'Diff':>12}")
    print(f"  {'-'*50}")
    for yr in all_years:
        pa = sim_a["yearly"].get(yr, 0)
        pb = sim_b["yearly"].get(yr, 0)
        print(f"  {yr:<8}{pa:>+12.0f} EUR{pb:>+12.0f} EUR{pb-pa:>+10.0f} EUR")
    print(sep)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    dl_start = "2019-01-01"

    print(f"Watchlist cTrader: {len(WATCHLIST_CT_USA)} USA + {len(WATCHLIST_CT_EUR)} Europa = {len(WATCHLIST)} titoli")
    print(f"Periodo backtest: {BT_START} -> {BT_END}")
    print(f"\n[1/3] Download dati WEEKLY {dl_start} -> {BT_END}...")
    all_data = download_all(WATCHLIST, dl_start, BT_END)
    print(f"  Scaricati: {len(all_data)}/{len(WATCHLIST)}")

    print(f"\n[2/3] Backtest V1 — MIN_SCORE=0 (attuale)...")
    trades_a, total_weeks, wd_a = run_backtest(all_data, min_score=0.0)
    sim_a = simulate_capital(trades_a)
    print(f"  trade: {sim_a['trades']} | WR: {sim_a['wr']:.1f}% | Finale: {sim_a['final_bal']:,.0f} EUR")

    print(f"\n[3/3] Backtest V1 — MIN_SCORE=6 (filtrato)...")
    trades_b, _, wd_b = run_backtest(all_data, min_score=6.0)
    sim_b = simulate_capital(trades_b)
    print(f"  trade: {sim_b['trades']} | WR: {sim_b['wr']:.1f}% | Finale: {sim_b['final_bal']:,.0f} EUR")

    print_report(sim_a, sim_b, wd_a, wd_b, total_weeks)

    trades_a.to_csv("backtest_minscore0.csv", index=False)
    trades_b.to_csv("backtest_minscore6.csv", index=False)
    print("\nCSV salvati: backtest_minscore0.csv | backtest_minscore6.csv")
