"""
backtest_midcap.py
------------------
Confronto Bloomberg V2 — Large Cap (S&P 500) vs Mid Cap (S&P 400).
Config ottimale: SL=2.0xATR  R:R 1:2  (la migliore per EV e stabilita).

Mid-cap watchlist: ~120 componenti S&P 400 disponibili su Trade Republic,
scelti per coprire tutti i settori e avere storia almeno dal 2020.

Output: tabella comparativa + dettaglio annuale per entrambi i gruppi.
"""

import os
import pickle
import pandas as pd
import numpy as np
from datetime import datetime
import yfinance as yf
from analyzer import compute_indicators, score_stock

# ---------------------------------------------------------------------------
# Parametri backtest
# ---------------------------------------------------------------------------

CAPITAL    = 20_000
TRADE_SIZE = 500
SAFETY_CAP = 52      # max settimane per trade
MIN_BARS   = 26
PRE_FILTER_N = 20
TOP_N = 3

BT_START = "2020-01-01"
BT_END   = "2026-04-30"

SL_MULT = 2.0   # ATR multiplier per SL
RR      = 2.0   # Risk:Reward ratio (TP = entry + RR * SL_dist)

COMMISSION_EUR = 2.0  # Trade Republic: 1 EUR/ordine x2

CACHE_LARGE = os.path.join(os.path.dirname(__file__), "market_data.pkl")
CACHE_MID   = os.path.join(os.path.dirname(__file__), "market_data_midcap.pkl")

# ---------------------------------------------------------------------------
# Watchlist Mid Cap (S&P 400) — disponibili su Trade Republic
# ---------------------------------------------------------------------------

