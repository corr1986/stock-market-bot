import sys
import json
import os
from datetime import datetime, timezone
from analyzer import build_market_snapshot, pre_filter_snapshot, get_top_signals
from claude_analyst import generate_report       # v1: Groq/Llama (demo — gratuito)
# from claude_analyst_v3 import generate_report # v3: Anthropic API + web search (live)
from notifier import send_telegram
import math
from config import PORTFOLIO_START, TRADE_SIZE_EUR, MAX_OPEN_TRADES, TICKER_TO_NAME
import yfinance as yf

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "portfolio.json")


# ---------------------------------------------------------------------------
# Portfolio paper trading
# ---------------------------------------------------------------------------

def load_portfolio() -> dict:
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {
        "balance": PORTFOLIO_START,
        "realized_pnl": 0.0,
        "open": [],
        "closed": [],
    }


def save_portfolio(p: dict):
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(p, f, indent=2, ensure_ascii=False)


def add_new_positions(signals: list, entry_date: str):
    """Aggiunge posizioni pending al portfolio paper trading dai segnali già calcolati."""
    portfolio = load_portfolio()
    open_tickers = {p["ticker"] for p in portfolio["open"]}
    slots = MAX_OPEN_TRADES - len(portfolio["open"])

    if slots <= 0:
        print(f"Paper trading: {MAX_OPEN_TRADES} posizioni già aperte, nessuna nuova aggiunta.")
        return

    added = 0
    for sig in signals:
        if slots <= 0:
            break
        if sig["ticker"] in open_tickers:
            continue
        portfolio["open"].append({
            "id":          f"{sig['ticker']}_{entry_date}",
            "ticker":      sig["ticker"],
            "category":    sig["category"],
            "entry_date":  entry_date,
            "entry_price": None,    # impostato dal tracker all'apertura del mercato
            "sl":          None,
            "tp":          None,
            "atr":         sig["atr"],
            "trade_eur":   TRADE_SIZE_EUR,
            "status":      "pending",
        })
        added += 1
        slots -= 1
        print(f"  + {sig['ticker']} (pending — entry al prezzo di apertura mercato)")

    save_portfolio(portfolio)
    print(f"Paper trading: {added} nuova/e posizione/i aperta/e (tot. aperte: {len(portfolio['open'])}).")




# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run():
    today     = datetime.now().strftime("%d/%m/%Y")
    today_iso = datetime.now().strftime("%Y-%m-%d")
    print(f"[{today}] Stock Market Bot avviato")

    # 1. Download dati di mercato (una sola volta per tutto)
    print("Scaricamento dati di mercato...")
    snapshot  = build_market_snapshot()
    usa_count = len(snapshot["USA"])
    eu_count  = len(snapshot["EUROPE"])
    idx_count = len(snapshot["INDICES"])
    total     = usa_count + eu_count + idx_count
    print(f"Dati raccolti: {idx_count} indici, {usa_count} USA, {eu_count} Europa ({total} totali)")

    if total == 0:
        print("Nessun dato disponibile. Uscita.")
        sys.exit(1)

    # 2. Bloomberg V2 signals — calcolati UNA VOLTA, usati ovunque
    print("Calcolo segnali Bloomberg V2...")
    signals = get_top_signals(snapshot, n=MAX_OPEN_TRADES, sl_mult=2.0, rr=2.0)
    if signals:
        for s in signals:
            print(f"  {s['ticker']:8s} | score={s['score']} | bl={s['bl_score']} "
                  f"| SL={s['sl']} | TP={s['tp']}")
    else:
        print("  Nessun segnale generato questa settimana.")

    # 3. Salva segnali per place_orders.py (eseguito a mercato aperto)
    SIGNALS_FILE = os.path.join(os.path.dirname(__file__), "signals.json")
    with open(SIGNALS_FILE, "w", encoding="utf-8") as f:
        json.dump({"date": today_iso, "signals": signals}, f, indent=2)
    print(f"Segnali salvati in signals.json ({len(signals)} segnali)")

    # 4. Telegram — costruisci messaggio segnali
    # Tassi FX live via yfinance
    def _fx(sym, fallback):
        try:
            h = yf.Ticker(sym).history(period='5d', interval='1d')
            return float(h['Close'].iloc[-1]) if not h.empty else fallback
        except Exception:
            return fallback
    eurusd = _fx('EURUSD=X', 1.10)
    eurgbp = _fx('EURGBP=X', 0.86) * 100  # in pence per LSE

    signal_lines = []
    for s in signals:
        ticker    = s['ticker']
        entry     = s['entry_price']
        sl        = s['sl']
        tp        = s['tp']
        score     = s['bl_score']
        full_name = TICKER_TO_NAME.get(ticker, ticker)

        # Converti in EUR
        if any(ticker.endswith(sfx) for sfx in ['.DE', '.AS', '.PA', '.MC', '.MI']):
            cur = 'EUR'
            entry_eur, sl_eur, tp_eur = entry, sl, tp
        elif ticker.endswith('.L'):
            cur = 'GBP'
            entry_eur = round(entry * 100 / eurgbp, 2)
            sl_eur    = round(sl    * 100 / eurgbp, 2)
            tp_eur    = round(tp    * 100 / eurgbp, 2)
        elif ticker.startswith('^'):
            continue
        else:
            cur = 'USD'
            entry_eur = round(entry / eurusd, 2)
            sl_eur    = round(sl    / eurusd, 2)
            tp_eur    = round(tp    / eurusd, 2)

        sl_pct   = round((entry - sl) / entry * 100, 1)
        tp_pct   = round((tp - entry) / entry * 100, 1)
        qty      = math.ceil(TRADE_SIZE_EUR / entry_eur)   # arrotondamento per eccesso
        cost_eur = round(qty * entry_eur, 2)

        if cur == 'EUR':
            line = (f"*{ticker}* — {full_name} | score {score:.1f}\n"
                    f"  Quantita: *{qty} azioni* (~{cost_eur} EUR)\n"
                    f"  Entry: {entry:.2f} EUR\n"
                    f"  SL: {sl:.2f} EUR (-{sl_pct}%)\n"
                    f"  TP: {tp:.2f} EUR (+{tp_pct}%)")
        else:
            line = (f"*{ticker}* — {full_name} | score {score:.1f}\n"
                    f"  Quantita: *{qty} azioni* (~{cost_eur} EUR)\n"
                    f"  Entry: {entry:.2f} {cur} = {entry_eur} EUR\n"
                    f"  SL: {sl:.2f} {cur} = *{sl_eur} EUR* (-{sl_pct}%)\n"
                    f"  TP: {tp:.2f} {cur} = *{tp_eur} EUR* (+{tp_pct}%)\n"
                    f"  (cambio {cur}/EUR: {round(1/eurusd if cur=='USD' else 100/eurgbp, 4)})")

        signal_lines.append(line)

    signals_block = ""
    if signal_lines:
        signals_block = "*Segnali Bloomberg V2 — settimana corrente*\n\n"
        signals_block += "\n\n".join(signal_lines)
        signals_block += "\n\n---\n\n"

    header       = f"*Stock Market Bot — {today}*\n\n"
    full_message = header + signals_block
    print("Invio report su Telegram...")
    ok = send_telegram(full_message)
    if ok:
        print("Report inviato con successo.")
    else:
        # Non interrompere l'esecuzione: i segnali sono già salvati in signals.json
        # e il paper trading può essere aggiornato ugualmente.
        print("WARN: invio Telegram fallito. Segnali salvati in signals.json — continuo.")

    # 7. Paper trading
    print("Aggiornamento paper trading...")
    add_new_positions(signals, today_iso)


if __name__ == "__main__":
    run()
