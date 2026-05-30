"""
Simulazione v3 — watchlist ampliata da simboli cTrader + filtro fondamentale EPS.
Confronto: V1 = solo tecnica | V3 = tecnica + macro + fondamentali.
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

FUNDAMENTAL_BUFFER_DAYS = 30

# ---------------------------------------------------------------------------
# Watchlist ampliata (simboli cTrader → yfinance)
# ---------------------------------------------------------------------------

WATCHLIST_USA = [
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

WATCHLIST_EUROPE = [
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

WATCHLIST_INDICES = {
    "^GSPC":     "S&P 500",
    "^NDX":      "NASDAQ 100",
    "^DJI":      "Dow Jones",
    "^GDAXI":    "DAX",
    "^FTSE":     "FTSE 100",
    "^FCHI":     "CAC 40",
    "^STOXX50E": "Euro Stoxx 50",
}

# ---------------------------------------------------------------------------
# Mapping ticker -> settore
# ---------------------------------------------------------------------------

TICKER_SECTOR = {
    # USA - Tech
    "AAPL":"Tech","MSFT":"Tech","NVDA":"Tech","GOOGL":"Tech","GOOG":"Tech",
    "META":"Tech","AVGO":"Tech","AMD":"Tech","CSCO":"Tech","ADBE":"Tech",
    "QCOM":"Tech","TXN":"Tech","ADI":"Tech","MU":"Tech","AMAT":"Tech",
    "KLAC":"Tech","SNPS":"Tech","CDNS":"Tech","PANW":"Tech","ORCL":"Tech",
    "CRM":"Tech","NOW":"Tech","IBM":"Tech","INTU":"Tech","NXPI":"Tech",
    "MRVL":"Tech","INTC":"Tech","FTNT":"Tech","DDOG":"Tech","SNOW":"Tech",
    "OKTA":"Tech","ZM":"Tech","TWLO":"Tech","DOCU":"Tech","WDAY":"Tech",
    "SPLK":"Tech","ROKU":"Tech","TTD":"Tech","TSM":"Tech",
    # USA - Consumer Cyc
    "NFLX":"Consumer Cyc","DIS":"Consumer Cyc","SPOT":"Consumer Cyc",
    "SHOP":"Consumer Cyc","MELI":"Consumer Cyc","BKNG":"Consumer Cyc",
    "EBAY":"Consumer Cyc","UBER":"Consumer Cyc","SNAP":"Consumer Cyc",
    "PINS":"Consumer Cyc","HD":"Consumer Cyc","LOW":"Consumer Cyc",
    "TJX":"Consumer Cyc","NKE":"Consumer Cyc","RACE":"Consumer Cyc",
    "MAR":"Consumer Cyc","HLT":"Consumer Cyc","EA":"Consumer Cyc",
    "TTWO":"Consumer Cyc","ATVI":"Consumer Cyc","AMZN":"Consumer Cyc",
    "TSLA":"Consumer Cyc",
    # USA - Financials
    "V":"Financials","MA":"Financials","PYPL":"Financials","SQ":"Financials",
    "AXP":"Financials","JPM":"Financials","BAC":"Financials","GS":"Financials",
    "MS":"Financials","BLK":"Financials","C":"Financials","CB":"Financials",
    "SCHW":"Financials","SPGI":"Financials","MCO":"Financials",
    "CME":"Financials","ICE":"Financials","USB":"Financials",
    "PGR":"Financials","PRU":"Financials","MET":"Financials",
    "AFL":"Financials","TRV":"Financials","PNC":"Financials",
    "DFS":"Financials","COF":"Financials","MMC":"Financials","BK":"Financials",
    # USA - Healthcare
    "UNH":"Healthcare","LLY":"Healthcare","ABBV":"Healthcare","MRK":"Healthcare",
    "ABT":"Healthcare","TMO":"Healthcare","DHR":"Healthcare","AMGN":"Healthcare",
    "ISRG":"Healthcare","GILD":"Healthcare","MDT":"Healthcare","BSX":"Healthcare",
    "VRTX":"Healthcare","ZTS":"Healthcare","REGN":"Healthcare","BDX":"Healthcare",
    "SYK":"Healthcare","ELV":"Healthcare","HUM":"Healthcare","CI":"Healthcare",
    "IDXX":"Healthcare","DXCM":"Healthcare","EW":"Healthcare","MRNA":"Healthcare",
    "BIIB":"Healthcare","ILMN":"Healthcare","BMY":"Healthcare","PFE":"Healthcare",
    "JNJ":"Healthcare","CVS":"Healthcare","A":"Healthcare",
    # USA - Consumer Defensive
    "PG":"Consumer Def","KO":"Consumer Def","PEP":"Consumer Def",
    "WMT":"Consumer Def","COST":"Consumer Def","PM":"Consumer Def",
    "MCD":"Consumer Def","SBUX":"Consumer Def","KMB":"Consumer Def",
    "CL":"Consumer Def","MDLZ":"Consumer Def","GIS":"Consumer Def",
    "KR":"Consumer Def","YUM":"Consumer Def","HSY":"Consumer Def",
    # USA - Energy
    "XOM":"Energy","CVX":"Energy","EOG":"Energy","COP":"Energy",
    "OXY":"Energy","DVN":"Energy","HAL":"Energy","SLB":"Energy",
    "VLO":"Energy","MPC":"Energy","PSX":"Energy","WMB":"Energy",
    "OKE":"Energy","KMI":"Energy",
    # USA - Industrials / Defense
    "CAT":"Industrials","DE":"Industrials","GE":"Industrials",
    "ETN":"Industrials","HON":"Industrials","ITW":"Industrials",
    "EMR":"Industrials","WM":"Industrials","MMM":"Industrials",
    "FDX":"Industrials","UPS":"Industrials","CSX":"Industrials",
    "UNP":"Industrials","ROK":"Industrials","CMI":"Industrials",
    "RTX":"Defense","NOC":"Defense","LMT":"Defense","LHX":"Defense","GD":"Defense",
    # USA - Materials
    "SHW":"Materials","DOW":"Materials","DD":"Materials",
    "LYB":"Materials","ECL":"Materials","FCX":"Materials",
    "NEM":"Materials","PPG":"Materials",
    # USA - Utilities / Renewables
    "NEE":"Renewables","DUK":"Utilities","SO":"Utilities",
    "D":"Utilities","EXC":"Utilities","AEP":"Utilities",
    "DTE":"Utilities","SRE":"Utilities",
    # USA - Real Estate
    "PLD":"Real Estate","EQIX":"Real Estate","AMT":"Real Estate",
    "CCI":"Real Estate","PSA":"Real Estate","EQR":"Real Estate","AVB":"Real Estate",
    # Europe - Tech
    "ASML.AS":"Tech","SAP.DE":"Tech","SIE.DE":"Tech","IFX.DE":"Tech",
    "ASM.AS":"Tech","SHL.DE":"Tech","DB1.DE":"Tech","WKL.AS":"Tech",
    # Europe - Healthcare
    "BAYN.DE":"Healthcare","MRK.DE":"Healthcare","SAN.PA":"Healthcare",
    "PHIA.AS":"Healthcare","FRE.DE":"Healthcare","GSK.L":"Healthcare",
    # Europe - Financials
    "ALV.DE":"Financials","MUV2.DE":"Financials","DBK.DE":"Financials",
    "AGN.AS":"Financials","NN.AS":"Financials","BNP.PA":"Financials",
    "GLE.PA":"Financials","HSBA.L":"Financials","LLOY.L":"Financials",
    "BARC.L":"Financials","STAN.L":"Financials","BBVA.MC":"Financials",
    "SAN.MC":"Financials","NWG.L":"Financials",
    # Europe - Consumer Def
    "AD.AS":"Consumer Def","HEIA.AS":"Consumer Def","HEN3.DE":"Consumer Def",
    "BEI.DE":"Consumer Def","OR.PA":"Consumer Def",
    # Europe - Consumer Cyc
    "MC.PA":"Consumer Cyc","KER.PA":"Consumer Cyc","RMS.PA":"Consumer Cyc",
    "BMW.DE":"Consumer Cyc","VOW3.DE":"Consumer Cyc","ITX.MC":"Consumer Cyc",
    "ADS.DE":"Consumer Cyc","PUB.PA":"Consumer Cyc","CON.DE":"Consumer Cyc",
    # Europe - Industrials
    "AIR.PA":"Industrials","SU.PA":"Industrials","AI.PA":"Industrials",
    "MTX.DE":"Industrials","RAND.AS":"Industrials","REL.AS":"Industrials",
    "IMCD.AS":"Industrials","ACS.MC":"Industrials","ANA.MC":"Industrials",
    # Europe - Energy / Materials
    "BP.L":"Energy","SHEL.L":"Energy","TTE.PA":"Energy","REP.MC":"Energy",
    "RIO.L":"Materials","GLEN.L":"Materials","BAS.DE":"Materials",
    # Europe - Utilities / Renewables
    "IBE.MC":"Utilities","RWE.DE":"Renewables","EOAN.DE":"Renewables",
    # Europe - Real Estate
    "VNA.DE":"Real Estate",
}

DEFENSIVE_SECTORS = {"Healthcare", "Consumer Def", "Utilities", "Energy", "Defense"}

SECTOR_ETF = {
    "Tech":"XLK","Healthcare":"XLV","Energy":"XLE","Financials":"XLF",
    "Consumer Def":"XLP","Consumer Cyc":"XLY","Industrials":"XLI",
    "Defense":"ITA","Renewables":"ICLN","Utilities":"XLU",
    "Materials":"XLB","Real Estate":"XLRE",
}

# ---------------------------------------------------------------------------
# Download prezzi
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
# Download fondamentali
# ---------------------------------------------------------------------------

def download_fundamentals(tickers):
    fundamentals = {}
    total = len(tickers)
    skipped = 0
    for i, ticker in enumerate(tickers, 1):
        print(f"\r  {i}/{total}: {ticker:<14}  (ok: {len(fundamentals)}  skip: {skipped})", end="", flush=True)
        try:
            t  = yf.Ticker(ticker)
            qi = t.quarterly_income_stmt
            if qi is None or qi.empty:
                skipped += 1
                continue
            eps_row = None
            for label in ["Diluted EPS", "Basic EPS"]:
                if label in qi.index:
                    eps_row = qi.loc[label]
                    break
            if eps_row is None:
                skipped += 1
                continue
            df_eps = eps_row.to_frame(name="EPS")
            df_eps.index = pd.to_datetime(df_eps.index)
            fundamentals[ticker] = df_eps.sort_index()
        except Exception:
            skipped += 1
    print(f"\n  Fondamentali: {len(fundamentals)}/{total} ({skipped} senza dati)")
    return fundamentals

# ---------------------------------------------------------------------------
# Filtro fondamentale
# ---------------------------------------------------------------------------

def fundamental_bonus(ticker, fundamentals, sig_date):
    eps_df = fundamentals.get(ticker)
    if eps_df is None or eps_df.empty:
        return 0.0
    cutoff = sig_date - pd.Timedelta(days=FUNDAMENTAL_BUFFER_DAYS)
    past   = eps_df[eps_df.index <= cutoff]
    if len(past) < 1:
        return 0.0
    last_eps = float(past["EPS"].iloc[-1])
    if last_eps > 0:
        bonus = 1.5
    elif last_eps == 0:
        bonus = 0.0
    else:
        bonus = -3.0
    if len(past) >= 2 and float(past["EPS"].iloc[-2]) > 0 and last_eps > 0:
        bonus += 0.5
    return bonus

# ---------------------------------------------------------------------------
# Contesto macro
# ---------------------------------------------------------------------------

def get_weekly_sector_perf(all_data_macro, date):
    perf = {}
    for sector, etf in SECTOR_ETF.items():
        if etf not in all_data_macro:
            continue
        hist = all_data_macro[etf][all_data_macro[etf].index <= date]
        if len(hist) < 2:
            continue
        prev = float(hist["Close"].iloc[-2])
        last = float(hist["Close"].iloc[-1])
        if prev > 0:
            perf[sector] = (last - prev) / prev * 100
    return perf

def get_vix(all_data_macro, date):
    if "^VIX" not in all_data_macro:
        return None
    hist = all_data_macro["^VIX"][all_data_macro["^VIX"].index <= date]
    return float(hist["Close"].iloc[-1]) if not hist.empty else None

def sector_score_bonus(ticker, sector_perf, vix):
    sector = TICKER_SECTOR.get(ticker)
    if not sector or not sector_perf:
        return 0.0
    perf = sector_perf.get(sector, 0.0)
    if   perf >= 2.0:  bonus = 2.0
    elif perf >= 0.5:  bonus = 1.0
    elif perf >= 0:    bonus = 0.5
    elif perf >= -1.0: bonus = -0.5
    else:              bonus = -1.5
    if vix and vix > 25:
        if sector in DEFENSIVE_SECTORS:
            bonus += 1.0
        elif sector in {"Tech", "Consumer Cyc", "Real Estate"}:
            bonus -= 1.0
    return bonus

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
                "date": sig_date, "year": sig_date.year, "ticker": ticker,
                "sector": TICKER_SECTOR.get(ticker, "N/D"),
                "entry": entry,
                "sl_pct": round((entry - sl) / entry * 100, 2),
                "tp_pct": round((tp - entry) / entry * 100, 2),
                "outcome": outcome,
                "pnl_pct": round((exit_price - entry) / entry * 100, 2),
            })
    return pd.DataFrame(trades)

# ---------------------------------------------------------------------------
# Backtest V3 — tecnica + macro + fondamentali
# ---------------------------------------------------------------------------

def run_backtest_v3(all_data, all_data_macro, fundamentals, top_n=3):
    signal_dates = pd.date_range(BT_START, BT_END, freq="W-FRI")
    trades = []
    for sig_date in signal_dates:
        vix         = get_vix(all_data_macro, sig_date)
        sector_perf = get_weekly_sector_perf(all_data_macro, sig_date)
        candidates  = []
        for ticker, df in all_data.items():
            if ticker.startswith("^"):
                continue
            hist = df[df.index <= sig_date].tail(200)
            if len(hist) < MIN_BARS:
                continue
            try:
                ind    = compute_indicators(hist)
                score  = score_stock(ind)
                if score > 0 and (ind.get("macd_hist") or 0) > 0:
                    macro_b = sector_score_bonus(ticker, sector_perf, vix)
                    fund_b  = fundamental_bonus(ticker, fundamentals, sig_date)
                    candidates.append((ticker, ind, score + macro_b + fund_b))
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
                "date": sig_date, "year": sig_date.year, "ticker": ticker,
                "sector": TICKER_SECTOR.get(ticker, "N/D"),
                "vix": round(vix, 1) if vix else None,
                "entry": entry,
                "sl_pct": round((entry - sl) / entry * 100, 2),
                "tp_pct": round((tp - entry) / entry * 100, 2),
                "outcome": outcome,
                "pnl_pct": round((exit_price - entry) / entry * 100, 2),
            })
    return pd.DataFrame(trades)

# ---------------------------------------------------------------------------
# Simulazione capitale
# ---------------------------------------------------------------------------

def simulate_capital(trades_df):
    closed = trades_df[trades_df["outcome"].isin(["WIN","LOSS","TIMEOUT"])].copy()
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
        if o == "LOSS": curr += 1; max_cl = max(max_cl, curr)
        else: curr = 0
    wins  = (closed["outcome"] == "WIN").sum()
    losses = (closed["outcome"] == "LOSS").sum()
    total = len(closed)
    years = (pd.Timestamp(BT_END) - pd.Timestamp(BT_START)).days / 365.25
    return {
        "trades":    total,
        "open":      (trades_df["outcome"] == "OPEN").sum(),
        "wins":      wins,
        "losses":    losses,
        "wr":        wins / total * 100 if total else 0,
        "ev":        closed["pnl_pct"].mean() if total else 0,
        "final_bal": round(balance, 0),
        "total_pnl": round(balance - CAPITAL, 0),
        "ann_ret":   round((balance / CAPITAL) ** (1 / years) * 100 - 100, 1) if years > 0 else 0,
        "max_dd_eur":round(max_dd, 0),
        "max_dd_pct":round(max_dd / peak * 100, 1),
        "max_consec":max_cl,
        "yearly":    yearly,
    }

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(sims):
    sep  = "=" * 60
    sep2 = "-" * 56
    labels = {1: "V1 (tecnica)", 3: "V3 (+macro+fond.)"}
    keys   = sorted(sims.keys())
    print(f"\n{sep}")
    print(f"  CONFRONTO V1 vs V3 — Backtest Weekly {BT_START} -> {BT_END}")
    print(f"  R:R 3:1 | SL=1.5xATR | Cap {CAPITAL:,}EUR | Trade {TRADE_SIZE}EUR")
    print(f"  Universo: {len(WATCHLIST_USA)} USA + {len(WATCHLIST_EUROPE)} Europa + {len(WATCHLIST_INDICES)} indici")
    print(sep)
    header = f"  {'Metrica':<30}" + "".join(f"{labels[k]:>14}" for k in keys)
    print(header)
    print(f"  {sep2}")
    def row(label, *vals):
        cells = "".join(f"{str(v):>14}" for v in vals)
        print(f"  {label:<30}{cells}")
    r = {k: sims[k] for k in keys}
    row("Trade chiusi",       *[r[k]["trades"]               for k in keys])
    row("WIN",                *[r[k]["wins"]                  for k in keys])
    row("LOSS",               *[r[k]["losses"]                for k in keys])
    row("Win rate",           *[f"{r[k]['wr']:.1f}%"          for k in keys])
    row("EV medio/trade",     *[f"{r[k]['ev']:+.2f}%"         for k in keys])
    print(f"  {sep2}")
    row("Capitale finale",    *[f"{r[k]['final_bal']:,.0f}EUR"  for k in keys])
    row("P&L totale",         *[f"{r[k]['total_pnl']:+,.0f}EUR" for k in keys])
    row("Rendimento annuo",   *[f"{r[k]['ann_ret']:.1f}%"       for k in keys])
    print(f"  {sep2}")
    row("Max drawdown EUR",   *[f"-{r[k]['max_dd_eur']:,.0f}EUR" for k in keys])
    row("Max drawdown %",     *[f"-{r[k]['max_dd_pct']:.1f}%"   for k in keys])
    row("Max SL consec.",     *[r[k]["max_consec"]              for k in keys])
    print(sep)
    all_years = sorted(set(yr for k in keys for yr in r[k]["yearly"]))
    print(f"\n  {'Anno':<8}" + "".join(f"{labels[k]:>14}" for k in keys) + f"  {'Diff':>10}")
    print(f"  {'-'*44}")
    for yr in all_years:
        p1 = r[1]["yearly"].get(yr, 0)
        p3 = r[3]["yearly"].get(yr, 0)
        vals = f"{p1:>+13.0f}EUR {p3:>+13.0f}EUR {p3-p1:>+9.0f}EUR"
        print(f"  {yr:<8}{vals}")
    print(sep)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    all_tickers   = WATCHLIST_USA + WATCHLIST_EUROPE + list(WATCHLIST_INDICES.keys())
    macro_tickers = list(SECTOR_ETF.values()) + ["^VIX"]

    total_stocks = len(WATCHLIST_USA) + len(WATCHLIST_EUROPE)
    print(f"Universo: {len(WATCHLIST_USA)} USA + {len(WATCHLIST_EUROPE)} Europa + {len(WATCHLIST_INDICES)} indici = {len(all_tickers)} totali")

    dl_start = "2019-01-01"
    dl_end   = datetime.today().strftime("%Y-%m-%d")

    print(f"\n[1/4] Download dati WEEKLY {dl_start} -> {dl_end}...")
    all_data = download_all(all_tickers, dl_start, dl_end, "1wk")
    print(f"  Scaricati: {len(all_data)}/{len(all_tickers)}")

    print(f"\n[2/4] Download dati macro ({len(macro_tickers)} ETF/VIX)...")
    all_data_macro = download_all(macro_tickers, dl_start, dl_end, "1wk")
    print(f"  Scaricati: {len(all_data_macro)}/{len(macro_tickers)}")

    print(f"\n[3/4] Download fondamentali ({total_stocks} ticker)...")
    fundamentals = download_fundamentals(WATCHLIST_USA + WATCHLIST_EUROPE)

    print("\n[4/4] Esecuzione backtest...")

    print("  V1 (solo tecnica)...", end=" ", flush=True)
    trades_v1 = run_backtest_v1(all_data)
    sim_v1    = simulate_capital(trades_v1)
    print(f"trade: {sim_v1['trades']} | WR: {sim_v1['wr']:.1f}% | Finale: {sim_v1['final_bal']:,.0f}EUR")

    print("  V3 (tecnica + macro + fondamentali)...", end=" ", flush=True)
    trades_v3 = run_backtest_v3(all_data, all_data_macro, fundamentals)
    sim_v3    = simulate_capital(trades_v3)
    print(f"trade: {sim_v3['trades']} | WR: {sim_v3['wr']:.1f}% | Finale: {sim_v3['final_bal']:,.0f}EUR")

    print_report({1: sim_v1, 3: sim_v3})

    trades_v1.to_csv("backtest_v1_results.csv", index=False)
    trades_v3.to_csv("backtest_v3_results.csv", index=False)
    print("\nRisultati salvati in backtest_v1_results.csv e backtest_v3_results.csv")
