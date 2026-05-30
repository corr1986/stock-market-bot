"""
backtest_insider.py
-------------------
Confronto Bloomberg V2 con e senza Insider Signal (Form 4 SEC EDGAR via OpenInsider)

  A) Bloomberg V2 puro        — SL=2.0xATR, R:R 1:2, Top 3
  B) Bloomberg V2 + Insider   — stesso ma con bonus score per insider buying

Universo: 186 ticker USA (WATCHLIST_USA aggiornata)
Periodo:  2020-01-01 → 2026-04-30 (6.33 anni)
Capitale: 20.000 EUR | Trade size: 500 EUR

Fonte insider: OpenInsider (openinsider.com) — acquisti open-market > $25k
Cache:        market_data.pkl (price data) + insider_cache.pkl (transazioni insider)
"""

import os
import pickle
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from io import StringIO

from analyzer import compute_indicators, score_stock
from config import WATCHLIST_USA

# ---------------------------------------------------------------------------
# Parametri
# ---------------------------------------------------------------------------

CAPITAL       = 20_000
TRADE_SIZE    = 500
SAFETY_CAP    = 52
MIN_BARS      = 26
PRE_FILTER_N  = 20
TOP_N         = 3

BT_START = "2020-01-01"
BT_END   = "2026-04-30"

SL_MULT        = 2.0
RR             = 2.0
COMMISSION_EUR = 2.0

INSIDER_WINDOW_DAYS = 30    # Guarda indietro N giorni per insider signal
MIN_INSIDER_VALUE   = 25_000  # USD minimo per contare l'acquisto
INSIDER_BONUS_CLUSTER  = 3.0  # Bonus se 2+ insider hanno comprato
INSIDER_BONUS_SENIOR   = 1.5  # Bonus se CEO/CFO/President singolo > $50k
INSIDER_BONUS_DIRECTOR = 0.8  # Bonus se direttore/VP singolo > $25k

CACHE_PRICE   = os.path.join(os.path.dirname(__file__), "market_data.pkl")
CACHE_INSIDER = os.path.join(os.path.dirname(__file__), "insider_cache.pkl")

# Ruoli senior (segnale più forte)
SENIOR_ROLES = ['CEO', 'CFO', 'President', 'Chairman', 'COO', 'CTO', 'CIO',
                 'Chief Executive', 'Chief Financial', 'Chief Operating']


# ---------------------------------------------------------------------------
# Bloomberg V2 score (identico alla produzione)
# ---------------------------------------------------------------------------

def bloomberg_enhanced_score(ind: dict, insider_bonus: float = 0.0) -> float:
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

    return base + bonus + insider_bonus


# ---------------------------------------------------------------------------
# Download insider data da OpenInsider
# ---------------------------------------------------------------------------

