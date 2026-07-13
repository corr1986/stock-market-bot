"""Entry giornaliero del bot Serenity (hold-60). Gira 1x/giorno pre-apertura USA.

Flusso:
1. clone/pull repo dati yan-labs, carica tweet, costruisce eventi freshness
2. classifica i nuovi eventi via Groq (cache serenity_stance_cache.json)
3. seleziona i segnali bullish freschi conv>=4 dall'ultima data processata
4. per ogni segnale (ticker non gia' aperto): scarica prezzo+ATR, crea posizione
   PENDING rispettando il capitale 50k. Il tracker la attivera' all'open reale.
5. salva portfolio_serenity.json, notifica Telegram [SERENITY]

Portfolio state: portfolio_serenity.json (+ campo last_signal_date).
"""
import json
import os
import subprocess
import tempfile
from datetime import date, datetime, timedelta

import pandas as pd

from serenity_data import load_tweets, build_fresh_events
from serenity_stance import classify_event, load_cache, save_cache
from serenity_signals import select_bullish
from serenity_live import plan_entry, invested_capital, CAPITAL_START, SIZE_EUR
from backtest_serenity import compute_atr, ATR_PERIOD
from notifier import send_telegram

HERE = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(HERE, "portfolio_serenity.json")
LOOKBACK_DAYS = 5  # al primo avvio / dopo gap, guarda gli ultimi N giorni


def load_portfolio():
    if not os.path.exists(PORTFOLIO_FILE):
        return {"balance": CAPITAL_START, "realized_pnl": 0.0,
                "open": [], "closed": [], "last_signal_date": None,
                "unrealized_pnl": 0.0}
    with open(PORTFOLIO_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_portfolio(pf):
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(pf, f, ensure_ascii=False, indent=2)


def ensure_repo():
    tmp = os.path.join(tempfile.gettempdir(), "serenity_repo")
    if not os.path.exists(tmp):
        subprocess.run(["git", "clone", "--depth", "1",
                        "https://github.com/yan-labs/serenity-aleabitoreddit.git", tmp],
                       check=True)
    else:
        subprocess.run(["git", "-C", tmp, "pull"], check=False)
    return os.path.join(tmp, "data", "aleabitoreddit_tweets.json")


def fetch_ref_and_atr(ticker):
    """(ultimo close, ATR(14)) via yfinance, o (None, None) se dati insufficienti."""
    import yfinance as yf
    df = yf.download(ticker, period="4mo", interval="1d",
                     progress=False, auto_adjust=True)
    if df is None or len(df) < ATR_PERIOD + 2:
        return None, None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    atr = compute_atr(df).iloc[-1]
    ref = float(df["Close"].iloc[-1])
    if pd.isna(atr) or atr <= 0:
        return None, None
    return ref, float(atr)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="mostra i segnali senza salvare portfolio/notificare")
    ap.add_argument("--lookback", type=int, default=LOOKBACK_DAYS,
                    help="giorni indietro da cui raccogliere segnali (cold-start: usa di piu')")
    args = ap.parse_args()

    pf = load_portfolio()
    tweets_path = ensure_repo()
    events = build_fresh_events(load_tweets(tweets_path))

    # 1. classifica i nuovi eventi (solo quelli recenti, per non riempire di storico)
    since = date.today() - timedelta(days=args.lookback)
    if pf.get("last_signal_date"):
        since = min(since, date.fromisoformat(pf["last_signal_date"]) + timedelta(days=1))
    from groq import Groq
    from config import GROQ_API_KEY
    client = Groq(api_key=GROQ_API_KEY)
    cache = load_cache()
    for e in events:
        if e["date"] >= since and f"{e['ticker']}:{e['tweet_ids'][0]}" not in cache:
            classify_event(e, client, cache)
    save_cache(cache)

    # 2. segnali bullish freschi da processare
    signals = select_bullish(events, cache, since)
    open_tickers = {p["ticker"] for p in pf["open"]}
    new_pending = []
    for sig in signals:
        if sig["ticker"] in open_tickers:
            continue
        ref, atr = fetch_ref_and_atr(sig["ticker"])
        if ref is None:
            print(f"  skip {sig['ticker']}: niente dati")
            continue
        if invested_capital(pf) + SIZE_EUR > CAPITAL_START:
            print("  capitale pieno, stop entry")
            break
        pos = plan_entry(sig["ticker"], ref, atr, sig["date"])
        if pos is None:
            continue
        pf["open"].append(pos)
        open_tickers.add(sig["ticker"])
        new_pending.append(pos)

    if args.dry_run:
        print(f"\n[DRY-RUN] since={since} | segnali bullish: {len(signals)} "
              f"({[s['ticker'] for s in signals]})")
        print(f"[DRY-RUN] entrerebbe in: "
              f"{[(p['ticker'], p['shares'], round(p['entry_ref'],2)) for p in new_pending]}")
        print("[DRY-RUN] nessun salvataggio, nessuna notifica.")
        return

    # 3. avanza la data processata
    if signals:
        pf["last_signal_date"] = max(s["date"] for s in signals).isoformat()
    save_portfolio(pf)

    # 4. notifica
    if new_pending:
        lines = ["*[SERENITY] Nuovi segnali BUY (pending)*", ""]
        for p in new_pending:
            lines.append(f"• `{p['ticker']}` ~{p['entry_ref']:.2f} · "
                         f"{p['shares']} az · SL {p['initial_sl']:.2f}")
        lines.append("")
        lines.append(f"Capitale impegnato: {invested_capital(pf):,.0f}€ / {CAPITAL_START:,.0f}€")
        send_telegram("\n".join(lines))
        print(f"Aggiunti {len(new_pending)} pending")
    else:
        print("Nessun nuovo segnale oggi")


if __name__ == "__main__":
    main()
