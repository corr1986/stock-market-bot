"""
main_v3.py — Entry point settimanale v3.
Eseguire ogni lunedì mattina prima dell'apertura dei mercati.
"""

import json
import math
import os
from datetime import datetime
import yfinance as yf

from analyzer import build_market_snapshot, get_top_signals
from macro_analyzer import get_macro_context, format_macro_for_prompt
from claude_analyst_v2 import generate_signals
from earnings_filter import has_earnings_soon
from position_sizing import calculate_size, get_regime_config, SL_MULT
from tracker_v3 import load_portfolio, save_portfolio, PORTFOLIO_PATH
from notifier import send_telegram as send_telegram_message

V3_PREFIX = "[V3]"


def _fx(sym: str, fallback: float) -> float:
    try:
        h = yf.Ticker(sym).history(period="5d", interval="1d")
        return float(h["Close"].iloc[-1]) if not h.empty else fallback
    except Exception:
        return fallback


def init_portfolio_if_missing():
    if not os.path.exists(PORTFOLIO_PATH):
        data = {"balance": 20000.0, "realized_pnl": 0.0, "open": [], "closed": []}
        with open(PORTFOLIO_PATH, "w") as f:
            json.dump(data, f, indent=2)


def count_active(portfolio: dict) -> int:
    return sum(1 for p in portfolio["open"] if p["status"] in ("active", "pending"))


def run():
    init_portfolio_if_missing()
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. Regime VIX
    macro  = get_macro_context()
    vix    = macro.get("vix") or 20.0
    regime = get_regime_config(vix)

    if not regime["allow_entry"]:
        send_telegram_message(
            f"{V3_PREFIX} ⚠️ Risk-Off (VIX={vix:.1f})\nNessuna nuova entry questa settimana."
        )
        return

    # 2. Slot disponibili
    portfolio = load_portfolio()
    active    = count_active(portfolio)
    slots     = regime["max_positions"] - active
    if slots <= 0:
        send_telegram_message(f"{V3_PREFIX} Portfolio pieno ({active} pos). Nessuna nuova entry.")
        return

    # 3. Snapshot tecnico — top-10 Bloomberg V2 + 13F
    snapshot   = build_market_snapshot()
    candidates = get_top_signals(snapshot, n=10, sl_mult=SL_MULT, rr=2.0)

    # 4. Earnings pre-filter (rapido, senza costo API)
    candidates = [c for c in candidates if not has_earnings_soon(c["ticker"], days=14)]
    if not candidates:
        send_telegram_message(f"{V3_PREFIX} Nessun candidato dopo earnings filter.")
        return

    # 5. Filtra snapshot ai soli candidati
    candidate_set = {c["ticker"] for c in candidates}
    filtered_snap = {
        cat: {t: ind for t, ind in assets.items() if t in candidate_set}
        for cat, assets in snapshot.items()
    }

    # 6. LLM selezione — passa contesto macro all'analista
    macro_str = format_macro_for_prompt(macro)
    signals = generate_signals(snapshot=filtered_snap, date=today,
                               macro_context=macro_str, max_positions=slots)

    if not signals:
        send_telegram_message(
            f"{V3_PREFIX} Nessun setup BUY convincente. (VIX={vix:.1f}, {regime['regime']})"
        )
        return

    # 7. FX rates per conversione in EUR
    eurusd = _fx("EURUSD=X", 1.10)
    eurgbp = _fx("EURGBP=X", 0.86) * 100  # pence per LSE

    # 8. Sizing dinamico + aggiunta al portfolio
    cand_map  = {c["ticker"]: c for c in candidates}
    sig_map   = {s["ticker"]: s for s in signals if s.get("ticker")}
    added     = []
    for sig in signals[:slots]:
        ticker = sig.get("ticker", "")
        entry  = sig.get("entry_price", 0)
        cand   = cand_map.get(ticker)
        if not cand or not entry:
            continue

        atr  = cand["atr"]
        size = calculate_size(entry_price=entry, atr_entry=atr)
        sl   = round(entry - SL_MULT * atr, 4)

        position = {
            "ticker":               ticker,
            "category":             sig.get("category", cand.get("category", "")),
            "status":               "pending",
            "entry_price":          None,
            "entry_price_ref":      round(entry, 2),   # prezzo LLM, solo riferimento
            "size_eur":             round(size, 2),
            "atr_entry":            round(atr, 4),
            "initial_sl":           sl,
            "max_high_since_entry": 0.0,
            "chandelier_stop":      sl,
            "setup":                sig.get("setup", ""),
            "entry_date":           None,
            "close_date":           None,
            "close_price":          None,
            "pnl_pct":              None,
            "pnl_eur":              None,
        }
        portfolio["open"].append(position)
        added.append(position)

    save_portfolio(portfolio)

    # 9. Telegram report
    lines = [f"{V3_PREFIX} 📊 Segnali {today} — VIX={vix:.1f} ({regime['regime']})"]
    for p in added:
        ticker = p["ticker"]
        entry  = p["entry_price_ref"]
        sl     = p["initial_sl"]

        # Valuta e conversione EUR
        if any(ticker.endswith(sfx) for sfx in [".DE", ".AS", ".PA", ".MC", ".MI"]):
            cur, entry_eur = "EUR", entry
        elif ticker.endswith(".L"):
            cur, entry_eur = "GBp", round(entry / eurgbp, 2) if eurgbp else entry
        elif ticker.startswith("^"):
            continue
        else:
            cur, entry_eur = "USD", round(entry / eurusd, 2) if eurusd else entry

        sl_pct = round((entry - sl) / entry * 100, 1) if entry > 0 else 0
        qty    = math.ceil(p["size_eur"] / entry_eur) if entry_eur > 0 else "?"

        lines.append(
            f"\n*{ticker}* ({cur})\n"
            f"  Entry rif.: {entry:.2f} {cur} ≈ {entry_eur:.2f} EUR\n"
            f"  SL: {sl:.2f} {cur} (-{sl_pct}%) | Chandelier Exit (no TP fisso)\n"
            f"  Size: {p['size_eur']:.0f}€ → ~{qty} azioni\n"
            f"  Setup: {p['setup']}"
        )

    lines.append(f"\n⚠️ Entry e SL confermati all'apertura del mercato")
    lines.append(f"Posizioni: {active + len(added)}/{regime['max_positions']}")
    send_telegram_message("\n".join(lines))


if __name__ == "__main__":
    run()
