"""
Confronto watchlist — strategia V1 identica, universo diverso.
  A = Watchlist ORIGINALE (produzione)
  B = Watchlist cTRADER (ampliata)
Periodo: 2020-01-01 -> 2026-04-30 | Capitale: 20.000EUR | Trade: 500EUR
"""

import pandas as pd
import yfinance as yf
from datetime import datetime
from analyzer import compute_indicators, score_stock

CAPITAL    = 20_000
TRADE_SIZE = 500
SL_MULT    = 1.5
RR         = 3.0
SAFETY_CAP = 52
MIN_BARS   = 26

BT_START = "2020-01-01"
BT_END   = "2026-04-30"

# ---------------------------------------------------------------------------
# Watchlist A — ORIGINALE (da config.py, produzione)
# ---------------------------------------------------------------------------

WATCHLIST_A_USA = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "BRK-B", "LLY",
    "JPM", "V", "UNH", "XOM", "MA", "COST", "HD", "PG", "JNJ", "NFLX",
    "ABBV", "BAC", "CRM", "AMD", "WMT", "MRK", "KO", "CVX", "ORCL", "ACN",
    "MCD", "PEP", "TMO", "CSCO", "ADBE", "ABT", "QCOM", "GE", "TXN", "LIN",
    "AMGN", "MS", "ISRG", "DHR", "PM", "CAT", "IBM", "INTU", "GS", "SPGI",
    "AXP", "BKNG", "SYK", "BLK", "T", "NOW", "RTX", "CB", "ELV", "LOW",
    "GILD", "C", "BSX", "VRTX", "AMAT", "PLD", "MDT", "DE", "ADI", "SCHW",
    "MU", "REGN", "NEE", "TJX", "ETN", "ZTS", "CI", "ADP", "PANW", "SHW",
    "HUM", "EQIX", "PGR", "SO", "BDX", "EOG", "KLAC", "SNPS", "APH", "MCO",
    "CDNS", "WM", "CME", "ICE", "NOC", "LMT", "MMM", "USB", "EMR", "DUK",
]

WATCHLIST_A_EUROPE = [
    # UK
    "AZN.L", "SHEL.L", "HSBA.L", "ULVR.L", "GSK.L",
    "RIO.L", "BP.L", "REL.L", "NG.L", "EXPN.L",
    "CRH.L", "PRU.L", "AAL.L", "LLOY.L", "NXT.L",
    "GLEN.L", "DGE.L", "LSEG.L", "BA.L", "STAN.L",
    # Francia
    "MC.PA", "TTE.PA", "OR.PA", "SAN.PA", "BNP.PA",
    "AI.PA", "RMS.PA", "BN.PA", "GLE.PA", "SU.PA",
    "KER.PA", "VIE.PA", "DSY.PA", "CAP.PA", "LR.PA",
    "PUB.PA", "DG.PA", "AIR.PA", "ORA.PA", "RI.PA",
    # Germania
    "SAP.DE", "SIE.DE", "ALV.DE", "MUV2.DE", "DTE.DE",
    "BAYN.DE", "BMW.DE", "MBG.DE", "BAS.DE", "IFX.DE",
    "DBK.DE", "MRK.DE", "HEN3.DE", "BEI.DE", "RWE.DE",
    "CON.DE", "FRE.DE", "MTX.DE", "VNA.DE", "ADS.DE",
    # Paesi Bassi
    "ASML.AS", "AD.AS", "RAND.AS", "PHIA.AS", "WKL.AS",
    "AGN.AS", "NN.AS", "HEIA.AS", "IMCD.AS", "ASM.AS",
    # Svizzera
    "NESN.SW", "ROG.SW", "NOVN.SW", "ALC.SW", "ZURN.SW",
    "GIVN.SW", "ABBN.SW", "LONN.SW", "SREN.SW", "HOLN.SW",
    # Altri
    "NOVO-B.CO", "CARL-B.CO", "MAERSK-B.CO",
    "ENI.MI", "ENEL.MI", "ISP.MI", "UCG.MI", "RACE.MI", "STMPA.PA", "G.MI",
    "IBE.MC", "SAN.MC", "BBVA.MC", "ITX.MC", "REP.MC",
    "VOLV-B.ST", "HEXA-B.ST", "ESSITY-B.ST", "ATCO-A.ST",
    "ABI.BR",
]