WATCHLIST_MIDCAP = [
    # --- Technology / Software (25) ---
    "PAYC",   # Paycom Software
    "MANH",   # Manhattan Associates
    "PCTY",   # Paylocity
    "QLYS",   # Qualys
    "APPF",   # AppFolio
    "NCNO",   # nCino
    "ALRM",   # Alarm.com
    "JAMF",   # JAMF Holding
    "BILL",   # Bill Holdings
    "ZI",     # ZoomInfo
    "PAYO",   # Payoneer
    "DOCS",   # Doximity
    "HUBS",   # HubSpot (mid nel 2020)
    "PRGS",   # Progress Software
    "CEVA",   # CEVA Inc
    "NTCT",   # NetScout Systems
    "EVTC",   # Evertec
    "CNXC",   # Concentrix
    "CARG",   # CarGurus
    "SMAR",   # Smartsheet
    "TNET",   # TriNet Group
    "TASK",   # TaskUs
    "BLKB",   # Blackbaud
    "FOUR",   # Shift4 Payments
    "PVBC",   # ProvidentBancorp (skip - small)

    # --- Healthcare (20) ---
    "MMSI",   # Merit Medical Systems
    "OMCL",   # Omnicell
    "ACAD",   # Acadia Pharmaceuticals
    "EXAS",   # Exact Sciences
    "HALO",   # Halozyme Therapeutics
    "ITGR",   # Integer Holdings
    "PRVA",   # Privia Health
    "ACLS",   # Axcelis Technologies (semi/med)
    "AGIO",   # Agios Pharmaceuticals
    "PRCT",   # Procept BioRobotics
    "PGNY",   # Progyny
    "LNTH",   # Lantheus Holdings
    "NUVL",   # Nuvalent
    "TGTX",   # TG Therapeutics
    "INVA",   # Innoviva
    "IMVT",   # Immunovant
    "ENSG",   # Ensign Group
    "AMED",   # Amedisys
    "CHCO",   # City Holding
    "MLAB",   # Mesa Labs

    # --- Financials (20) ---
    "BOKF",   # BOK Financial
    "WSFS",   # WSFS Financial
    "WBS",    # Webster Financial
    "ONB",    # Old National Bancorp
    "SBCF",   # Seacoast Banking
    "EWBC",   # East West Bancorp
    "COLB",   # Columbia Banking
    "BANF",   # BancFirst
    "CVBF",   # CVB Financial
    "WABC",   # Westamerica Bancorporation
    "PFSI",   # PennyMac Financial
    "GPOR",   # Gulfport Energy
    "SIGI",   # Selective Insurance
    "HCI",    # HCI Group
    "KNTK",   # Kinetik Holdings
    "RYAN",   # Ryan Specialty Holdings
    "BRP",    # BRP Group
    "DBRG",   # DigitalBridge
    "HLNE",   # Hamilton Lane
    "APAM",   # Artisan Partners

    # --- Consumer Discretionary (20) ---
    "FIVE",   # Five Below
    "DKS",    # Dick's Sporting Goods
    "DECK",   # Deckers Outdoor (HOKA/UGG)
    "BOOT",   # Boot Barn
    "WING",   # Wingstop
    "CBRL",   # Cracker Barrel
    "GPI",    # Group 1 Automotive
    "LAD",    # Lithia Motors
    "PRGS",   # skip dup
    "MODG",   # Acushnet Holdings
    "GRMN",   # Garmin (swiss-listed, skip)
    "SBH",    # Sally Beauty
    "HLLY",   # Holley
    "LESL",   # Leslie's
    "ARKO",   # ARKO Corp
    "PTLO",   # Portillo's
    "FAT",    # FAT Brands
    "DENN",   # Denny's
    "PLAY",   # Dave & Buster's
    "GOLF",   # Acushnet

    # --- Consumer Staples (8) ---
    "MGPI",   # MGP Ingredients
    "POST",   # Post Holdings
    "LANC",   # Lancaster Colony
    "USFD",   # US Foods Holding
    "PFGC",   # Performance Food Group
    "FRPT",   # Freshpet
    "CENTA",  # Central Garden & Pet
    "UFPT",   # UFP Technologies

    # --- Industrials (18) ---
    "GNRC",   # Generac Holdings
    "AIT",    # Applied Industrial Technologies
    "EXPO",   # Exponent
    "MMS",    # Maximus
    "KTOS",   # Kratos Defense
    "BWXT",   # BWX Technologies
    "HXL",    # Hexcel
    "HLIO",   # Helios Technologies
    "LMB",    # Limbach Holdings
    "HAYW",   # Hayward Holdings
    "UFPI",   # UFP Industries
    "IBP",    # Installed Building Products
    "TREX",   # Trex Company
    "BCPC",   # Balchem
    "HWKN",   # Hawkins
    "KMPR",   # Kemper
    "WERN",   # Werner Enterprises
    "HUBG",   # Hub Group

    # --- Energy (10) ---
    "RRC",    # Range Resources
    "AR",     # Antero Resources
    "CIVI",   # Civitas Resources
    "CHRD",   # Chord Energy
    "VTLE",   # Vital Energy
    "SM",     # SM Energy
    "MTDR",   # Matador Resources
    "CTRA",   # Coterra Energy
    "NOG",    # Northern Oil & Gas
    "MGY",    # Magnolia Oil & Gas

    # --- Materials (8) ---
    "SLVM",   # Sylvamo
    "UFPI",   # UFP Industries (dup)
    "CLF",    # Cleveland-Cliffs
    "STLD",   # Steel Dynamics
    "CMC",    # Commercial Metals
    "KALU",   # Kaiser Aluminum
    "WOR",    # Worthington Enterprises
    "KWR",    # Quaker Chemical

    # --- Real Estate (8) ---
    "IIPR",   # Innovative Industrial Properties
    "STAG",   # Stag Industrial
    "PEB",    # Pebblebrook Hotel Trust
    "ALEX",   # Alexander & Baldwin
    "DEI",    # Douglas Emmett
    "UNIT",   # Uniti Group
    "NSA",    # National Storage Affiliates
    "ROIC",   # Retail Opportunity Investments

    # --- Utilities (5) ---
    "MGEE",   # MGE Energy
    "OTTR",   # Otter Tail
    "NWE",    # NorthWestern Energy
    "SPKE",   # Spark Energy
    "GWRS",   # Global Water Resources
]

# Rimuovi duplicati mantenendo ordine
seen = set()
WATCHLIST_MIDCAP = [t for t in WATCHLIST_MIDCAP if not (t in seen or seen.add(t))]

print(f"Mid-cap watchlist: {len(WATCHLIST_MIDCAP)} ticker")


# ---------------------------------------------------------------------------
# Bloomberg V2 score (identico al simulatore principale)
# ---------------------------------------------------------------------------

