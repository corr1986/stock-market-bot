# portfolio_updater.py
# Legge posizioni e ordini aperti da IBKR via IB Gateway (ib_insync)
# e aggiorna Portfolio Status.md nel vault Obsidian.
# Task Scheduler: ogni ora (o manualmente), python.exe portfolio_updater.py

# Fix compatibilita Python 3.10+ con ib_insync
import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import sys
from datetime import datetime, timezone, timedelta
from ib_insync import IB

BALI_TZ = timezone(timedelta(hours=8))  # UTC+8 — Bali/WITA

IBKR_HOST   = '127.0.0.1'
IBKR_PORT   = 4002   # IB Gateway paper
IBKR_CLIENT = 20     # clientId diverso da ibkr_executor (10)

INITIAL_BALANCE = 1_000_000.0  # EUR demo IBKR

OUTPUT_MD = r"C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot\Portfolio Status.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt_eur(val: float) -> str:
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:,.2f} EUR"


def fmt_price(val) -> str:
    if val is None:
        return "—"
    return f"{float(val):.3f}"


def get_sl_tp_for_symbol(open_orders: list, symbol: str) -> tuple:
    """
    Cerca tra gli ordini aperti il SL (stop) e TP (limit) per un dato simbolo.
    Restituisce (sl_price, tp_price) o (None, None).
    """
    sl = tp = None
    for trade in open_orders:
        if trade.contract.symbol != symbol:
            continue
        if trade.order.action != 'SELL':
            continue
        ot = trade.order.orderType
        if ot == 'STP':
            sl = trade.order.auxPrice
        elif ot == 'LMT':
            tp = trade.order.lmtPrice
    return sl, tp


# ---------------------------------------------------------------------------
# Aggiornamento portfolio
# ---------------------------------------------------------------------------

def _write_offline_status(reason: str):
    """Scrive un Portfolio Status.md minimo quando IBKR non è raggiungibile."""
    now_str = datetime.now(BALI_TZ).strftime("%d/%m/%Y %H:%M (Bali)")
    content = (
        "# Portfolio Status — [[Stock Market Bot]]\n"
        f"*Aggiornato: {now_str}  |  Fonte: IBKR Demo (DUQ074602)*\n\n"
        f"> ⚠️ IB Gateway non raggiungibile — {reason}\n"
        "> Assicurati che IB Gateway sia aperto e connesso a 127.0.0.1:4002\n"
    )
    import os
    os.makedirs(os.path.dirname(OUTPUT_MD), exist_ok=True)
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(content)