# ---------------------------------------------------------------------------
# Watchlist B — cTRADER (ampliata)
# ---------------------------------------------------------------------------

WATCHLIST_B_USA = [
    # Mega cap tech
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "META", "AMZN", "TSLA", "AVGO",
    # Semiconduttori / Hardware
    "AMD", "QCOM", "TXN", "ADI", "MU", "AMAT", "KLAC", "SNPS", "CDNS",
    "NXPI", "MRVL", "INTC",
    # Software / Cloud / Cyber
    "CRM", "ADBE", "NOW", "PANW", "INTU", "ORCL", "IBM", "CSCO", "FTNT",
    "DDOG", "SNOW", "OKTA", "ZM", "TWLO", "DOCU", "WDAY", "SPLK",
    # Internet / Media / E-comm
    "NFLX", "DIS", "SPOT", "SHOP", "MELI", "BKNG", "EBAY", "UBER",
    "TTD", "SNAP", "PINS", "ROKU",
    # Fintech / Pagamenti
    "V", "MA", "PYPL", "SQ", "AXP",
    # Healthcare - Pharma / Biotech
    "LLY", "ABBV", "MRK", "ABT", "AMGN", "GILD", "VRTX", "REGN",
    "BMY", "PFE", "JNJ", "MRNA", "BIIB", "ILMN",
    # Healthcare - Dispositivi / Servizi
    "UNH", "TMO", "DHR", "ISRG", "MDT", "BSX", "BDX", "SYK",
    "ELV", "HUM", "CI", "IDXX", "DXCM", "EW", "CVS", "A",
    # Financials
    "JPM", "BAC", "GS", "MS", "BLK", "C", "CB", "SCHW",
    "SPGI", "MCO", "CME", "ICE", "USB", "PGR", "PRU", "MET",
    "AFL", "TRV", "PNC", "DFS", "COF", "MMC", "BK",
    # Consumer Defensive
    "PG", "KO", "PEP", "WMT", "COST", "PM", "MCD", "SBUX",
    "KMB", "CL", "MDLZ", "GIS", "KR", "YUM", "HSY",
    # Consumer Cyclical
    "HD", "LOW", "TJX", "NKE", "RACE", "MAR", "HLT",
    "EA", "TTWO", "ATVI",
    # Energy
    "XOM", "CVX", "EOG", "COP", "OXY", "DVN", "HAL", "SLB",
    "VLO", "MPC", "PSX", "WMB", "OKE", "KMI",
    # Industrials
    "CAT", "DE", "GE", "ETN", "HON", "ITW", "EMR", "WM", "MMM",
    "RTX", "NOC", "LMT", "LHX", "FDX", "UPS", "CSX", "UNP", "GD", "ROK", "CMI",
    # Materials
    "SHW", "DOW", "DD", "LYB", "ECL", "FCX", "NEM", "PPG",
    # Utilities
    "NEE", "DUK", "SO", "D", "EXC", "AEP", "DTE", "SRE",
    # Real Estate
    "PLD", "EQIX", "AMT", "CCI", "PSA", "EQR", "AVB",
    # Asia / global
    "TSM",
]

