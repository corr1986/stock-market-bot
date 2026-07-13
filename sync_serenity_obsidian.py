"""Genera 'Portfolio Serenity Status.md' nel vault, nello stile di Portfolio V3 Status.

Legge portfolio_serenity.json. Lanciato dal tracker (o a mano dopo git pull).
"""
import json
import os
import subprocess
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(HERE, "portfolio_serenity.json")
OBSIDIAN_STATUS = os.path.join(HERE, "Portfolio Serenity Status.md")


def git_pull():
    try:
        r = subprocess.run(["git", "pull"], cwd=HERE,
                           capture_output=True, text=True, timeout=30)
        print(r.stdout.strip() or "git pull ok")
    except Exception as e:
        print(f"git pull fallito: {e}")


def load_portfolio():
    if not os.path.exists(PORTFOLIO_FILE):
        return {"balance": 50000.0, "realized_pnl": 0.0, "open": [], "closed": [],
                "unrealized_pnl": 0.0}
    with open(PORTFOLIO_FILE, encoding="utf-8") as f:
        return json.load(f)


def write_obsidian(pf):
    ts = datetime.utcnow().strftime("%d/%m/%Y %H:%M")
    active = [p for p in pf["open"] if p["status"] == "active"]
    pending = [p for p in pf["open"] if p["status"] == "pending"]
    closed = pf.get("closed", [])

    unrealized = round(sum(p.get("unrealized_eur") or 0 for p in active), 2)
    equity = pf["balance"] + unrealized
    wins = sum(1 for p in closed if (p.get("pnl_eur") or 0) > 0)
    losses = len(closed) - wins
    wr = (wins / len(closed) * 100) if closed else 0.0

    lines = [
        "# Portfolio Serenity — Stock Market Bot",
        f"*Aggiornato: {ts} UTC | Hold 60gg · SL 2×ATR · Segnali @aleabitoreddit*",
        "*[portfolio_serenity.json](portfolio_serenity.json)*",
        "",
        "## Riepilogo",
        "| Balance | Unrealized | Equity | Realizzato | Trade chiusi | Win Rate |",
        "|---|---|---|---|---|---|",
        f"| {pf['balance']:,.0f}€ | {unrealized:+,.0f}€ | {equity:,.0f}€ "
        f"| {pf.get('realized_pnl', 0):+,.0f}€ | {len(closed)} ({wins}W/{losses}L) | {wr:.0f}% |",
        "",
        "## Posizioni Aperte",
    ]

    if active:
        lines += [
            "| Ticker | Entry | Qty | Prezzo att. | P&L % | P&L € | SL | Scadenza |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for p in active:
            lines.append(
                f"| **{p['ticker']}** | {p['entry_price']} | {p['shares']} "
                f"| {p.get('current_price', '—')} | {p.get('unrealized_pct', 0):+.2f}% "
                f"| {p.get('unrealized_eur', 0):+.0f}€ | {p['initial_sl']:.2f} "
                f"| {p.get('deadline', '—')} |"
            )
    else:
        lines.append("*Nessuna posizione attiva.*")

    if pending:
        lines += ["", "## In attesa di apertura",
                  "| Ticker | Rif. | Qty | SL previsto | Segnale |",
                  "|---|---|---|---|---|"]
        for p in pending:
            lines.append(f"| {p['ticker']} | {p.get('entry_ref', '—')} | {p['shares']} "
                         f"| {p['initial_sl']:.2f} | {p.get('signal_date', '—')} |")

    lines += ["", "## Trade Chiusi"]
    if closed:
        lines += [
            "| Data uscita | Ticker | Entry | Uscita | P&L % | P&L € | Motivo |",
            "|---|---|---|---|---|---|---|",
        ]
        for p in reversed(closed):
            icon = "✅" if (p.get("pnl_eur") or 0) > 0 else "❌"
            lines.append(
                f"| {p.get('close_date', '—')} | {p['ticker']} | {p.get('entry_price', '—')} "
                f"| {p.get('close_price', '—')} | {p.get('pnl_pct', 0):+.2f}% "
                f"| {icon} {p.get('pnl_eur', 0):+.0f}€ | {p.get('close_reason', '—')} |"
            )
    else:
        lines.append("*Nessun trade ancora chiuso.*")

    lines += [
        "",
        "---",
        "*Modello hold-60 (backtest +62%/anno, MaxDD 4% su 50k) · segnali freschi conv≥4 · "
        "non è consulenza finanziaria*",
        "*[portfolio_serenity.json su GitHub]"
        "(https://github.com/corr1986/stock-market-bot/blob/main/portfolio_serenity.json)*",
    ]

    with open(OBSIDIAN_STATUS, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Portfolio Serenity Status.md aggiornato ({ts})")


if __name__ == "__main__":
    git_pull()
    write_obsidian(load_portfolio())
