"""
Simulazione v2 — aggiunge contesto macro (VIX + settori) alla selezione.
Stesso periodo, stesso capitale, stessa logica SL/TP di simulate.py (v1).
Confronto diretto: v1 = solo tecnica | v2 = tecnica + macro + settori.
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from analyzer import compute_indicators, score_stock
from config import WATCHLIST_USA, WATCHLIST_EUROPE, WATCHLIST_INDICES

CAPITAL    = 20_000
TRADE_SIZE = 500
SL_MULT    = 1.5
RR         = 3.0
SAFETY_CAP = 52
MIN_BARS   = 26

BT_START = "2020-01-01"
BT_END   = "2026-04-30"

# ---------------------------------------------------------------------------
# Mapping ticker -> settore
# ---------------------------------------------------------------------------

TICKER_SECTOR = {
    # USA - Tech
    "AAPL": "Tech",  "MSFT": "Tech",  "NVDA": "Tech",  "GOOGL": "Tech",
    "META": "Tech",  "AVGO": "Tech",  "AMD": "Tech",   "CSCO": "Tech",
    "ADBE": "Tech",  "QCOM": "Tech",  "TXN": "Tech",   "ADI": "Tech",
    "MU": "Tech",    "AMAT": "Tech",  "KLAC": "Tech",  "SNPS": "Tech",
    "CDNS": "Tech",  "PANW": "Tech",  "ORCL": "Tech",  "CRM": "Tech",
    "NOW": "Tech",   "IBM": "Tech",   "INTU": "Tech",  "APH": "Tech",
    # USA - Healthcare
    "UNH": "Healthcare", "LLY": "Healthcare", "ABBV": "Healthcare",
    "MRK": "Healthcare", "ABT": "Healthcare", "TMO": "Healthcare",
    "DHR": "Healthcare", "AMGN": "Healthcare","ISRG": "Healthcare",
    "GILD": "Healthcare","MDT": "Healthcare", "BSX": "Healthcare",
    "VRTX": "Healthcare","ZTS": "Healthcare", "REGN": "Healthcare",
    "BDX": "Healthcare", "SYK": "Healthcare", "ELV": "Healthcare",
    "HUM": "Healthcare", "CI": "Healthcare",
    # USA - Financials
    "JPM": "Financials","V": "Financials",   "MA": "Financials",
    "BAC": "Financials","GS": "Financials",  "MS": "Financials",
    "BLK": "Financials","C": "Financials",   "AXP": "Financials",
    "CB": "Financials", "SCHW": "Financials","SPGI": "Financials",
    "MCO": "Financials","CME": "Financials", "ICE": "Financials",
    "USB": "Financials","PGR": "Financials", "BRK-B": "Financials",
    # USA - Consumer Defensive
    "PG": "Consumer Def", "KO": "Consumer Def",  "PEP": "Consumer Def",
    "WMT": "Consumer Def","COST": "Consumer Def","PM": "Consumer Def",
    "MCD": "Consumer Def",
    # USA - Consumer Cyclical
    "TSLA": "Consumer Cyc","HD": "Consumer Cyc","LOW": "Consumer Cyc",
    "TJX": "Consumer Cyc","BKNG": "Consumer Cyc","NFLX": "Consumer Cyc",
    "AMZN": "Consumer Cyc",
    # USA - Energy
    "XOM": "Energy", "CVX": "Energy", "EOG": "Energy",
    # USA - Industrials
    "CAT": "Industrials","DE": "Industrials", "GE": "Industrials",
    "ETN": "Industrials","EMR": "Industrials","WM": "Industrials",
    "MMM": "Industrials","RTX": "Defense",   "NOC": "Defense",
    "LMT": "Defense",
    # USA - Materials / Utilities / Real Estate
    "LIN": "Materials","SHW": "Materials",
    "NEE": "Renewables","DUK": "Utilities","SO": "Utilities",
    "PLD": "Real Estate","EQIX": "Real Estate",
    # Europe - Tech
    "ASML.AS": "Tech",  "SAP.DE": "Tech",  "SIE.DE": "Tech",
    "IFX.DE": "Tech",   "STMPA.PA": "Tech","CAP.PA": "Tech",
    "DSY.PA": "Tech",   "ASM.AS": "Tech",
    # Europe - Healthcare
    "AZN.L": "Healthcare","GSK.L": "Healthcare","NOVO-B.CO": "Healthcare",
    "NOVN.SW": "Healthcare","ROG.SW": "Healthcare","BAYN.DE": "Healthcare",
    "MRK.DE": "Healthcare","SAN.PA": "Healthcare","PHIA.AS": "Healthcare",
    "GIVN.SW": "Healthcare","ALC.SW": "Healthcare",
    # Europe - Energy / Materials
    "BP.L": "Energy",  "SHEL.L": "Energy","TTE.PA": "Energy",
    "REP.MC": "Energy","ENI.MI": "Energy",
    "RIO.L": "Materials","GLEN.L": "Materials","AAL.L": "Materials",
    "BAS.DE": "Materials","IMCD.AS": "Materials",
    # Europe - Financials
    "HSBA.L": "Financials","BNP.PA": "Financials","GLE.PA": "Financials",
    "SAN.MC": "Financials","BBVA.MC": "Financials","ALV.DE": "Financials",
    "MUV2.DE": "Financials","DBK.DE": "Financials","AGN.AS": "Financials",
    "NN.AS": "Financials","LSEG.L": "Financials","REL.L": "Financials",
    "EXPN.L": "Financials","PRU.L": "Financials","LLOY.L": "Financials",
    "STAN.L": "Financials","G.MI": "Financials","ISP.MI": "Financials",
    "UCG.MI": "Financials","SREN.SW": "Financials","ZURN.SW": "Financials",
    # Europe - Consumer Defensive
    "DGE.L": "Consumer Def","ULVR.L": "Consumer Def","BN.PA": "Consumer Def",
    "OR.PA": "Consumer Def","NESN.SW": "Consumer Def","CARL-B.CO": "Consumer Def",
    "HEIA.AS": "Consumer Def","ESSITY-B.ST": "Consumer Def",
    "AD.AS": "Consumer Def","HEN3.DE": "Consumer Def","BEI.DE": "Consumer Def",
    "RI.PA": "Consumer Def","ABI.BR": "Consumer Def",
    # Europe - Consumer Cyclical
    "MC.PA": "Consumer Cyc","KER.PA": "Consumer Cyc","RMS.PA": "Consumer Cyc",
    "BMW.DE": "Consumer Cyc","MBG.DE": "Consumer Cyc","NXT.L": "Consumer Cyc",
    "ITX.MC": "Consumer Cyc","RACE.MI": "Consumer Cyc","CON.DE": "Consumer Cyc",
    "ADS.DE": "Consumer Cyc","PUB.PA": "Consumer Cyc",
    # Europe - Industrials
    "CRH.L": "Industrials","AIR.PA": "Industrials","SU.PA": "Industrials",
    "LR.PA": "Industrials","MAERSK-B.CO": "Industrials","VOLV-B.ST": "Industrials",
    "ATCO-A.ST": "Industrials","HEXA-B.ST": "Industrials","ABBN.SW": "Industrials",
    "RAND.AS": "Industrials","WKL.AS": "Industrials","AI.PA": "Industrials",
    "DG.PA": "Industrials","MTX.DE": "Industrials","LONN.SW": "Industrials",
    "HOLN.SW": "Industrials",
    # Europe - Utilities / Renewables
    "ENEL.MI": "Renewables","RWE.DE": "Renewables","NG.L": "Utilities",
    "IBE.MC": "Utilities","ORA.PA": "Utilities","DTE.DE": "Utilities",
    "VIE.PA": "Utilities",
    # Europe - Defense / Real Estate
    "BA.L": "Defense","FRE.DE": "Real Estate","VNA.DE": "Real Estate",
}

# Settori difensivi preferiti in Risk-Off
DEFENSIVE_SECTORS = {"Healthcare", "Consumer Def", "Utilities", "Energy", "Defense"}

# Mapping settore -> ETF per performance settimanale
SECTOR_ETF = {
    "Tech":         "XLK",
    "Healthcare":   "XLV",
    "Energy":       "XLE",
    "Financials":   "XLF",
    "Consumer Def": "XLP",
    "Consumer Cyc": "XLY",
    "Industrials":  "XLI",
    "Defense":      "ITA",
    "Renewables":   "ICLN",
    "Utilities":    "XLU",
    "Materials":    "XLB",
    "Real Estate":  "XLRE",
}


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
# Contesto macro settimanale (VIX + settori)
# ---------------------------------------------------------------------------

def get_weekly_sector_perf(all_data_macro, date):
    """Variazione settimanale di ogni settore prima di 'date'."""
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
    if hist.empty:
        return None
    return float(hist["Close"].iloc[-1])


def sector_score_bonus(ticker, sector_perf, vix):
    """Bonus/malus basato su settore e regime macro."""
    sector = TICKER_SECTOR.get(ticker)
    if not sector or not sector_perf:
        return 0.0

    perf = sector_perf.get(sector, 0.0)

    # Bonus/malus da performance settoriale
    if perf >= 2.0:
        bonus = 2.0
    elif perf >= 0.5:
        bonus = 1.0
    elif perf >= 0:
        bonus = 0.5
    elif perf >= -1.0:
        bonus = -0.5
    else:
        bonus = -1.5

    # In Risk-Off (VIX > 25): boost settori difensivi, penalizza growth
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
# Backtest principale
# ---------------------------------------------------------------------------

def run_backtest(all_data, all_data_macro, top_n=3):
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
                ind   = compute_indicators(hist)
                score = score_stock(ind)
                if score > 0 and (ind.get("macd_hist") or 0) > 0:
                    bonus       = sector_score_bonus(ticker, sector_perf, vix)
                    total_score = score + bonus
                    candidates.append((ticker, ind, total_score))
            except Exception:
                continue

        candidates.sort(key=lambda x: x[2], reverse=True)

        for ticker, ind, _ in candidates[:top_n]:
            entry  = ind["price"]
            atr    = ind.get("atr_14") or (entry * 0.02)
            sl     = round(entry - SL_MULT * atr, 4)
            tp     = round(entry + RR * SL_MULT * atr, 4)
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
                "sector":  TICKER_SECTOR.get(ticker, "N/D"),
                "vix":     round(vix, 1) if vix else None,
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
    peak         = CAPITAL
    max_dd_eur   = 0.0
    yearly       = {}

    for _, row in closed.iterrows():
        pnl_eur  = row["pnl_pct"] / 100 * TRADE_SIZE
        balance += pnl_eur
        if balance > peak:
            peak = balance
        dd = peak - balance
        if dd > max_dd_eur:
            max_dd_eur = dd
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
    wr     = wins / total * 100 if total else 0
    years  = (pd.Timestamp(BT_END) - pd.Timestamp(BT_START)).days / 365.25

    return {
        "trades":     total,
        "open":       (trades_df["outcome"] == "OPEN").sum(),
        "wins":       wins,
        "losses":     losses,
        "wr":         wr,
        "ev":         closed["pnl_pct"].mean() if total else 0,
        "final_bal":  round(balance, 0),
        "total_pnl":  round(balance - CAPITAL, 0),
        "ann_ret":    round((balance / CAPITAL) ** (1 / years) * 100 - 100, 1) if years > 0 else 0,
        "max_dd_eur": round(max_dd_eur, 0),
        "max_dd_pct": round(max_dd_eur / peak * 100, 1),
        "max_consec": max_cl,
        "yearly":     yearly,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(v1_sim, v2_sim):
    sep = "=" * 68
    print(f"\n{sep}")
    print(f"  CONFRONTO V1 (solo tecnica) vs V2 (tecnica + macro + settori)")
    print(f"  Periodo: {BT_START} -> {BT_END} | R:R 3:1 | SL=1.5x ATR weekly")
    print(f"  Capitale: {CAPITAL:,}EUR | Posizione: {TRADE_SIZE}EUR/trade")
    print(sep)
    print(f"  {'Metrica':<32} {'V1':>16} {'V2':>16}")
    print(f"  {'-'*64}")

    def row(label, v1, v2):
        print(f"  {label:<32} {str(v1):>16} {str(v2):>16}")

    row("Trade chiusi",         v1_sim["trades"],      v2_sim["trades"])
    row("WIN",                  v1_sim["wins"],         v2_sim["wins"])
    row("LOSS",                 v1_sim["losses"],       v2_sim["losses"])
    row("Win rate",             f"{v1_sim['wr']:.1f}%", f"{v2_sim['wr']:.1f}%")
    row("EV medio per trade",   f"{v1_sim['ev']:+.2f}%",f"{v2_sim['ev']:+.2f}%")
    print(f"  {'-'*64}")
    row("Capitale finale",      f"{v1_sim['final_bal']:,.0f}EUR", f"{v2_sim['final_bal']:,.0f}EUR")
    row("P&L totale",           f"{v1_sim['total_pnl']:+,.0f}EUR",f"{v2_sim['total_pnl']:+,.0f}EUR")
    row("Rendimento annualizzato",f"{v1_sim['ann_ret']:.1f}%",  f"{v2_sim['ann_ret']:.1f}%")
    print(f"  {'-'*64}")
    row("Max drawdown EUR",     f"-{v1_sim['max_dd_eur']:,.0f}EUR",f"-{v2_sim['max_dd_eur']:,.0f}EUR")
    row("Max drawdown %",       f"-{v1_sim['max_dd_pct']:.1f}%", f"-{v2_sim['max_dd_pct']:.1f}%")
    row("Max SL consecutivi",   v1_sim["max_consec"],  v2_sim["max_consec"])
    print(sep)

    all_years = sorted(set(list(v1_sim["yearly"]) + list(v2_sim["yearly"])))
    print(f"\n  {'Anno':<8} {'V1 P&L':>14} {'V2 P&L':>14} {'Diff':>10}")
    print(f"  {'-'*50}")
    for yr in all_years:
        p1 = v1_sim["yearly"].get(yr, 0)
        p2 = v2_sim["yearly"].get(yr, 0)
        print(f"  {yr:<8} {p1:>+13.0f}EUR {p2:>+13.0f}EUR {p2-p1:>+9.0f}EUR")
    print(sep)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_backtest_v1(all_data, top_n=3):
    """V1: selezione solo tecnica, senza contesto macro."""
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
                "entry": entry, "sl_pct": round((entry-sl)/entry*100, 2),
                "tp_pct": round((tp-entry)/entry*100, 2),
                "outcome": outcome, "pnl_pct": round((exit_price-entry)/entry*100, 2),
            })
    return pd.DataFrame(trades)


if __name__ == "__main__":
    all_tickers   = WATCHLIST_USA + WATCHLIST_EUROPE + list(WATCHLIST_INDICES.keys())
    macro_tickers = list(SECTOR_ETF.values()) + ["^VIX"]

    dl_start = "2019-01-01"
    dl_end   = datetime.today().strftime("%Y-%m-%d")

    print(f"Download dati WEEKLY {dl_start} -> {dl_end} per {len(all_tickers)} asset...")
    all_data = download_all(all_tickers, dl_start, dl_end, "1wk")
    print(f"Asset scaricati: {len(all_data)}/{len(all_tickers)}\n")

    print(f"Download dati macro (VIX + {len(SECTOR_ETF)} ETF settoriali)...")
    all_data_macro = download_all(macro_tickers, dl_start, dl_end, "1wk")
    print(f"Macro scaricati: {len(all_data_macro)}/{len(macro_tickers)}\n")

    print("Backtest V1 (solo tecnica)...")
    trades_v1 = run_backtest_v1(all_data, top_n=3)
    v1_sim    = simulate_capital(trades_v1)
    print(f"  Trade chiusi: {v1_sim['trades']} | WR: {v1_sim['wr']:.1f}% | Finale: {v1_sim['final_bal']:,.0f}EUR")

    print("\nBacktest V2 (tecnica + macro + settori)...")
    trades_v2 = run_backtest(all_data, all_data_macro, top_n=3)
    v2_sim    = simulate_capital(trades_v2)
    print(f"  Trade chiusi: {v2_sim['trades']} | WR: {v2_sim['wr']:.1f}% | Finale: {v2_sim['final_bal']:,.0f}EUR")

    print_report(v1_sim, v2_sim)

    trades_v1.to_csv("backtest_v1_results.csv", index=False)
    trades_v2.to_csv("backtest_v2_results.csv", index=False)
    print("\nRisultati salvati in backtest_v1_results.csv e backtest_v2_results.csv")
