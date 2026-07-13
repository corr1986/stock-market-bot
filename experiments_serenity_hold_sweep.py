# Ottimizzazione parametro hold: 45/60/90/120 giorni + variante trailing-only (no deadline).
# Riusa i moduli del repo. Modello: entry open giorno dopo, SL -2ATR, no TP,
# esci su deadline / stance bearish / SL. Variante trailing: Chandelier largo 3ATR, no deadline.
import sys, os
REPO = r"C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot"
sys.path.insert(0, REPO); os.chdir(REPO)
from datetime import timedelta
import pandas as pd
import experiments_serenity_exits as ex
from serenity_data import load_tweets, build_fresh_events
from serenity_stance import load_cache
from backtest_serenity import _download_prices, compute_atr, MIN_CONVICTION

TWEETS = os.path.join(os.environ["TEMP"], "serenity_repo", "data", "aleabitoreddit_tweets.json")

def sim_hold_days(df, event_date, bearish_dates=(), days=60):
    ex.HOLD_DAYS = days
    return ex.sim_hold(df, event_date, bearish_dates=bearish_dates)

def sim_trail_only(df, event_date, bearish_dates=(), trail_mult=3.0):
    """Nessuna deadline: trailing Chandelier largo, esci su SL/trail o stance bearish."""
    e = ex._entry(df, event_date)
    if not e: return None
    entry_idx, pos, entry, atr = e
    sh = ex._shares(entry)
    initial_sl = entry - 2*atr
    stop, max_high = initial_sl, entry
    nb = min((d for d in bearish_dates if d > event_date), default=None)
    for ts, row in df.iloc[pos:].iterrows():
        o, h, l = float(row["Open"]), float(row["High"]), float(row["Low"])
        if o < stop: return ex._t(entry_idx, ts, sh, entry, o)
        if ts != entry_idx and l <= stop: return ex._t(entry_idx, ts, sh, entry, stop)
        if nb and ts.date() >= nb: return ex._t(entry_idx, ts, sh, entry, float(row["Close"]))
        max_high = max(max_high, h)
        stop = max(max_high - trail_mult*atr, initial_sl)
    last = df.iloc[-1]
    return ex._t(entry_idx, df.index[-1], sh, entry, float(last["Close"]), True)

tweets = load_tweets(TWEETS)
events = build_fresh_events(tweets)
cache = load_cache()
signals, bearish = [], {}
for e in events:
    st = cache.get(f"{e['ticker']}:{e['tweet_ids'][0]}")
    if not st: continue
    if st["stance"] == "bearish": bearish.setdefault(e["ticker"], []).append(e["date"])
    if st["stance"] == "bullish" and st["conviction"] >= MIN_CONVICTION:
        signals.append({"ticker": e["ticker"], "date": e["date"]})
start = min(s["date"] for s in signals) - timedelta(days=60)
end = max(t["date"].date() for t in tweets) + timedelta(days=1)
prices = _download_prices(sorted({s["ticker"] for s in signals}), start, end)
print(f"Segnali: {len(signals)} | prezzi: {len(prices)} ticker\n")

print(f"{'Variante hold':<26}{'Trade':>6}{'WR%':>7}{'PnL EUR':>11}{'Ret%':>8}{'MaxDD%':>8}{'aperti':>8}")
print("-"*74)
configs = [(f"deadline {d}gg", lambda df,ed,bd,d=d: sim_hold_days(df,ed,bd,d)) for d in (45,60,90,120)]
configs += [("trailing 3ATR (no dl)", lambda df,ed,bd: sim_trail_only(df,ed,bd,3.0)),
            ("trailing 4ATR (no dl)", lambda df,ed,bd: sim_trail_only(df,ed,bd,4.0))]
for name, fn in configs:
    trades = []
    for sig in sorted(signals, key=lambda s: s["date"]):
        df = prices.get(sig["ticker"])
        if df is None: continue
        t = fn(df, sig["date"], bearish.get(sig["ticker"], ()))
        if t: trades.append(t)
    m = ex.metrics(trades)
    op = sum(1 for t in trades if t.get("open_at_end"))
    print(f"{name:<26}{m['n']:>6}{m['wr']:>7.1f}{m['pnl']:>+11.0f}{m['ret']:>+8.2f}{m['mdd']:>8.2f}{op:>8}")
