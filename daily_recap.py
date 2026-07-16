"""
daily_recap.py — Resoconto giornaliero dei 4 portafogli via Telegram.

Eseguito dal workflow v1_tracker alle 13:00 UTC (21:00 Manila, UTC+8).
Legge V1/V3/Serenity dai JSON locali del repo e Insider dal suo repo pubblico.
"""

import json
import os
from datetime import datetime

import requests

from notifier import send_telegram

BASE = os.path.dirname(os.path.abspath(__file__))
INSIDER_URL = (
    "https://raw.githubusercontent.com/corr1986/insider-tracker/main/"
    "portfolio_insider.json"
)


def _load(filename: str) -> dict:
    with open(os.path.join(BASE, filename), encoding="utf-8-sig") as f:
        return json.load(f)


def summarize_standard(d: dict) -> dict:
    """Riepilogo per portfolio con schema balance/unrealized_pnl/open/closed
    (V1, V3, Serenity)."""
    balance = d["balance"]
    unreal = d.get("unrealized_pnl") or 0.0
    return {
        "saldo": balance,
        "equity": round(balance + unreal, 2),
        "aperti": len(d.get("open", [])),
        "chiusi": len(d.get("closed", [])),
    }


def summarize_insider(d: dict) -> dict:
    """Riepilogo per il portfolio Insider (schema cash/positions/closed).
    equity = cash + capitale investito nelle posizioni aperte + P&L non realizzato."""
    positions = d.get("positions", [])
    equity = d["cash"] + sum(
        (p.get("invested") or 0.0) + (p.get("unrealized_pnl") or 0.0)
        for p in positions
    )
    return {
        "saldo": d["cash"],
        "equity": round(equity, 2),
        "aperti": len(positions),
        "chiusi": len(d.get("closed", [])),
    }


def _fmt(value: float) -> str:
    """Formatta un importo con separatore migliaia italiano: 20.151"""
    return f"{value:,.0f}".replace(",", ".")


def _line(name: str, s: dict, cur: str) -> str:
    return (
        f"*{name}*: saldo {_fmt(s['saldo'])}{cur} | equity {_fmt(s['equity'])}{cur}"
        f" | aperti {s['aperti']} | chiusi {s['chiusi']}"
    )


def build_message(v1: dict, v3: dict, insider: dict, serenity: dict) -> str:
    today = datetime.now().strftime("%d/%m/%Y")
    return "\n".join([
        f"📊 *Recap portafogli — {today}*",
        "",
        _line("V1", v1, "€"),
        _line("V3", v3, "€"),
        _line("Insider", insider, "$"),
        _line("Serenity", serenity, "€"),
    ])


def main():
    v1 = summarize_standard(_load("portfolio.json"))
    v3 = summarize_standard(_load("portfolio_v3.json"))
    serenity = summarize_standard(_load("portfolio_serenity.json"))

    resp = requests.get(INSIDER_URL, timeout=30)
    resp.raise_for_status()
    insider = summarize_insider(resp.json())

    msg = build_message(v1=v1, v3=v3, insider=insider, serenity=serenity)
    ok = send_telegram(msg)
    print("Recap inviato." if ok else "ERRORE invio recap.")


if __name__ == "__main__":
    main()
