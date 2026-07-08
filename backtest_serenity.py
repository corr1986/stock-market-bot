"""Backtest FASE 1 strategia Serenity fresh-ticker.

Regole (spec docs/superpowers/specs/2026-07-08-serenity-signals-design.md):
- evento freshness + stance bullish conviction >= 4 -> BUY all'open del giorno dopo
- SL iniziale 2xATR(14), trailing Chandelier (riuso position_sizing), no TP
- rischio 40 EUR/trade, max 3 posizioni, VIX>30 blocca entry (get_regime_config)
Semplificazioni FASE 1 (documentate): niente earnings filter storico,
niente SELL anticipato su stance bearish, niente limite dinamico posizioni
nel regime cautious.
"""
import pandas as pd

from position_sizing import (
    calculate_size,
    calculate_chandelier_stop,
    get_regime_config,
    SL_MULT,
)

RISK_EUR = 40.0
BALANCE_START = 20000.0
MAX_POSITIONS = 3
ATR_PERIOD = 14
MIN_CONVICTION = 4


def compute_atr(df, period=ATR_PERIOD):
    """ATR classico (media mobile semplice del True Range)."""
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def simulate_trade(df, event_date, risk_eur=RISK_EUR):
    """Simula un singolo trade long dall'evento all'exit Chandelier.

    df: OHLC giornaliero (index datetime). Entry: open del primo giorno di borsa
    successivo a event_date. Ritorna dict trade o None se dati insufficienti.
    """
    atr = compute_atr(df)
    future = df[df.index.date > event_date]
    if future.empty:
        return None
    entry_idx = future.index[0]
    pos = df.index.get_loc(entry_idx)
    atr_entry = atr.iloc[pos - 1] if pos >= 1 else float("nan")
    if pd.isna(atr_entry) or atr_entry <= 0:
        return None

    entry = float(df.loc[entry_idx, "Open"])
    initial_sl = entry - SL_MULT * atr_entry
    # solo azioni intere: size teorica -> floor in unita', minimo 1 azione
    # (se 1 azione supera la size massima, rischio e size sforano il target)
    size_target = calculate_size(entry, atr_entry, risk_target=risk_eur)
    shares = max(1, int(size_target // entry))
    size_eur = shares * entry

    stop = initial_sl
    max_high = entry
    exit_price = None
    exit_date = None
    open_at_end = False

    path = df.iloc[pos:]
    for ts, row in path.iterrows():
        if float(row["Open"]) < stop:          # gap sotto lo stop
            exit_price, exit_date = float(row["Open"]), ts.date()
            break
        # lo stop non scatta sul Low del giorno di entry (SL piazzato dopo l'apertura)
        if float(row["Low"]) <= stop and ts != entry_idx:
            exit_price, exit_date = stop, ts.date()
            break
        max_high = max(max_high, float(row["High"]))
        stop = calculate_chandelier_stop(max_high, atr_entry, initial_sl)

    if exit_price is None:                     # ancora aperto a fine dati
        last = path.iloc[-1]
        exit_price, exit_date = float(last["Close"]), path.index[-1].date()
        open_at_end = True

    pnl_pct = (exit_price - entry) / entry
    return {
        "entry_date": entry_idx.date(),
        "entry": entry,
        "exit_date": exit_date,
        "exit": exit_price,
        "shares": shares,
        "size_eur": size_eur,
        "pnl_eur": shares * (exit_price - entry),
        "pnl_pct": pnl_pct * 100,
        "open_at_end": open_at_end,
    }


def _vix_at(vix, day):
    """Ultimo valore VIX disponibile <= day (None se nessuno)."""
    subset = vix[vix.index.date <= day]
    return float(subset.iloc[-1]) if len(subset) else None


def run_backtest(signals, prices, vix, risk_eur=RISK_EUR, max_positions=MAX_POSITIONS):
    """Simula tutti i segnali in ordine cronologico rispettando la concorrenza.

    signals: [{ticker, date, stance: {stance, conviction}}]
    prices: dict ticker -> DataFrame OHLC giornaliero
    vix: Series di chiusure ^VIX
    Ritorna lista trade (dict di simulate_trade + ticker/event_date).
    """
    open_until = []  # exit_date dei trade aperti
    trades = []
    for sig in sorted(signals, key=lambda s: s["date"]):
        stance = sig.get("stance") or {}
        if stance.get("stance") != "bullish" or stance.get("conviction", 0) < MIN_CONVICTION:
            continue
        df = prices.get(sig["ticker"])
        if df is None or df.empty:
            continue
        v = _vix_at(vix, sig["date"])
        if v is None or not get_regime_config(v)["allow_entry"]:
            continue

        trade = simulate_trade(df, sig["date"], risk_eur=risk_eur)
        if trade is None:
            continue
        # concorrenza: conta i trade ancora aperti alla data di entry
        open_until = [d for d in open_until if d >= trade["entry_date"]]
        if len(open_until) >= max_positions:
            continue
        open_until.append(trade["exit_date"])
        trade.update({"ticker": sig["ticker"], "event_date": sig["date"]})
        trades.append(trade)
    return trades


def compute_metrics(trades, balance_start=BALANCE_START):
    """Metriche aggregate sull'equity curve ordinata per data di exit."""
    if not trades:
        return {"n_trades": 0, "win_rate": 0.0, "total_pnl_eur": 0.0,
                "return_pct": 0.0, "max_drawdown_pct": 0.0}
    ordered = sorted(trades, key=lambda t: t["exit_date"])
    wins = sum(1 for t in ordered if t["pnl_eur"] > 0)
    total = sum(t["pnl_eur"] for t in ordered)

    equity = balance_start
    peak = balance_start
    max_dd = 0.0
    for t in ordered:
        equity += t["pnl_eur"]
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)

    return {
        "n_trades": len(ordered),
        "win_rate": wins / len(ordered) * 100,
        "total_pnl_eur": total,
        "return_pct": total / balance_start * 100,
        "max_drawdown_pct": max_dd * 100,
    }


def _download_prices(tickers, start, end):
    """Scarica OHLC daily per ticker via yfinance. Ritorna dict ticker->df (skip mancanti)."""
    import yfinance as yf
    prices = {}
    for t in tickers:
        try:
            df = yf.download(t, start=start, end=end, interval="1d",
                             progress=False, auto_adjust=True)
            if df is not None and isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df is not None and len(df) >= ATR_PERIOD + 2:
                prices[t] = df
        except Exception as e:
            print(f"  skip {t}: {e}")
    return prices


def main():
    import argparse
    import os
    import subprocess
    import tempfile
    from datetime import timedelta

    import yfinance as yf
    from groq import Groq

    from config import GROQ_API_KEY
    from serenity_data import load_tweets, build_fresh_events
    from serenity_stance import classify_event, load_cache, save_cache

    parser = argparse.ArgumentParser()
    parser.add_argument("--tweets", help="path aleabitoreddit_tweets.json (default: clona il repo)")
    parser.add_argument("--limit", type=int, default=0, help="max eventi da classificare (0=tutti)")
    parser.add_argument("--offline", action="store_true",
                        help="usa solo la cache stance, nessuna chiamata Groq")
    parser.add_argument("--max-positions", type=int, default=MAX_POSITIONS,
                        help="max posizioni contemporanee (0=illimitate)")
    args = parser.parse_args()

    # 1. archivio tweet
    if args.tweets:
        tweets_path = args.tweets
    else:
        tmp = os.path.join(tempfile.gettempdir(), "serenity_repo")
        if not os.path.exists(tmp):
            subprocess.run(["git", "clone", "--depth", "1",
                            "https://github.com/yan-labs/serenity-aleabitoreddit.git", tmp],
                           check=True)
        else:
            subprocess.run(["git", "-C", tmp, "pull"], check=False)
        tweets_path = os.path.join(tmp, "data", "aleabitoreddit_tweets.json")

    tweets = load_tweets(tweets_path)
    events = build_fresh_events(tweets)
    print(f"Tweet: {len(tweets)} | Eventi freshness: {len(events)}")
    if args.limit:
        events = events[:args.limit]

    # 2. classificazione stance (cache su disco, resume-safe)
    client = None if args.offline else Groq(api_key=GROQ_API_KEY)
    cache = load_cache()
    signals = []
    for i, e in enumerate(events):
        stance = classify_event(e, client, cache)
        if stance:
            signals.append({"ticker": e["ticker"], "date": e["date"], "stance": stance})
        if (i + 1) % 25 == 0:
            save_cache(cache)
            print(f"  classificati {i + 1}/{len(events)}")
    save_cache(cache)
    bullish = [s for s in signals
               if s["stance"]["stance"] == "bullish"
               and s["stance"]["conviction"] >= MIN_CONVICTION]
    print(f"Segnali bullish conviction>={MIN_CONVICTION}: {len(bullish)}")
    if not bullish:
        print("Nessun segnale: stop.")
        return

    # 3. prezzi + VIX
    start = min(s["date"] for s in bullish) - timedelta(days=60)
    end = max(t["date"].date() for t in tweets) + timedelta(days=1)
    tickers = sorted({s["ticker"] for s in bullish})
    print(f"Download prezzi per {len(tickers)} ticker...")
    prices = _download_prices(tickers, start, end)
    print(f"Prezzi disponibili per {len(prices)}/{len(tickers)} ticker")
    vix_df = yf.download("^VIX", start=start, end=end, interval="1d", progress=False)
    if isinstance(vix_df.columns, pd.MultiIndex):
        vix_df.columns = vix_df.columns.get_level_values(0)
    vix = vix_df["Close"]

    # 4. simulazione + report
    max_pos = args.max_positions if args.max_positions > 0 else 10**9
    trades = run_backtest(bullish, prices, vix, max_positions=max_pos)
    m = compute_metrics(trades)
    print("\n=== BACKTEST SERENITY (FASE 1) ===")
    print(f"Trade: {m['n_trades']} | WR: {m['win_rate']:.1f}% | "
          f"PnL: {m['total_pnl_eur']:+.0f} EUR ({m['return_pct']:+.2f}%) | "
          f"MaxDD: {m['max_drawdown_pct']:.2f}%")
    still_open = sum(1 for t in trades if t.get("open_at_end"))
    print(f"Posizioni ancora aperte a fine periodo: {still_open}")

    out = pd.DataFrame(trades)
    out.to_csv("backtest_serenity_trades.csv", index=False)
    print("Trade salvati in backtest_serenity_trades.csv")


if __name__ == "__main__":
    main()
