"""Esperimenti sulle strategie di USCITA per i segnali Serenity.

Confronta 5 modelli di exit a parita' di segnali (bullish conv>=4, azioni intere,
posizioni illimitate, capitale 20k). Obiettivo: capire se catturare i multi-bagger
di Serenity con exit piu' larghe/lunghe batte le uscite rapide di v1/v3.

Modelli:
  B1  v1        SL=entry-2ATR, TP=entry+4ATR (2:1)          [baseline v1]
  B2  v3        SL=entry-2ATR, trailing Chandelier 2ATR      [baseline v3]
  E1  partial   vendi meta' a +4ATR, resto trailing 3ATR     [TP parziale]
  E2  conv5     come v1 ma solo segnali conviction==5         [filtro qualita']
  E3  hold60    nessun TP, esci dopo 60gg o su stance bearish [hold temporale]

Uso: ./venv/Scripts/python.exe experiments_serenity_exits.py [--tweets PATH]
Offline: usa solo la cache stance esistente, zero chiamate API.
"""
import argparse
import os
import sys
from datetime import timedelta

import pandas as pd

from serenity_data import load_tweets, build_fresh_events
from serenity_stance import load_cache
from backtest_serenity import _download_prices, compute_atr, MIN_CONVICTION

CAPITAL = 20_000.0
SIZE_EUR = 500.0
ATR_P = 14
HOLD_DAYS = 60


def _entry(df, event_date):
    """(entry_idx, pos, entry_price, atr_entry) o None se dati insufficienti."""
    atr = compute_atr(df, ATR_P)
    future = df[df.index.date > event_date]
    if future.empty:
        return None
    entry_idx = future.index[0]
    pos = df.index.get_loc(entry_idx)
    atr_e = atr.iloc[pos - 1] if pos >= 1 else float("nan")
    entry = float(df.loc[entry_idx, "Open"])
    if pd.isna(atr_e) or atr_e <= 0 or entry <= 0:
        return None
    return entry_idx, pos, entry, float(atr_e)