def download_insider_data(tickers: list) -> pd.DataFrame:
    """
    Scarica storico acquisti insider da OpenInsider per tutti i ticker.
    Restituisce DataFrame con colonne:
      ticker, filing_date, insider_name, title, shares, price, value_usd
    """
    cached = _load_insider_cache()
    if cached is not None:
        return cached

    print(f"Download insider data da OpenInsider ({len(tickers)} ticker USA)...")
    all_rows = []

    for i, ticker in enumerate(tickers, 1):
        print(f"  {i}/{len(tickers)}: {ticker:<8}", end="", flush=True)
        try:
            # OpenInsider screener URL: solo acquisti open-market > $25k, tutti i ruoli
            url = (
                f"http://openinsider.com/screener"
                f"?s={ticker}&o=&pl={MIN_INSIDER_VALUE}&ph=&ll=&lh="
                f"&fd=-1&fdr=2019-01-01+-+2026-05-01"
                f"&td=0&tdr=&fdlyl=&fdlyh=&daysago="
                f"&xp=1&xs=0&xa=0&xd=0&xg=0&xf=0&xm=0&xxg=0&xss=0&xx=0"
                f"&sortcol=0&cnt=500&action=1"
            )
            headers = {"User-Agent": "Mozilla/5.0 (research bot) corradocuri@gmail.com"}
            resp = requests.get(url, headers=headers, timeout=15)

            if resp.status_code != 200:
                print(f"HTTP {resp.status_code}")
                time.sleep(1)
                continue

            tables = pd.read_html(StringIO(resp.text))
            if not tables:
                print("no table")
                time.sleep(0.5)
                continue

            df = tables[-1]  # OpenInsider usa l'ultima tabella
            if len(df) == 0:
                print("0 acquisti")
                time.sleep(0.3)
                continue

            # Normalizza colonne OpenInsider
            df.columns = [str(c).strip() for c in df.columns]

            # Mappa colonne possibili
            col_map = {}
            for c in df.columns:
                cl = c.lower()
                if 'filing' in cl and 'date' in cl: col_map['filing_date'] = c
                elif 'trade' in cl and 'date' in cl: col_map['trade_date'] = c
                elif 'insider' in cl or 'name' in cl: col_map['insider_name'] = c
                elif 'title' in cl or 'position' in cl: col_map['title'] = c
                elif 'qty' in cl or 'shares' in cl or '#shares' in cl: col_map['shares'] = c
                elif 'price' in cl: col_map['price'] = c
                elif 'value' in cl: col_map['value'] = c

            # Estrai righe
            for _, row in df.iterrows():
                try:
                    filing_date_raw = row.get(col_map.get('filing_date', ''), None)
                    if filing_date_raw is None or str(filing_date_raw).strip() in ['', 'nan']:
                        continue
                    filing_date = pd.to_datetime(str(filing_date_raw), errors='coerce')
                    if pd.isna(filing_date):
                        continue

                    shares_raw = row.get(col_map.get('shares', ''), 0)
                    price_raw  = row.get(col_map.get('price', ''), 0)
                    value_raw  = row.get(col_map.get('value', ''), 0)

                    # Pulisci valori numerici
                    shares = _parse_number(shares_raw)
                    price  = _parse_number(price_raw)
                    value  = _parse_number(value_raw)
                    if value == 0 and shares > 0 and price > 0:
                        value = shares * price

                    if value < MIN_INSIDER_VALUE:
                        continue

                    title = str(row.get(col_map.get('title', ''), '')).strip()
                    name  = str(row.get(col_map.get('insider_name', ''), '')).strip()

                    all_rows.append({
                        'ticker':       ticker,
                        'filing_date':  filing_date,
                        'insider_name': name,
                        'title':        title,
                        'shares':       shares,
                        'price':        price,
                        'value_usd':    value,
                    })
                except Exception:
                    continue

            n = sum(1 for r in all_rows if r['ticker'] == ticker)
            print(f"{n} acquisti")
            time.sleep(0.4)   # rate limit gentile

        except Exception as e:
            print(f"ERR: {e}")
            time.sleep(1)

    if not all_rows:
        print("WARN: nessun dato insider scaricato.")
        return pd.DataFrame()

    result = pd.DataFrame(all_rows)
    result['filing_date'] = pd.to_datetime(result['filing_date'])
    result = result.sort_values('filing_date').reset_index(drop=True)

    _save_insider_cache(result)
    print(f"\nTotale acquisti insider: {len(result)} su {result['ticker'].nunique()} ticker")
    return result


def _parse_number(val) -> float:
    try:
        s = str(val).replace(',', '').replace('$', '').replace('+', '').strip()
        return float(s)
    except Exception:
        return 0.0


def _load_insider_cache() -> pd.DataFrame | None:
    if not os.path.exists(CACHE_INSIDER):
        return None
    age = (datetime.now().timestamp() - os.path.getmtime(CACHE_INSIDER)) / 86400
    with open(CACHE_INSIDER, 'rb') as f:
        df = pickle.load(f)
    print(f"  Cache insider: {len(df)} record su {df['ticker'].nunique()} ticker ({age:.1f}gg fa)")
    return df


