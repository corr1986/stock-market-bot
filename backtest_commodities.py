# backtest_commodities.py
# Confronto V1 attuale (solo azioni) vs V1 + metals/commodities
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
BT_START   = "2020-01-01"
BT_END     = datetime.today().strftime("%Y-%m-%d")

# ---------------------------------------------------------------------------
# Watchlist A — V1 attuale (solo azioni cTrader)
# ---------------------------------------------------------------------------
WATCHLIST_STOCKS = [
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

# ---------------------------------------------------------------------------
# Commodities — yfinance futures symbols → cTrader label
# ---------------------------------------------------------------------------
COMMODITIES_YF = {
    # Metalli preziosi
    "GC=F":  "XAUUSD",   # Gold
    "SI=F":  "XAGUSD",   # Silver
    "PA=F":  "XPDUSD",   # Palladio
    "PL=F":  "XPTUSD",   # Platino
    # Energia
    "CL=F":  "XTIUSD",   # WTI Crude Oil
    "BZ=F":  "XBRUSD",   # Brent Crude
    "NG=F":  "XNGUSD",   # Natural Gas
    # Soft commodities
    "CT=F":  "COTTON",   # Cotone
    "SB=F":  "SUGAR",    # Zucchero
    "KC=F":  "COFFEE",   # Caffe
    "ZW=F":  "WHEAT",    # Grano
    "CC=F":  "COCOA",    # Cacao
    "ZC=F":  "CORN",     # Mais
}

WATCHLIST_B = WATCHLIST_STOCKS + list(COMMODITIES_YF.keys())


# ---------------------------------------------------------------------------
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


def run_backtest(all_data, watchlist, label=""):
    signal_dates = pd.date_range(BT_START, BT_END, freq="W-FRI")
    trades = []
    wd = {0: 0, 1: 0, 2: 0, 3: 0}

    for sig_date in signal_dates:
        candidates = []
        for ticker in watchlist:
            if ticker not in all_data:
                continue
            df   = all_data[ticker]
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
            # Usa nome leggibile per le commodities
            display = COMMODITIES_YF.get(ticker, ticker)
            trades.append({
                "date":    sig_date,
                "year":    sig_date.year,
                "ticker":  display,
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


def print_report(sim_a, sim_b, wd_a, wd_b, total_weeks, n_a, n_b):
    sep  = "=" * 66
    sep2 = "-" * 62
    la   = f"V1 solo azioni ({n_a})"
    lb   = f"V1 + commodities ({n_b})"
    print(f"\n{sep}")
    print(f"  CONFRONTO: azioni vs azioni + commodities")
    print(f"  Periodo: {BT_START} -> {BT_END} | Cap {CAPITAL:,}EUR | Trade {TRADE_SIZE}EUR | R:R 3:1")
    print(sep)

    def row(lbl, va, vb):
        print(f"  {lbl:<32}{str(va):>15}{str(vb):>15}")

    row("Titoli in watchlist",     n_a,                              n_b)
    row("Trade chiusi",            sim_a["trades"],                  sim_b["trades"])
    row("WIN",                     sim_a["wins"],                    sim_b["wins"])
    row("LOSS",                    sim_a["losses"],                  sim_b["losses"])
    row("Win rate",                f"{sim_a['wr']:.1f}%",            f"{sim_b['wr']:.1f}%")
    row("EV medio/trade",          f"{sim_a['ev']:+.2f}%",           f"{sim_b['ev']:+.2f}%")
    print(f"  {sep2}")
    row("Capitale finale",         f"{sim_a['final_bal']:,.0f} EUR", f"{sim_b['final_bal']:,.0f} EUR")
    row("P&L totale",              f"{sim_a['total_pnl']:+,.0f} EUR",f"{sim_b['total_pnl']:+,.0f} EUR")
    row("Rendimento annuo",        f"{sim_a['ann_ret']:.1f}%",       f"{sim_b['ann_ret']:.1f}%")
    print(f"  {sep2}")
    row("Max drawdown EUR",        f"-{sim_a['max_dd_eur']:,.0f} EUR",f"-{sim_b['max_dd_eur']:,.0f} EUR")
    row("Max drawdown %",          f"-{sim_a['max_dd_pct']:.1f}%",   f"-{sim_b['max_dd_pct']:.1f}%")
    row("Max SL consecutivi",      sim_a["max_consec"],              sim_b["max_consec"])
    print(sep)

    print(f"\n  DISTRIBUZIONE SETTIMANE ({total_weeks} totali)")
    print(f"  {'':32}{la:>15}{lb:>15}")
    print(f"  {sep2}")
    for n in [0, 1, 2, 3]:
        va = wd_a.get(n, 0); vb = wd_b.get(n, 0)
        print(f"  {str(n)+' trade/settimana':<32}{va:>8} ({va/total_weeks*100:.0f}%){vb:>8} ({vb/total_weeks*100:.0f}%)")
    print(sep)

    # Quali commodities sono apparse nei trade
    print(f"\n  COMMODITIES — frequenza nei trade B:")
    print(f"  {sep2}")

    all_years = sorted(set(list(sim_a["yearly"]) + list(sim_b["yearly"])))
    print(f"\n  Anno       {la:>16}  {lb:>16}  {'Diff':>10}")
    print(f"  {'-'*56}")
    for yr in all_years:
        pa = sim_a["yearly"].get(yr, 0)
        pb = sim_b["yearly"].get(yr, 0)
        print(f"  {yr}  {pa:>+13.0f} EUR  {pb:>+13.0f} EUR  {pb-pa:>+8.0f} EUR")
    print(sep)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    n_a = len(WATCHLIST_STOCKS)
    n_b = len(WATCHLIST_B)
    print(f"Watchlist A (azioni):            {n_a} titoli")
    print(f"Watchlist B (azioni+commodities): {n_b} titoli ({len(COMMODITIES_YF)} commodities)")
    print(f"Periodo: {BT_START} -> {BT_END}")

    all_unique = list(dict.fromkeys(WATCHLIST_STOCKS + list(COMMODITIES_YF.keys())))
    print(f"\n[1/3] Download dati WEEKLY 2019-01-01 -> {BT_END}...")
    all_data = download_all(all_unique, "2019-01-01", BT_END)
    print(f"  Scaricati: {len(all_data)}/{len(all_unique)}")

    # Verifica quali commodities hanno dati
    comm_ok = [t for t in COMMODITIES_YF if t in all_data]
    comm_ko = [t for t in COMMODITIES_YF if t not in all_data]
    print(f"  Commodities OK: {[COMMODITIES_YF[t] for t in comm_ok]}")
    if comm_ko:
        print(f"  Commodities KO: {[COMMODITIES_YF[t] for t in comm_ko]}")

    print(f"\n[2/3] Backtest V1 — solo azioni ({n_a} titoli)...")
    trades_a, total_weeks, wd_a = run_backtest(all_data, WATCHLIST_STOCKS)
    sim_a = simulate_capital(trades_a)
    print(f"  trade={sim_a['trades']} | WR={sim_a['wr']:.1f}% | Finale={sim_a['final_bal']:,.0f} EUR")

    print(f"\n[3/3] Backtest V1 — azioni + commodities ({n_b} titoli)...")
    trades_b, _, wd_b = run_backtest(all_data, WATCHLIST_B)
    sim_b = simulate_capital(trades_b)
    print(f"  trade={sim_b['trades']} | WR={sim_b['wr']:.1f}% | Finale={sim_b['final_bal']:,.0f} EUR")

    print_report(sim_a, sim_b, wd_a, wd_b, total_weeks, n_a, n_b)

    # Frequenza commodities nei trade B
    if not trades_b.empty:
        comm_labels = set(COMMODITIES_YF.values())
        comm_trades = trades_b[trades_b["ticker"].isin(comm_labels)]
        if not comm_trades.empty:
            freq = comm_trades["ticker"].value_counts()
            print(f"\n  Commodity       Trade  WIN  LOSS   WR%")
            print(f"  {'-'*45}")
            for ticker, count in freq.items():
                sub  = comm_trades[comm_trades["ticker"] == ticker]
                sub_closed = sub[sub["outcome"].isin(["WIN","LOSS","TIMEOUT"])]
                w = (sub_closed["outcome"] == "WIN").sum()
                l = (sub_closed["outcome"] == "LOSS").sum()
                wr = w / len(sub_closed) * 100 if len(sub_closed) > 0 else 0
                print(f"  {ticker:<15} {count:>5}  {w:>3}  {l:>4}   {wr:.0f}%")
        else:
            print("\n  Nessuna commodity selezionata nei top-3 settimanali.")

    trades_a.to_csv("backtest_stocks_only.csv", index=False)
    trades_b.to_csv("backtest_stocks_commodities.csv", index=False)
    print("\nCSV: backtest_stocks_only.csv | backtest_stocks_commodities.csv")