WATCHLIST_B_EUROPE = [
    # Germania (.DE)
    "ADS.DE", "ALV.DE", "BAS.DE", "BAYN.DE", "BEI.DE", "BMW.DE",
    "CON.DE", "DBK.DE", "DB1.DE", "EOAN.DE", "FRE.DE", "HEN3.DE",
    "IFX.DE", "MRK.DE", "MTX.DE", "MUV2.DE", "RWE.DE", "SAP.DE",
    "SIE.DE", "SHL.DE", "VNA.DE", "VOW3.DE",
    # Paesi Bassi (.AS)
    "AGN.AS", "ASM.AS", "ASML.AS", "HEIA.AS", "IMCD.AS", "NN.AS",
    "PHIA.AS", "RAND.AS", "REL.AS", "AD.AS", "WKL.AS",
    # Francia (.PA)
    "AI.PA", "AIR.PA", "BNP.PA", "GLE.PA", "KER.PA", "MC.PA",
    "OR.PA", "PUB.PA", "RMS.PA", "SAN.PA", "SU.PA", "TTE.PA",
    # Spagna (.MC)
    "ACS.MC", "ANA.MC", "BBVA.MC", "IBE.MC", "ITX.MC", "REP.MC", "SAN.MC",
    # UK (.L)
    "BARC.L", "BP.L", "GLEN.L", "GSK.L", "HSBA.L", "LLOY.L",
    "NWG.L", "RIO.L", "SHEL.L", "STAN.L",
]

WATCHLIST_INDICES = [
    "^GSPC", "^NDX", "^DJI", "^GDAXI", "^FTSE", "^FCHI", "^STOXX50E",
]

# ---------------------------------------------------------------------------
# Download prezzi
# ---------------------------------------------------------------------------

def download_all(tickers, dl_start, dl_end, interval):
    data = {}
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        print(f"\r  {i}/{total}: {ticker:<16}", end="", flush=True)
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
# Backtest V1 — solo tecnica
# ---------------------------------------------------------------------------

