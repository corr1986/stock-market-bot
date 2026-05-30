"""
ibkr_executor.py
----------------
Piazza bracket orders su IBKR via ib_insync per i segnali Bloomberg V2.
Connette a IB Gateway paper trading (localhost:4002).

Bracket order: Market BUY (entry) + Limit SELL (TP) + Stop SELL (SL).
outsideRth=False -> esegue solo in orario di mercato regolare.
Dopo il piazzamento, TWS/Gateway puo essere chiuso: IBKR gestisce SL/TP in autonomia.
"""

# Fix compatibilita Python 3.10+ con ib_insync (asyncio event loop)
import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import yfinance as yf
from ib_insync import IB, Stock, LimitOrder, StopOrder

from config import TRADE_SIZE_EUR

# ---------------------------------------------------------------------------
# Configurazione connessione
# ---------------------------------------------------------------------------

IBKR_HOST   = '127.0.0.1'
IBKR_PORT   = 4002   # IB Gateway paper (4001=live, 7497=TWS paper)
IBKR_CLIENT = 55     # clientId fisso per non confliggere con altri bot

# ---------------------------------------------------------------------------
# Mapping suffisso YF -> (exchange IBKR, currency)
# ---------------------------------------------------------------------------

YF_TO_IBKR = {
    '.DE': ('IBIS', 'EUR'),   # XETRA elettronico su IBKR = IBIS
    '.AS': ('AEB',  'EUR'),
    '.PA': ('SBF',  'EUR'),
    '.MC': ('BM',   'EUR'),
    '.MI': ('BVME', 'EUR'),   # Borsa Italiana
    '.L':  ('LSE',  'GBP'),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_live_price(ticker: str, fallback: float) -> float:
    """
    Recupera il prezzo intraday corrente via yfinance (barre 1m di oggi).
    Necessario perche fast_info.last_price restituisce il close di venerdi.
    Fallback: usa il prezzo del segnale se yfinance non risponde.
    """
    try:
        hist = yf.Ticker(ticker).history(period='1d', interval='1m')
        if not hist.empty:
            price = float(hist['Close'].iloc[-1])
            if price > 0:
                return price
    except Exception:
        pass
    # Fallback: usa 5% sopra il segnale (copre la maggior parte dei movimenti intraday)
    print(f"  WARN: prezzo live non disponibile per {ticker}, uso signal+5%")
    return fallback * 1.05


def _resolve_contract(ib: IB, ticker: str):
    """
    Converte un ticker Yahoo Finance in contratto IBKR qualificato.
    Restituisce (contract, currency, is_pence) o (None, None, False) se fallisce.
    is_pence=True per azioni LSE: yfinance restituisce GBP, IBKR usa pence (GBX).
    """
    if ticker.startswith('^'):
        return None, None, False

    suffix = ''
    for sfx in YF_TO_IBKR:
        if ticker.endswith(sfx):
            suffix = sfx
            break

    if suffix:
        exchange, currency = YF_TO_IBKR[suffix]
        symbol = ticker[:-len(suffix)]
    else:
        exchange, currency = 'SMART', 'USD'
        symbol = ticker

    try:
        contract  = Stock(symbol, exchange, currency)
        qualified = ib.qualifyContracts(contract)
        if not qualified and exchange != 'SMART':
            # Fallback: prova SMART routing con la stessa currency
            contract  = Stock(symbol, 'SMART', currency)
            qualified = ib.qualifyContracts(contract)
        if not qualified:
            return None, currency, False
        return qualified[0], currency, (currency == 'GBP')
    except Exception as e:
        print(f"  WARN: errore qualifica contratto {ticker}: {e}")
        return None, None, False


def _get_fx_rate(currency: str) -> float:
    """
    Restituisce il tasso EUR -> valuta locale per il calcolo delle quantita.
      EUR -> EUR : 1.0
      EUR -> USD : tasso EURUSD=X (es. 1.10)
      EUR -> GBP : tasso EURGBP=X * 100 (converte in pence, es. 86.0)
    In caso di errore usa fallback conservativi.
    """
    if currency == 'EUR':
        return 1.0

    fx_map = {'USD': 'EURUSD=X', 'GBP': 'EURGBP=X'}
    fallbacks = {'USD': 1.10, 'GBP': 86.0}

    yf_sym = fx_map.get(currency)
    if not yf_sym:
        return 1.0

    try:
        tk = yf.Ticker(yf_sym)
        hist = tk.history(period='5d', interval='1d')
        rate = float(hist['Close'].iloc[-1])
        if currency == 'GBP':
            rate *= 100  # converti in pence per coerenza con prezzi LSE
        return rate
    except Exception:
        fb = fallbacks.get(currency, 1.0)
        print(f"  WARN: fx rate {currency} non disponibile, uso fallback {fb}")
        return fb


# ---------------------------------------------------------------------------
# Funzione pubblica
# ---------------------------------------------------------------------------

def place_orders(signals: list) -> list:
    """
    Piazza bracket orders su IBKR per ogni segnale Bloomberg V2.

    Parametri:
        signals: output di get_top_signals() - lista di dict con
                 ticker, entry_price, sl, tp, atr, score, bl_score, category

    Restituisce:
        lista di dict con { ticker, status, qty/msg }
        status: "OK" | "SKIP" | "ERROR"
    """
    if not signals:
        print("IBKR: nessun segnale da piazzare.")
        return []

    ib = IB()
    results = []

    # --- Connessione ---
    try:
        ib.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT)
        print(f"IBKR: connesso a {IBKR_HOST}:{IBKR_PORT} (clientId={IBKR_CLIENT})")
        # Abilita dati ritardati gratuiti (tipo 3) per paper account senza subscription live
        # Senza questo, il simulatore paper non riceve dati e gli ordini restano PendingSubmit
        ib.reqMarketDataType(3)
    except Exception as e:
        print(f"IBKR ERROR: impossibile connettersi a IB Gateway ({IBKR_HOST}:{IBKR_PORT}): {e}")
        print("  -> Assicurati che IB Gateway sia aperto e connesso.")
        return [{"ticker": s["ticker"], "status": "ERROR", "msg": str(e)} for s in signals]

    try:
        # Posizioni gia aperte -> evita duplicati
        open_symbols = set()
        try:
            open_symbols = {p.contract.symbol for p in ib.positions()}
        except Exception:
            pass

        for sig in signals:
            ticker = sig["ticker"]
            entry  = sig["entry_price"]
            sl     = sig["sl"]
            tp     = sig["tp"]

            # Indici non tradabili
            if ticker.startswith('^'):
                print(f"  SKIP {ticker}: indice non tradabile")
                results.append({"ticker": ticker, "status": "SKIP", "msg": "indice"})
                continue

            # Risoluzione contratto
            contract, currency, is_pence = _resolve_contract(ib, ticker)
            if contract is None:
                print(f"  WARN {ticker}: contratto non trovato su IBKR - saltato")
                results.append({"ticker": ticker, "status": "SKIP", "msg": "contratto non trovato"})
                continue

            # Posizione gia aperta
            if contract.symbol in open_symbols:
                print(f"  SKIP {ticker}: posizione gia aperta ({contract.symbol})")
                results.append({"ticker": ticker, "status": "SKIP", "msg": "posizione gia aperta"})
                continue

            # Prezzi in valuta locale
            # yfinance LSE restituisce GBP, IBKR vuole pence (GBX) -> *100
            mult = 100.0 if is_pence else 1.0
            entry_l = round(entry * mult, 4)
            sl_l    = round(sl    * mult, 4)
            tp_l    = round(tp    * mult, 4)

            # Calcolo quantita: acquista ~TRADE_SIZE_EUR di azioni
            fx = _get_fx_rate(currency)
            qty = max(1, int(TRADE_SIZE_EUR * fx / entry_l))

            # Prezzo limite di entry: prezzo live IBKR +2% per garantire fill immediato.
            # IBKR paper rifiuta Market orders (err 202); usiamo LimitOrder sopra mercato.
            # +2% copre spread ask + piccolo buffer intraday.
            current_px  = _get_live_price(ticker, entry_l)
            limit_entry = round(current_px * 1.02, 4)

            print(f"  {ticker:<10} signal={entry_l:.4f}  live={current_px:.4f}  "
                  f"lmt_entry={limit_entry:.4f}  sl={sl_l:.4f}  tp={tp_l:.4f}  "
                  f"qty={qty}  fx={fx:.4f}  currency={currency}")

            # --- TWO-STEP ORDER: Limit BUY entry (standalone) → attendi fill → SL + TP GTC ---
            # Approccio due fasi per evitare il bug parentId (Error 135) sui bracket:
            # 1. Piazza solo il BUY Limit, transmit=True immediato
            # 2. Aspetta fill, poi piazza SL e TP come ordini GTC standalone

            entry_order = LimitOrder('BUY', qty, limit_entry,
                                     transmit=True,
                                     outsideRth=False,
                                     tif='DAY')

            try:
                trade_entry = ib.placeOrder(contract, entry_order)
                print(f"  Attendo fill entry {ticker} (max 20 min)...")

                filled = False
                for _ in range(600):   # 600 × 2s = 1200s = 20 min max
                    ib.sleep(2)
                    status_now = trade_entry.orderStatus.status
                    if status_now == 'Filled':
                        filled = True
                        break
                    if status_now in ('ApiCancelled', 'Cancelled', 'Inactive'):
                        print(f"  WARN {ticker}: entry cancellata (status={status_now})")
                        break

                if filled:
                    avg_px = trade_entry.orderStatus.avgFillPrice
                    print(f"  Entry FILLED @ {avg_px:.4f}  qty={qty} — piazzo SL e TP...")
                    # SL e TP come GTC standalone (no parentId, persistono dopo disconnect)
                    sl_order = StopOrder('SELL', qty, sl_l,
                                         transmit=True, outsideRth=False, tif='GTC')
                    tp_order = LimitOrder('SELL', qty, tp_l,
                                          transmit=True, outsideRth=False, tif='GTC')
                    ib.placeOrder(contract, sl_order)
                    ib.placeOrder(contract, tp_order)
                    ib.sleep(2)
                    print(f"  OK {ticker}: IN POSIZIONE  fill={avg_px:.4f}  "
                          f"SL={sl_l:.4f}  TP={tp_l:.4f}  qty={qty}")
                    results.append({"ticker": ticker, "status": "OK", "qty": qty})
                else:
                    final_st = trade_entry.orderStatus.status
                    print(f"  WARN {ticker}: entry non filled dopo timeout "
                          f"(status={final_st})")
                    results.append({"ticker": ticker, "status": "WARN",
                                    "msg": f"entry status={final_st}"})
            except Exception as e:
                print(f"  ERROR {ticker}: {e}")
                results.append({"ticker": ticker, "status": "ERROR", "msg": str(e)})

    finally:
        ib.disconnect()
        print("IBKR: disconnesso")

    return results