def update_portfolio():
    ib = IB()
    try:
        ib.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT)
    except Exception as e:
        msg = str(e)
        print(f"ERRORE: impossibile connettersi a IB Gateway: {msg}")
        print("Assicurati che IB Gateway sia aperto e connesso.")
        _write_offline_status(msg)
        return False

    try:
        now_bali = datetime.now(BALI_TZ)
        now_str  = now_bali.strftime("%d/%m/%Y %H:%M (Bali)")

        # --- Dati account ---
        account_vals = {v.tag: v.value for v in ib.accountValues()
                        if v.currency in ('EUR', 'BASE', '')}

        net_liquidation = float(account_vals.get('NetLiquidation', 0) or 0)
        cash_balance    = float(account_vals.get('CashBalance',    0) or 0)
        unrealized_pnl  = float(account_vals.get('UnrealizedPnL',  0) or 0)
        realized_pnl    = float(account_vals.get('RealizedPnL',    0) or 0)
        total_pnl       = net_liquidation - INITIAL_BALANCE

        # --- Posizioni aperte ---
        portfolio_items = ib.portfolio()   # include marketPrice e unrealizedPNL live
        open_orders     = ib.openOrders()

        # --- Storico trade (eseguiti oggi/recenti) ---
        trades_history = []
        try:
            execs = ib.executions()
            for ex in execs:
                if ex.execution.side == 'SLD':   # vendita = chiusura
                    trades_history.append(ex)
        except Exception:
            pass

        lines = []

        # Header
        lines.append("# Portfolio Status — [[Stock Market Bot]]")
        lines.append(f"*Aggiornato: {now_str}  |  Fonte: IBKR Demo (DUQ074602)*")
        lines.append("")

        # Riepilogo account
        lines.append("## Riepilogo")
        lines.append("| Voce | Valore |")
        lines.append("|---|---|")
        lines.append(f"| Capitale iniziale | {INITIAL_BALANCE:,.0f} EUR |")
        lines.append(f"| Net Liquidation | {net_liquidation:,.2f} EUR |")
        lines.append(f"| Cash balance | {cash_balance:,.2f} EUR |")
        lines.append(f"| P&L non realizzato | {fmt_eur(unrealized_pnl)} |")
        lines.append(f"| P&L realizzato | {fmt_eur(realized_pnl)} |")
        lines.append(f"| **P&L totale** | **{fmt_eur(total_pnl)}** |")
        lines.append(f"| Posizioni aperte | {len(portfolio_items)} |")
        lines.append("")

        # Posizioni aperte
        lines.append("## Posizioni aperte")
        if not portfolio_items:
            lines.append("*Nessuna posizione aperta.*")
        else:
            lines.append("| Simbolo | Qty | Entry | Prezzo | SL | TP | P&L | P&L% |")
            lines.append("|---|---|---|---|---|---|---|---|")
            for item in portfolio_items:
                sym     = item.contract.symbol
                qty     = item.position
                entry   = item.averageCost
                price   = item.marketPrice
                upnl    = item.unrealizedPNL
                upnl_pct = (price - entry) / entry * 100 if entry else 0
                sl, tp  = get_sl_tp_for_symbol(open_orders, sym)
                sign    = "+" if upnl >= 0 else ""
                lines.append(
                    f"| {sym} | {qty:.0f} | {fmt_price(entry)} | {fmt_price(price)} | "
                    f"{fmt_price(sl)} | {fmt_price(tp)} | "
                    f"{sign}{upnl:.2f} | {sign}{upnl_pct:.2f}% |"
                )
        lines.append("")

        # Ordini in attesa (non ancora eseguiti)
        pending = [t for t in open_orders
                   if t.order.action == 'BUY' and t.orderStatus.status
                   in ('Submitted', 'PreSubmitted')]
        if pending:
            lines.append("## Ordini in attesa di esecuzione")
            lines.append("| Simbolo | Tipo | Qty | Prezzo |")
            lines.append("|---|---|---|---|")
            for t in pending:
                ot = t.order.orderType
                px = t.order.lmtPrice if ot == 'LMT' else (t.order.auxPrice if ot == 'STP' else 'MKT')
                lines.append(f"| {t.contract.symbol} | {ot} | {t.order.totalQuantity} | {fmt_price(px)} |")
            lines.append("")

        # Storico esecuzioni recenti
        if trades_history:
            lines.append("## Esecuzioni recenti")
            lines.append("| Simbolo | Qty | Prezzo | Data |")
            lines.append("|---|---|---|---|")
            for ex in reversed(trades_history[-20:]):
                e   = ex.execution
                dt  = e.time.astimezone(BALI_TZ).strftime("%d/%m %H:%M") if e.time else "—"
                lines.append(f"| {ex.contract.symbol} | {e.shares:.0f} | {fmt_price(e.price)} | {dt} |")
            lines.append("")

        content = "\n".join(lines)

        import os
        os.makedirs(os.path.dirname(OUTPUT_MD), exist_ok=True)
        with open(OUTPUT_MD, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"OK Portfolio aggiornato: {len(portfolio_items)} posizioni, "
              f"equity={net_liquidation:,.2f} EUR, P&L={fmt_eur(total_pnl)}")
        return True

    finally:
        ib.disconnect()


if __name__ == "__main__":
    ok = update_portfolio()
    # Exit 0 anche se IBKR non è disponibile: Task Scheduler non deve
    # registrare un "errore" ricorrente quando IB Gateway è offline.
    # Il log e Portfolio Status.md mostrano già l'errore.
    sys.exit(0)