def bloomberg_enhanced_score(ind: dict) -> float:
    base   = score_stock(ind)
    rsi    = ind.get("rsi_14") or 0
    vol    = ind.get("volume_ratio") or 0
    change = ind.get("weekly_change_pct") or 0
    sma50  = ind.get("above_sma50") or False

    bonus = 0.0
    if vol >= 1.5:       bonus += 2.0
    elif vol >= 1.2:     bonus += 0.5
    if 50 <= rsi <= 62:  bonus += 1.5
    elif 48 <= rsi < 50: bonus += 0.5
    elif rsi > 65:       bonus -= 2.0
    if change >= 2.0:    bonus += 1.5
    elif change >= 1.0:  bonus += 0.5
    if sma50:            bonus += 1.0

    return base + bonus


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def load_cache(tickers, cache_file, label):
    if os.path.exists(cache_file):
        age_days = (datetime.now().timestamp() - os.path.getmtime(cache_file)) / 86400
        if age_days < 7:
            with open(cache_file, "rb") as f:
                data = pickle.load(f)
            print(f"Cache {label} caricata ({age_days:.1f}gg) — {len(data)}/{len(tickers)} ticker")
            return data
        print(f"Cache {label} scaduta ({age_days:.1f}gg), re-download...")

    print(f"Download dati WEEKLY {label} ({len(tickers)} ticker)...")
    data = {}
    for i, ticker in enumerate(tickers, 1):
        print(f"\r  {i}/{len(tickers)}: {ticker:<12}", end="", flush=True)
        try:
            df = yf.download(
                ticker, start="1999-01-01",
                end=datetime.today().strftime("%Y-%m-%d"),
                interval="1wk", progress=False, auto_adjust=True
            )
            if not df.empty:
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                data[ticker] = df
        except Exception:
            pass
    print()
    with open(cache_file, "wb") as f:
        pickle.dump(data, f)
    print(f"Scaricati: {len(data)}/{len(tickers)}\n")
    return data


# ---------------------------------------------------------------------------
# Simulazione trade
# ---------------------------------------------------------------------------

def simulate_trade(future, entry, sl, tp):
    for i, (_, row) in enumerate(future.iterrows()):
        if i >= SAFETY_CAP:
            return "TIMEOUT", float(future["Close"].iloc[i - 1]), i
        if float(row["Low"]) <= sl:
            return "LOSS", sl, i + 1
        if float(row["High"]) >= tp:
            return "WIN", tp, i + 1
    n = len(future)
    if n:
        return "OPEN", float(future["Close"].iloc[-1]), n
    return "OPEN", entry, 0


# ---------------------------------------------------------------------------
# Backtest Bloomberg V2
# ---------------------------------------------------------------------------

def run_backtest(all_data):
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
                if not (score > 0 and (ind.get("macd_hist") or 0) > 0):
                    continue
                candidates.append((ticker, ind, score))
            except Exception:
                continue

        candidates.sort(key=lambda x: x[2], reverse=True)
        top20 = candidates[:PRE_FILTER_N]
        final = sorted(top20, key=lambda x: bloomberg_enhanced_score(x[1]), reverse=True)

        for ticker, ind, _ in final[:TOP_N]:
            entry = ind["price"]
            atr   = ind.get("atr_14") or (entry * 0.02)
            sl    = round(entry - SL_MULT * atr, 4)
            tp    = round(entry + RR * SL_MULT * atr, 4)

            future = all_data[ticker][all_data[ticker].index > sig_date]
            if future.empty:
                continue

            outcome, exit_price, bars_held = simulate_trade(future, entry, sl, tp)
            pnl_pct = (exit_price - entry) / entry * 100
            comm_pct = COMMISSION_EUR / TRADE_SIZE * 100 if outcome != "OPEN" else 0.0

            trades.append({
                "date":      sig_date.strftime("%Y-%m-%d"),
                "year":      sig_date.year,
                "ticker":    ticker,
                "entry":     round(entry, 4),
                "sl":        round(sl, 4),
                "tp":        round(tp, 4),
                "outcome":   outcome,
                "bars_held": bars_held,
                "pnl_pct":   round(pnl_pct - comm_pct, 4),
            })

    return pd.DataFrame(trades)