def run_backtest_v1(all_data, top_n=3):
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
                "entry":   entry,
                "sl_pct":  round((entry - sl) / entry * 100, 2),
                "tp_pct":  round((tp - entry) / entry * 100, 2),
                "outcome": outcome,
                "pnl_pct": round((exit_price - entry) / entry * 100, 2),
            })
    return pd.DataFrame(trades)

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
# Simulazione capitale
# ---------------------------------------------------------------------------

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
    max_cl = curr = 0
    for o in closed["outcome"]:
        if o == "LOSS":
            curr += 1
            max_cl = max(max_cl, curr)
        else:
            curr = 0
    wins   = (closed["outcome"] == "WIN").sum()
    losses = (closed["outcome"] == "LOSS").sum()
    total  = len(closed)
    years  = (pd.Timestamp(BT_END) - pd.Timestamp(BT_START)).days / 365.25
    return {
        "trades":     total,
        "wins":       wins,
        "losses":     losses,
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

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(sim_a, sim_b, n_a, n_b):
    sep  = "=" * 62
    sep2 = "-" * 58
    la   = f"ORIGINALE ({n_a})"
    lb   = f"cTRADER ({n_b})"
    print(f"\n{sep}")
    print(f"  CONFRONTO WATCHLIST — Strategia V1 identica")
    print(f"  Periodo: {BT_START} -> {BT_END}")
    print(f"  R:R 3:1 | SL=1.5xATR | Cap {CAPITAL:,}EUR | Trade {TRADE_SIZE}EUR")
    print(sep)
    print(f"  {'Metrica':<30}{la:>16}{lb:>16}")
    print(f"  {sep2}")
    def row(label, va, vb):
        print(f"  {label:<30}{str(va):>16}{str(vb):>16}")
    row("Trade chiusi",     sim_a["trades"],                 sim_b["trades"])
    row("WIN",              sim_a["wins"],                   sim_b["wins"])
    row("LOSS",             sim_a["losses"],                 sim_b["losses"])
    row("Win rate",         f"{sim_a['wr']:.1f}%",           f"{sim_b['wr']:.1f}%")
    row("EV medio/trade",   f"{sim_a['ev']:+.2f}%",          f"{sim_b['ev']:+.2f}%")
    print(f"  {sep2}")
    row("Capitale finale",  f"{sim_a['final_bal']:,.0f}EUR", f"{sim_b['final_bal']:,.0f}EUR")
    row("P&L totale",       f"{sim_a['total_pnl']:+,.0f}EUR",f"{sim_b['total_pnl']:+,.0f}EUR")
    row("Rendimento annuo", f"{sim_a['ann_ret']:.1f}%",      f"{sim_b['ann_ret']:.1f}%")
    print(f"  {sep2}")
    row("Max drawdown EUR", f"-{sim_a['max_dd_eur']:,.0f}EUR",f"-{sim_b['max_dd_eur']:,.0f}EUR")
    row("Max drawdown %",   f"-{sim_a['max_dd_pct']:.1f}%",  f"-{sim_b['max_dd_pct']:.1f}%")
    row("Max SL consec.",   sim_a["max_consec"],             sim_b["max_consec"])
    print(sep)
    all_years = sorted(set(list(sim_a["yearly"]) + list(sim_b["yearly"])))
    print(f"\n  {'Anno':<8}{la:>16}{lb:>16}{'Diff':>12}")
    print(f"  {'-'*52}")
    for yr in all_years:
        pa = sim_a["yearly"].get(yr, 0)
        pb = sim_b["yearly"].get(yr, 0)
        print(f"  {yr:<8}{pa:>+14.0f}EUR{pb:>+14.0f}EUR{pb-pa:>+10.0f}EUR")
    print(sep)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    dl_start = "2019-01-01"
    dl_end   = datetime.today().strftime("%Y-%m-%d")

    tickers_a = WATCHLIST_A_USA + WATCHLIST_A_EUROPE + WATCHLIST_INDICES
    tickers_b = WATCHLIST_B_USA + WATCHLIST_B_EUROPE + WATCHLIST_INDICES

    n_a = len(WATCHLIST_A_USA) + len(WATCHLIST_A_EUROPE)
    n_b = len(WATCHLIST_B_USA) + len(WATCHLIST_B_EUROPE)

    print(f"Watchlist A (ORIGINALE): {len(WATCHLIST_A_USA)} USA + {len(WATCHLIST_A_EUROPE)} Europa + {len(WATCHLIST_INDICES)} indici = {len(tickers_a)} totali")
    print(f"Watchlist B (cTRADER):   {len(WATCHLIST_B_USA)} USA + {len(WATCHLIST_B_EUROPE)} Europa + {len(WATCHLIST_INDICES)} indici = {len(tickers_b)} totali")

    # Scarica tutti i ticker in un unico batch (evita download doppi per ticker comuni)
    all_unique = list(dict.fromkeys(tickers_a + tickers_b))
    print(f"\nTicker unici da scaricare: {len(all_unique)}")

    print(f"\n[1/3] Download dati WEEKLY {dl_start} -> {dl_end}...")
    all_data = download_all(all_unique, dl_start, dl_end, "1wk")
    print(f"  Scaricati: {len(all_data)}/{len(all_unique)}")

    # Filtra i dati per ciascuna watchlist
    data_a = {t: all_data[t] for t in tickers_a if t in all_data}
    data_b = {t: all_data[t] for t in tickers_b if t in all_data}

    print(f"\n[2/3] Backtest V1 — Watchlist A (ORIGINALE, {n_a} titoli)...")
    trades_a = run_backtest_v1(data_a)
    sim_a    = simulate_capital(trades_a)
    print(f"  trade: {sim_a['trades']} | WR: {sim_a['wr']:.1f}% | Finale: {sim_a['final_bal']:,.0f}EUR")

    print(f"\n[3/3] Backtest V1 — Watchlist B (cTRADER, {n_b} titoli)...")
    trades_b = run_backtest_v1(data_b)
    sim_b    = simulate_capital(trades_b)
    print(f"  trade: {sim_b['trades']} | WR: {sim_b['wr']:.1f}% | Finale: {sim_b['final_bal']:,.0f}EUR")

    print_report(sim_a, sim_b, n_a, n_b)

    trades_a.to_csv("backtest_watchlist_A.csv", index=False)
    trades_b.to_csv("backtest_watchlist_B.csv", index=False)
    print("\nRisultati salvati in backtest_watchlist_A.csv e backtest_watchlist_B.csv")