def _save_insider_cache(df: pd.DataFrame):
    with open(CACHE_INSIDER, 'wb') as f:
        pickle.dump(df, f)
    print(f"Cache insider salvata: {CACHE_INSIDER}")


# ---------------------------------------------------------------------------
# Calcolo insider score per data e ticker
# ---------------------------------------------------------------------------

def get_insider_score(ticker: str, signal_date, insider_df: pd.DataFrame) -> float:
    """
    Calcola il bonus score insider per un ticker a una data specifica.
    Considera solo acquisti con filing_date nei 30 giorni precedenti signal_date.
    """
    if insider_df.empty:
        return 0.0

    window_start = signal_date - timedelta(days=INSIDER_WINDOW_DAYS)
    mask = (
        (insider_df['ticker'] == ticker) &
        (insider_df['filing_date'] > window_start) &
        (insider_df['filing_date'] <= signal_date)
    )
    recent = insider_df[mask]

    if recent.empty:
        return 0.0

    # Conta acquirenti unici
    n_buyers = recent['insider_name'].nunique()

    if n_buyers >= 2:
        return INSIDER_BONUS_CLUSTER

    # Singolo acquisto — controlla ruolo
    row = recent.iloc[0]
    title = str(row['title']).upper()
    value = row['value_usd']

    is_senior = any(role.upper() in title for role in SENIOR_ROLES)

    if is_senior and value >= 50_000:
        return INSIDER_BONUS_SENIOR
    elif value >= MIN_INSIDER_VALUE:
        return INSIDER_BONUS_DIRECTOR

    return 0.0


# ---------------------------------------------------------------------------
# Selezione candidati (con e senza insider)
# ---------------------------------------------------------------------------

def get_top_candidates(all_data: dict, sig_date, top_n: int,
                       insider_df: pd.DataFrame, use_insider: bool) -> list:
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

    if use_insider:
        final = sorted(
            top20,
            key=lambda x: bloomberg_enhanced_score(
                x[1],
                insider_bonus=get_insider_score(x[0], sig_date, insider_df)
            ),
            reverse=True
        )
    else:
        final = sorted(top20, key=lambda x: bloomberg_enhanced_score(x[1]), reverse=True)

    return final[:top_n]


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
    return ("OPEN", float(future["Close"].iloc[-1]), n) if n else ("OPEN", entry, 0)


def process_signal(ticker, ind, all_data, sig_date):
    entry = ind["price"]
    atr   = ind.get("atr_14") or (entry * 0.02)
    sl    = round(entry - SL_MULT * atr, 4)
    tp    = round(entry + RR * SL_MULT * atr, 4)

    future = all_data[ticker][all_data[ticker].index > sig_date]
    if future.empty:
        return None

    outcome, exit_price, bars = simulate_trade(future, entry, sl, tp)
    pnl_pct  = (exit_price - entry) / entry * 100
    comm_pct = COMMISSION_EUR / TRADE_SIZE * 100 if outcome != "OPEN" else 0.0

    return {
        "date":      sig_date.strftime("%Y-%m-%d"),
        "year":      sig_date.year,
        "ticker":    ticker,
        "outcome":   outcome,
        "bars_held": bars,
        "pnl_pct":   round(pnl_pct - comm_pct, 4),
    }


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def run_backtest(all_data: dict, insider_df: pd.DataFrame, use_insider: bool,
                 top_n: int = TOP_N, label: str = "") -> pd.DataFrame:
    signal_dates = pd.date_range(BT_START, BT_END, freq="W-FRI")
    trades = []
    for sig_date in signal_dates:
        top = get_top_candidates(all_data, sig_date, top_n, insider_df, use_insider)
        for ticker, ind, _ in top:
            rec = process_signal(ticker, ind, all_data, sig_date)
            if rec:
                trades.append(rec)
    return pd.DataFrame(trades)