def _shares(entry):
    return max(1, int(SIZE_EUR // entry))


def sim_v1(df, event_date, **_):
    e = _entry(df, event_date)
    if not e:
        return None
    entry_idx, pos, entry, atr = e
    sh = _shares(entry)
    sl, tp = entry - 2 * atr, entry + 4 * atr
    for ts, row in df.iloc[pos:].iterrows():
        o, h, l = float(row["Open"]), float(row["High"]), float(row["Low"])
        if ts != entry_idx and o <= sl:
            return _t(entry_idx, ts, sh, entry, o)
        if ts != entry_idx and o >= tp:
            return _t(entry_idx, ts, sh, entry, o)
        if l <= sl:
            return _t(entry_idx, ts, sh, entry, sl)
        if h >= tp:
            return _t(entry_idx, ts, sh, entry, tp)
    last = df.iloc[-1]
    return _t(entry_idx, df.index[-1], sh, entry, float(last["Close"]), True)


def sim_v3(df, event_date, **_):
    e = _entry(df, event_date)
    if not e:
        return None
    entry_idx, pos, entry, atr = e
    sh = _shares(entry)
    initial_sl = entry - 2 * atr
    stop, max_high = initial_sl, entry
    for ts, row in df.iloc[pos:].iterrows():
        o, h, l = float(row["Open"]), float(row["High"]), float(row["Low"])
        if o < stop:
            return _t(entry_idx, ts, sh, entry, o)
        if ts != entry_idx and l <= stop:
            return _t(entry_idx, ts, sh, entry, stop)
        max_high = max(max_high, h)
        stop = max(max_high - 2 * atr, initial_sl)
    last = df.iloc[-1]
    return _t(entry_idx, df.index[-1], sh, entry, float(last["Close"]), True)


def sim_partial(df, event_date, **_):
    """Vendi meta' a +4ATR, resto con trailing 3ATR. PnL somma delle due gambe."""
    e = _entry(df, event_date)
    if not e:
        return None
    entry_idx, pos, entry, atr = e
    sh = _shares(entry)
    half = sh // 2
    rest = sh - half
    tp1 = entry + 4 * atr
    initial_sl = entry - 2 * atr
    stop, max_high = initial_sl, entry
    half_done = False
    pnl = 0.0
    exit_ts = df.index[-1]
    for ts, row in df.iloc[pos:].iterrows():
        o, h, l = float(row["Open"]), float(row["High"]), float(row["Low"])
        # stop sull'intera posizione residua
        if o < stop:
            pnl += (rest if half_done else sh) * (o - entry)
            exit_ts = ts
            return _raw(entry_idx, exit_ts, sh, entry, pnl)
        if ts != entry_idx and l <= stop:
            pnl += (rest if half_done else sh) * (stop - entry)
            exit_ts = ts
            return _raw(entry_idx, exit_ts, sh, entry, pnl)
        # prima gamba: TP a 4ATR
        if not half_done and half > 0 and h >= tp1:
            pnl += half * (tp1 - entry)
            half_done = True
        max_high = max(max_high, h)
        trail = 3 * atr if half_done else 2 * atr
        stop = max(max_high - trail, initial_sl)
        exit_ts = ts
    # fine dati: chiudi il residuo al close
    close = float(df.iloc[-1]["Close"])
    pnl += (rest if half_done else sh) * (close - entry)
    return _raw(entry_idx, exit_ts, sh, entry, pnl, True)


def sim_hold(df, event_date, bearish_dates=(), **_):
    """Nessun TP: esci dopo HOLD_DAYS, su stance bearish, o su SL -2ATR."""
    e = _entry(df, event_date)
    if not e:
        return None
    entry_idx, pos, entry, atr = e
    sh = _shares(entry)
    sl = entry - 2 * atr
    deadline = entry_idx.date() + timedelta(days=HOLD_DAYS)
    next_bear = min((d for d in bearish_dates if d > event_date), default=None)
    for ts, row in df.iloc[pos:].iterrows():
        o, l = float(row["Open"]), float(row["Low"])
        d = ts.date()
        if ts != entry_idx and o <= sl:
            return _t(entry_idx, ts, sh, entry, o)
        if l <= sl:
            return _t(entry_idx, ts, sh, entry, sl)
        if d >= deadline or (next_bear and d >= next_bear):
            return _t(entry_idx, ts, sh, entry, float(row["Close"]))
    last = df.iloc[-1]
    return _t(entry_idx, df.index[-1], sh, entry, float(last["Close"]), True)


def _t(entry_idx, exit_ts, sh, entry, exit_price, open_end=False):
    return _raw(entry_idx, exit_ts, sh, entry, sh * (exit_price - entry), open_end)


def _raw(entry_idx, exit_ts, sh, entry, pnl, open_end=False):
    return {"entry_date": entry_idx.date(),
            "exit_date": exit_ts.date() if hasattr(exit_ts, "date") else exit_ts,
            "shares": sh, "cost": sh * entry, "pnl_eur": pnl, "open_at_end": open_end}


def run(signals, prices, sim, bearish_by_ticker=None):
    trades = []
    for sig in sorted(signals, key=lambda s: s["date"]):
        df = prices.get(sig["ticker"])
        if df is None:
            continue
        bd = (bearish_by_ticker or {}).get(sig["ticker"], ())
        t = sim(df, sig["date"], bearish_dates=bd)
        if t:
            trades.append(t)
    return trades


def metrics(trades):
    if not trades:
        return {"n": 0, "wr": 0, "pnl": 0, "ret": 0, "mdd": 0}
    o = sorted(trades, key=lambda t: t["exit_date"])
    total = sum(t["pnl_eur"] for t in o)
    wins = sum(1 for t in o if t["pnl_eur"] > 0)
    eq = peak = CAPITAL
    mdd = 0.0
    for t in o:
        eq += t["pnl_eur"]
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak)
    return {"n": len(o), "wr": wins / len(o) * 100, "pnl": total,
            "ret": total / CAPITAL * 100, "mdd": mdd * 100}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tweets", default=os.path.join(
        os.environ.get("TEMP", "/tmp"), "serenity_repo", "data", "aleabitoreddit_tweets.json"))
    args = ap.parse_args()

    tweets = load_tweets(args.tweets)
    events = build_fresh_events(tweets)
    cache = load_cache()

    # segnali bullish conv>=4 + mappa delle date bearish per ticker (per E3)
    signals, sig5, bearish = [], [], {}
    for e in events:
        st = cache.get(f"{e['ticker']}:{e['tweet_ids'][0]}")
        if not st:
            continue
        if st["stance"] == "bearish":
            bearish.setdefault(e["ticker"], []).append(e["date"])
        if st["stance"] == "bullish" and st["conviction"] >= MIN_CONVICTION:
            signals.append({"ticker": e["ticker"], "date": e["date"]})
            if st["conviction"] == 5:
                sig5.append({"ticker": e["ticker"], "date": e["date"]})

    print(f"Segnali bullish conv>=4: {len(signals)} | di cui conv==5: {len(sig5)}")
    start = min(s["date"] for s in signals) - timedelta(days=60)
    end = max(t["date"].date() for t in tweets) + timedelta(days=1)
    prices = _download_prices(sorted({s["ticker"] for s in signals}), start, end)
    print(f"Prezzi: {len(prices)} ticker\n")

    rows = [
        ("B1 v1 (2:1 ATR)", run(signals, prices, sim_v1)),
        ("B2 v3 (Chandelier)", run(signals, prices, sim_v3)),
        ("E1 TP parziale", run(signals, prices, sim_partial)),
        ("E2 conv==5 (v1 exit)", run(sig5, prices, sim_v1)),
        ("E3 hold 60gg/bearish", run(signals, prices, sim_hold, bearish)),
    ]
    print(f"{'Modello':<24}{'Trade':>6}{'WR%':>7}{'PnL EUR':>11}{'Ret%':>8}{'MaxDD%':>8}")
    print("-" * 64)
    for name, trades in rows:
        m = metrics(trades)
        print(f"{name:<24}{m['n']:>6}{m['wr']:>7.1f}{m['pnl']:>+11.0f}"
              f"{m['ret']:>+8.2f}{m['mdd']:>8.2f}")


if __name__ == "__main__":
    main()