# ---------------------------------------------------------------------------
# Statistiche
# ---------------------------------------------------------------------------

def compute_stats(df, label):
    closed = df[df["outcome"].isin(["WIN", "LOSS", "TIMEOUT"])].copy()
    if closed.empty:
        return None

    wins     = closed[closed["outcome"] == "WIN"]
    losses   = closed[closed["outcome"] == "LOSS"]
    timeouts = closed[closed["outcome"] == "TIMEOUT"]

    wr = len(wins) / len(closed) * 100
    avg_win  = wins["pnl_pct"].mean() if not wins.empty else 0
    avg_loss = losses["pnl_pct"].mean() if not losses.empty else 0
    ev_pct   = (wr / 100) * avg_win + (1 - wr / 100) * avg_loss

    total_pnl = (closed["pnl_pct"] / 100 * TRADE_SIZE).sum()
    net_profit = total_pnl - max(0, total_pnl * 0.26)
    ann_net   = net_profit / 6.33

    # Drawdown
    balance = CAPITAL
    min_bal = CAPITAL
    for _, row in closed.sort_values("date").iterrows():
        balance += row["pnl_pct"] / 100 * TRADE_SIZE
        min_bal  = min(min_bal, balance)
    max_dd = (CAPITAL - min_bal) / CAPITAL * 100

    # Max SL consecutivi
    max_cl = curr = 0
    for _, row in closed.sort_values("date").iterrows():
        if row["outcome"] == "LOSS":
            curr += 1
            max_cl = max(max_cl, curr)
        else:
            curr = 0

    # Per anno
    yearly = {}
    for _, row in closed.sort_values("date").iterrows():
        yr = int(row["year"])
        pnl_eur = row["pnl_pct"] / 100 * TRADE_SIZE
        yearly[yr] = yearly.get(yr, 0) + pnl_eur

    # Unique tickers traded
    unique = closed["ticker"].nunique()
    top_tickers = (closed[closed["outcome"] == "WIN"]["ticker"]
                   .value_counts().head(5).to_dict())

    return {
        "label":       label,
        "trades":      len(closed),
        "wins":        len(wins),
        "losses":      len(losses),
        "timeouts":    len(timeouts),
        "win_rate":    round(wr, 1),
        "avg_win":     round(avg_win, 2),
        "avg_loss":    round(avg_loss, 2),
        "ev_pct":      round(ev_pct, 3),
        "ev_eur":      round(ev_pct / 100 * TRADE_SIZE, 2),
        "ann_net_eur": round(ann_net, 0),
        "ann_pct":     round(ann_net / CAPITAL * 100, 1),
        "max_dd":      round(max_dd, 1),
        "max_consec_l": max_cl,
        "avg_bars":    round(closed["bars_held"].mean(), 1),
        "unique_tkrs": unique,
        "yearly":      yearly,
        "top_wins":    top_tickers,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    SEP = "=" * 90

    print(SEP)
    print("  BLOOMBERG V2 — MID CAP vs LARGE CAP CONFRONTO")
    print(f"  SL={SL_MULT}xATR  R:R 1:{int(RR)}  |  Top {TOP_N}/sett.  |  2020-2026 (6.33 anni)")
    print(f"  Capitale {CAPITAL:,} EUR  |  Trade size {TRADE_SIZE} EUR  |  Tasse 26%  |  TR costs 2EUR RT")
    print(SEP)

    # --- Mid Cap ---
    print("\n[1/2] CARICAMENTO DATI MID CAP...")
    data_mid = load_cache(WATCHLIST_MIDCAP, CACHE_MID, "MID CAP")

    print(f"\n[1/2] BACKTEST MID CAP ({len(data_mid)} ticker disponibili)...")
    df_mid = run_backtest(data_mid)
    stats_mid = compute_stats(df_mid, f"Mid Cap S&P400 ({len(data_mid)} ticker)")
    df_mid.to_csv(os.path.join(os.path.dirname(__file__), "backtest_midcap_trades.csv"), index=False)

    # --- Large Cap (da cache esistente) ---
    print("\n[2/2] CARICAMENTO DATI LARGE CAP (cache esistente)...")
    from config import WATCHLIST_USA, WATCHLIST_EUROPE
    data_large = load_cache(WATCHLIST_USA + WATCHLIST_EUROPE, CACHE_LARGE, "LARGE CAP")

    print(f"\n[2/2] BACKTEST LARGE CAP ({len(data_large)} ticker disponibili)...")
    df_large = run_backtest(data_large)
    stats_large = compute_stats(df_large, f"Large Cap S&P500 ({len(data_large)} ticker)")

    # --- Report ---
    print(f"\n\n{SEP}")
    print(f"  RISULTATI COMPARATIVI — Bloomberg V2  SL=2.0xATR  R:R 1:2")
    print(SEP)

    hdr = (f"  {'Gruppo':<32} {'Trade':>6} {'WR%':>6} {'AvgWIN':>8} {'AvgLSS':>8} "
           f"{'EV EUR':>8} {'AnnNet':>9} {'Ann%':>6} {'MaxDD':>7} {'MaxSL-':>7} {'AvgWks':>7}")
    print(hdr)
    print(f"  {'-'*88}")

    for s in [stats_large, stats_mid]:
        if not s:
            continue
        print(
            f"  {s['label']:<32} "
            f"{s['trades']:>6} "
            f"{s['win_rate']:>5.1f}% "
            f"{s['avg_win']:>+7.1f}% "
            f"{s['avg_loss']:>+7.1f}% "
            f"{s['ev_eur']:>+8.2f} "
            f"{s['ann_net_eur']:>+8.0f}E "
            f"{s['ann_pct']:>+5.1f}% "
            f"{s['max_dd']:>+6.1f}% "
            f"{s['max_consec_l']:>7} "
            f"{s['avg_bars']:>7.1f}"
        )

    print(f"  {'-'*88}")
    print(SEP)

    # --- Dettaglio annuale ---
    for s in [stats_large, stats_mid]:
        if not s:
            continue
        print(f"\n  Dettaglio annuale — {s['label']}")
        print(f"  {'Anno':<8} {'PnL lordo':>12} {'Tasse 26%':>12} {'PnL netto':>12}")
        print(f"  {'-'*48}")
        total_gross = 0
        for yr in sorted(s["yearly"].keys()):
            gross = s["yearly"][yr]
            tax   = max(0, gross * 0.26)
            net   = gross - tax
            total_gross += gross
            print(f"  {yr:<8} {gross:>+11.0f}E {-tax:>+11.0f}E {net:>+11.0f}E")
        total_tax = max(0, total_gross * 0.26)
        print(f"  {'-'*48}")
        print(f"  {'TOTALE':<8} {total_gross:>+11.0f}E {-total_tax:>+11.0f}E {total_gross-total_tax:>+11.0f}E")
        print(f"  {'ANNUO':<8} {total_gross/6.33:>+11.0f}E {'':>12} {(total_gross-total_tax)/6.33:>+11.0f}E")

    # --- Top tickers vincenti mid cap ---
    if stats_mid:
        print(f"\n{SEP}")
        print(f"  TOP WIN TICKERS — Mid Cap (quante volte segnalato e vinto)")
        print(SEP)
        for t, cnt in stats_mid["top_wins"].items():
            print(f"  {t:<12} {cnt} volte")

    # --- Analisi rischio/volatilita ---
    print(f"\n{SEP}")
    print(f"  ANALISI DISTRIBUZIONE PnL%")
    print(SEP)

    for label, df in [("Large Cap", df_large), ("Mid Cap", df_mid)]:
        closed = df[df["outcome"].isin(["WIN", "LOSS", "TIMEOUT"])]
        if closed.empty:
            continue
        p = closed["pnl_pct"]
        print(f"  {label}:")
        print(f"    P10={np.percentile(p,10):+.1f}%  P25={np.percentile(p,25):+.1f}%  "
              f"Median={np.percentile(p,50):+.1f}%  P75={np.percentile(p,75):+.1f}%  "
              f"P90={np.percentile(p,90):+.1f}%")
        print(f"    Std={p.std():.2f}%  Skew={p.skew():.2f}  Max={p.max():+.1f}%  Min={p.min():+.1f}%\n")

    print(SEP)
    print("Risultati salvati in: backtest_midcap_trades.csv")
    print(SEP)