# ---------------------------------------------------------------------------
# Statistiche
# ---------------------------------------------------------------------------

def compute_stats(df: pd.DataFrame, label: str) -> dict:
    closed = df[df["outcome"].isin(["WIN", "LOSS", "TIMEOUT"])].copy()
    if closed.empty:
        return None

    wins     = closed[closed["outcome"] == "WIN"]
    losses   = closed[closed["outcome"] == "LOSS"]
    timeouts = closed[closed["outcome"] == "TIMEOUT"]

    wr      = len(wins) / len(closed) * 100
    avg_win = wins["pnl_pct"].mean()   if not wins.empty   else 0
    avg_los = losses["pnl_pct"].mean() if not losses.empty else 0
    ev_pct  = (wr / 100) * avg_win + (1 - wr / 100) * avg_los

    total_pnl  = (closed["pnl_pct"] / 100 * TRADE_SIZE).sum()
    net_profit = total_pnl - max(0, total_pnl * 0.26)
    ann_net    = net_profit / 6.33

    # Max drawdown (peak-to-trough)
    balance = CAPITAL
    balances = []
    for _, row in closed.sort_values("date").iterrows():
        balance += row["pnl_pct"] / 100 * TRADE_SIZE
        balances.append(balance)
    bal_arr = np.array(balances) if balances else np.array([CAPITAL])
    peak    = np.maximum.accumulate(bal_arr)
    max_dd  = ((bal_arr - peak) / peak * 100).min()

    # Max SL consecutivi
    max_cl = curr = 0
    for _, row in closed.sort_values("date").iterrows():
        if row["outcome"] == "LOSS":
            curr += 1; max_cl = max(max_cl, curr)
        else:
            curr = 0

    yearly = {}
    for _, row in closed.sort_values("date").iterrows():
        yr = int(row["year"])
        yearly[yr] = yearly.get(yr, 0) + row["pnl_pct"] / 100 * TRADE_SIZE

    return {
        "label":        label,
        "trades":       len(closed),
        "wins":         len(wins),
        "losses":       len(losses),
        "timeouts":     len(timeouts),
        "win_rate":     round(wr, 1),
        "avg_win":      round(avg_win, 2),
        "avg_loss":     round(avg_los, 2),
        "ev_pct":       round(ev_pct, 3),
        "ev_eur":       round(ev_pct / 100 * TRADE_SIZE, 2),
        "ann_net_eur":  round(ann_net, 0),
        "ann_pct":      round(ann_net / CAPITAL * 100, 1),
        "max_dd":       round(max_dd, 1),
        "max_consec_l": max_cl,
        "avg_bars":     round(closed["bars_held"].mean(), 1),
        "yearly":       yearly,
        "pnl_series":   closed["pnl_pct"].values,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    SEP  = "=" * 96
    SEP2 = "-" * 92

    print(SEP)
    print("  BLOOMBERG V2  vs  BLOOMBERG V2 + INSIDER SIGNAL")
    print(f"  SL={SL_MULT}xATR  R:R 1:{int(RR)}  |  Top {TOP_N}/sett.  |  2020-2026 (6.33 anni)")
    print(f"  Insider window: {INSIDER_WINDOW_DAYS}gg  |  Min value: ${MIN_INSIDER_VALUE:,}")
    print(SEP)

    # Carica price data
    print("\nCaricamento price data...")
    with open(CACHE_PRICE, "rb") as f:
        all_data = pickle.load(f)

    # Filtra solo ticker USA (186)
    usa_data = {t: df for t, df in all_data.items() if t in WATCHLIST_USA}
    print(f"Ticker USA disponibili nel cache: {len(usa_data)}")

    # Scarica/carica insider data
    print("\nCaricamento insider data...")
    insider_df = download_insider_data(WATCHLIST_USA)

    if not insider_df.empty:
        tickers_with_buys = insider_df['ticker'].nunique()
        total_buys        = len(insider_df)
        print(f"  Ticker con almeno 1 acquisto: {tickers_with_buys}/{len(WATCHLIST_USA)}")
        print(f"  Acquisti totali nel periodo:  {total_buys}")
        print(f"  Top ticker per acquisti:")
        top_ins = insider_df['ticker'].value_counts().head(10)
        for t, n in top_ins.items():
            total_val = insider_df[insider_df['ticker'] == t]['value_usd'].sum()
            print(f"    {t:8s} {n:3d}x  ${total_val/1e6:.1f}M")

    # Backtest
    print(f"\n[1/2] Bloomberg V2 PURO (senza insider)...")
    df_base = run_backtest(usa_data, insider_df, use_insider=False)
    s_base  = compute_stats(df_base, f"Bloomberg V2 Puro       (Top {TOP_N})")

    print(f"[2/2] Bloomberg V2 + INSIDER (con bonus insider)...")
    df_ins = run_backtest(usa_data, insider_df, use_insider=True)
    s_ins  = compute_stats(df_ins, f"Bloomberg V2 + Insider  (Top {TOP_N})")

    # Tabella comparativa
    print(f"\n\n{SEP}")
    print("  RISULTATI COMPARATIVI")
    print(SEP)
    hdr = (f"  {'Strategia':<28} {'Trade':>6} {'WR%':>6} {'AvgWIN':>8} {'AvgLSS':>8} "
           f"{'EV EUR':>8} {'AnnNet':>9} {'Ann%':>6} {'MaxDD':>7} {'MaxSL-':>7} {'AvgWks':>7}")
    print(hdr)
    print(f"  {SEP2}")

    for s in [s_base, s_ins]:
        if not s:
            continue
        marker = "  <-- INSIDER" if "Insider" in s["label"] else ""
        print(
            f"  {s['label']:<28} "
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
            f"{marker}"
        )

    print(f"  {SEP2}")
    print(SEP)

    # Dettaglio annuale confronto
    print(f"\n  Anno-per-anno: PURO vs INSIDER")
    print(f"  {'Anno':<6} {'Puro lordo':>12} {'Insider lordo':>14} {'Delta':>8}")
    print(f"  {'-'*44}")
    all_years = sorted(set(list(s_base["yearly"].keys()) + list(s_ins["yearly"].keys())))
    for yr in all_years:
        g_base = s_base["yearly"].get(yr, 0)
        g_ins  = s_ins["yearly"].get(yr, 0)
        delta  = g_ins - g_base
        marker = " +" if delta > 50 else (" -" if delta < -50 else "  ")
        print(f"  {yr:<6} {g_base:>+11.0f}E {g_ins:>+13.0f}E {delta:>+7.0f}E{marker}")

    print(f"\n{SEP}")
    print("  DISTRIBUZIONE PnL% per trade")
    print(f"  {'-'*72}")
    for s in [s_base, s_ins]:
        if not s:
            continue
        p = s["pnl_series"]
        print(f"  {s['label'][:24]:<24} "
              f"P10={np.percentile(p,10):+5.1f}%  "
              f"Med={np.percentile(p,50):+5.1f}%  "
              f"P90={np.percentile(p,90):+5.1f}%  "
              f"Std={p.std():5.2f}%")
    print(SEP)

    # Salva trades
    df_base.to_csv(os.path.join(os.path.dirname(__file__), "backtest_insider_base_trades.csv"), index=False)
    df_ins.to_csv(os.path.join(os.path.dirname(__file__), "backtest_insider_signal_trades.csv"), index=False)
    print("\nRisultati salvati:")
    print("  backtest_insider_base_trades.csv")
    print("  backtest_insider_signal_trades.csv")
    print(SEP)
