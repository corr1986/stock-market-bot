"""
ibkr_diag.py
------------
Diagnostica connessione IBKR: controlla account, open orders, posizioni,
e piazza un ordine MKT test su AAPL (1 sola azione) per vedere se
il paper account risponde correttamente.

Esegui: python ibkr_diag.py
"""

import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from ib_insync import IB, Stock, MarketOrder

IBKR_HOST   = '127.0.0.1'
IBKR_PORT   = 4002
IBKR_CLIENT = 99   # clientId diverso per non confliggere

ib = IB()

# Accumula tutti gli errori IBKR
errors = []
def on_error(reqId, errorCode, errorString, contract):
    msg = f"  [ERR reqId={reqId} code={errorCode}] {errorString}"
    if contract:
        msg += f"  ({contract.symbol})"
    print(msg)
    errors.append((reqId, errorCode, errorString))

ib.errorEvent += on_error

print(f"Connessione a {IBKR_HOST}:{IBKR_PORT}  clientId={IBKR_CLIENT}...")
try:
    ib.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT)
    print("Connesso.\n")
except Exception as e:
    print(f"ERRORE connessione: {e}")
    exit(1)

# --- Account info ---
print("=== ACCOUNT ===")
accounts = ib.managedAccounts()
print(f"Accounts: {accounts}")

account_vals = ib.accountValues()
tags = ['NetLiquidation', 'TotalCashValue', 'BuyingPower', 'AvailableFunds',
        'MaintMarginReq', 'FullAvailableFunds']
for v in account_vals:
    if v.tag in tags and v.currency in ('USD', 'EUR', 'BASE'):
        print(f"  {v.tag:30s} {v.value:>15s}  {v.currency}")

# --- Open orders ---
print("\n=== OPEN ORDERS ===")
open_orders = ib.reqAllOpenOrders()
ib.sleep(1)
if open_orders:
    for o in open_orders:
        print(f"  orderId={o.orderId}  {o.action} {o.totalQuantity} {o.orderType}")
else:
    print("  Nessun ordine aperto")

# --- Posizioni ---
print("\n=== POSIZIONI ===")
positions = list(ib.positions())
if positions:
    for p in positions:
        print(f"  {p.contract.symbol:<12} qty={p.position}  avgCost={p.avgCost:.4f}")
else:
    print("  Nessuna posizione aperta")

# --- Qualifica AAPL ---
print("\n=== TEST ORDER: AAPL 1 share ===")
contract = Stock('AAPL', 'SMART', 'USD')
qualified = ib.qualifyContracts(contract)
if not qualified:
    print("  FAIL: AAPL non qualificato!")
else:
    print(f"  Qualificato: {qualified[0]}")
    order = MarketOrder('BUY', 1,
                        transmit=True,
                        outsideRth=False,
                        tif='DAY')
    trade = ib.placeOrder(qualified[0], order)
    print(f"  Ordine piazzato: orderId={trade.order.orderId}")

    # Attendi fill o errore (max 30s)
    for i in range(15):
        ib.sleep(2)
        st = trade.orderStatus.status
        print(f"  t+{(i+1)*2:2d}s  status={st}  filled={trade.orderStatus.filled}")
        if st in ('Filled', 'Cancelled', 'ApiCancelled', 'Inactive'):
            break

    if trade.orderStatus.status == 'Filled':
        print(f"  [OK] FILLED @ {trade.orderStatus.avgFillPrice}")
    else:
        print(f"  [FAIL] NON FILLED -- status finale: {trade.orderStatus.status}")

print("\n=== ERRORI RICEVUTI DA IBKR ===")
if errors:
    for e in errors:
        print(f"  reqId={e[0]}  code={e[1]}  msg={e[2]}")
else:
    print("  Nessun errore ricevuto")

ib.disconnect()
print("\nDiagnostica completata.")
