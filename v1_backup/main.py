import sys
import json
import os
from datetime import datetime
from analyzer import build_market_snapshot, pre_filter_snapshot, get_top_signals
from claude_analyst import generate_report
from notifier import send_telegram
from config import PORTFOLIO_START, TRADE_SIZE_EUR, MAX_OPEN_TRADES

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "portfolio.json")


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


def add_new_positions(snapshot: dict, entry_date: str):
    portfolio = load_portfolio()
    open_tickers = {p["ticker"] for p in portfolio["open"]}
    slots = MAX_OPEN_TRADES - len(portfolio["open"])

    if slots <= 0:
        print(f"Paper trading: {MAX_OPEN_TRADES} posizioni già aperte, nessuna nuova aggiunta.")
        return

    signals = get_top_signals(snapshot, n=slots)
    added = 0
    for sig in signals:
        if sig["ticker"] in open_tickers:
            continue
        portfolio["open"].append({
            "id":         f"{sig['ticker']}_{entry_date}",
            "ticker":     sig["ticker"],
            "category":   sig["category"],
            "entry_date": entry_date,
            "entry_price": None,       # impostato dal tracker all'apertura del mercato
            "sl":          None,
            "tp":          None,
            "atr":         sig["atr"],
            "trade_eur":   TRADE_SIZE_EUR,
            "status":      "pending",
        })
        added += 1
        print(f"  + {sig['ticker']} (pending — entry al prezzo di apertura mercato)")

    save_portfolio(portfolio)
    print(f"Paper trading: {added} nuova/e posizione/i aperta/e (tot. aperte: {len(portfolio['open'])}).")


def run():
    today = datetime.now().strftime("%d/%m/%Y")
    today_iso = datetime.now().strftime("%Y-%m-%d")
    print(f"[{today}] Stock Market Bot avviato")

    print("Scaricamento dati di mercato...")
    snapshot = build_market_snapshot()

    usa_count = len(snapshot["USA"])
    eu_count = len(snapshot["EUROPE"])
    idx_count = len(snapshot["INDICES"])
    total = usa_count + eu_count + idx_count
    print(f"Dati raccolti: {idx_count} indici, {usa_count} titoli USA, {eu_count} titoli Europa ({total} totali)")

    if total == 0:
        print("Nessun dato disponibile. Uscita.")
        sys.exit(1)

    print("Pre-filtro tecnico in corso...")
    filtered = pre_filter_snapshot(snapshot)
    kept = sum(len(v) for v in filtered.values())
    print(f"Candidati selezionati dopo pre-filtro: {kept} su {total}")

    print("Analisi LLM in corso...")
    report = generate_report(filtered, today)

    header = f"*Stock Market Bot — {today}*\n\n"
    full_message = header + report

    print("Invio report su Telegram...")
    ok = send_telegram(full_message)

    if ok:
        print("Report inviato con successo.")
    else:
        print("Errore nell'invio Telegram.")
        sys.exit(1)

    print("Aggiornamento paper trading...")
    add_new_positions(snapshot, today_iso)


if __name__ == "__main__":
    run()
