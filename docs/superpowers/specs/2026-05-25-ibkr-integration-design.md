# IBKR Integration Design — Stock Market Bot
**Data:** 2026-05-25  
**Versione:** Bloomberg V2 RR4  
**Stato:** Approvato

---

## Obiettivo

Sostituire completamente l'integrazione cTrader (C# cBot + bridge JSON) con Interactive Brokers (IBKR) via TWS API. Il bot gira in Python puro, piazza bracket orders su TWS, gli ordini vengono gestiti dai server IBKR in autonomia dopo il piazzamento.

---

## Architettura

```
Task Scheduler (lunedì 13:30 Bali)
  └── main.py
        ├── build_market_snapshot()          # invariato
        ├── get_top_signals() Bloomberg V2 RR4  # invariato
        ├── ibkr_executor.place_orders()     # NUOVO
        ├── generate_report() + Telegram     # invariato
        └── add_new_positions() paper trading # invariato
```

### Flusso ordini IBKR

1. `main.py` chiama `ibkr_executor.place_orders(signals)` con i 3 segnali Bloomberg V2
2. `ibkr_executor` connette a TWS (`localhost:7497`, demo)
3. Per ogni segnale: risolve il contratto STK, calcola quantità, piazza bracket order
4. Bracket order inviato ai server IBKR (`outsideRth=False`)
5. `ibkr_executor` disconnette da TWS
6. TWS può essere chiuso — i server IBKR gestiscono esecuzione e SL/TP autonomamente
7. EU stocks: eseguono ~14:00 Bali | US stocks: eseguono ~21:30 Bali

---

## Componenti

### `ibkr_executor.py` (nuovo)

**Responsabilità:** connessione TWS, risoluzione contratti, calcolo volumi, piazzamento bracket orders, logging.

**Dipendenze:** `ib_insync`

**Interfaccia pubblica:**
```python
def place_orders(signals: list) -> list:
    """
    Piazza bracket orders su IBKR per ogni segnale Bloomberg V2.
    Restituisce lista di risultati con esito per ogni segnale.
    signals: output di get_top_signals() — lista di dict con
             ticker, entry_price, sl, tp, atr, score, bl_score, category
    """
```

**Logica interna:**
- Connette a TWS (port 7497, clientId=10 per non confliggere con altri bot)
- Per ogni segnale:
  - Risolve contratto `Stock(ticker, exchange, currency)` via `ib.qualifyContracts()`
  - Calcola quantità: `TRADE_SIZE_EUR / (sl_pct/100 * entry_price * fx_rate)`
  - Verifica che il ticker non abbia già una posizione aperta (evita duplicati)
  - Piazza bracket order: `ib.bracketOrder('BUY', qty, lmtPrice, takeProfitPrice, stopLossPrice)`
  - Invia i 3 ordini del bracket via `ib.placeOrder()`
  - Logga esito
- Disconnette da TWS
- Gestisce errori per simbolo (simbolo non trovato, mercato chiuso, etc.) senza bloccare gli altri

**Gestione errori:**
- Simbolo non trovato su IBKR → log WARN, salta e continua
- TWS non raggiungibile → log ERROR, esce senza crashare main.py
- Posizione già aperta per quel ticker → skip silenzioso

### Mapping simboli YF → IBKR

| Suffisso YF | Exchange IBKR | Currency |
|---|---|---|
| (nessuno — USA) | SMART | USD |
| `.DE` | XETRA | EUR |
| `.AS` | AEB | EUR |
| `.PA` | SBF | EUR |
| `.MC` | BM | EUR |
| `.L` | LSE | GBP |

Indici (`^GSPC`, `^NDX`, ecc.) → saltati (non tradabili come STK).

### `ibkr_portfolio_updater.py` (nuovo)

Sostituisce la lettura da `C:\TradeBridge\StockBot\portfolio_status.json` con query diretta a IBKR via `ib_insync`. Legge posizioni aperte e storico trade, aggiorna `Portfolio Status.md` in Obsidian con lo stesso formato attuale.

Task Scheduler `StockMarketBot_PortfolioUpdate` aggiornato per eseguire questo script.

### `main.py` (modifiche minime)

- Rimuove: `from ctrader_bot.stock_signal_generator import YF_TO_CT`
- Rimuove: funzione `write_ctrader_bridge()`
- Aggiunge: `from ibkr_executor import place_orders`
- Aggiunge: chiamata `place_orders(signals)` dopo `get_top_signals()`

### Eliminati

- `ctrader_bot/StockMarketBot.cs`
- `ctrader_bot/stock_signal_generator.py`
- `ctrader_bot/__init__.py`
- `C:\TradeBridge\StockBot\stock_signals.json` (bridge)
- Funzione `write_ctrader_bridge()` in `main.py`

---

## Parametri di rischio

| Parametro | Valore |
|---|---|
| Capital per trade | `TRADE_SIZE_EUR = 500 EUR` |
| SL | `1.5 × ATR settimanale` dal prezzo entry |
| TP | `4 × SL` (RR 4:1) |
| Order type | Market (entry) + Stop (SL) + Limit (TP) |
| Outside RTH | `False` — esegue solo in orario regolare |
| Max posizioni aperte | `MAX_OPEN_TRADES = 3` |

---

## Calcolo quantità

```
rischio_EUR  = TRADE_SIZE_EUR × (sl_pct / 100)
fx_rate      = tasso EUR/USD per azioni USA, 1.0 per EUR
               (EUR/GBP per azioni UK)
qty = rischio_EUR / (prezzo_entry × sl_pct/100) × fx_rate
qty = arrotondato al lotto minimo IBKR (generalmente 1 azione)
```

Per azioni UK in GBP: prezzo in pence su LSE → dividere per 100.

---

## Configurazione TWS richiesta

1. **API abilitata:** TWS → Edit → Global Configuration → API → Enable ActiveX and Socket Clients ✓
2. **Port:** 7497 (paper/demo), 7496 (live)
3. **Trusted IP:** 127.0.0.1
4. **Auto-confirm orders:** disabilitare "Precautionary Settings" per ordini automatici

---

## Task Scheduler (nessun cambio di orario)

| Task | Script | Orario |
|---|---|---|
| `StockMarketBot_Signal_Local` | `main.py` | Lunedì 13:30 Bali |
| `StockMarketBot_PortfolioUpdate` | `ibkr_portfolio_updater.py` | Periodico (invariato) |

---

## Dipendenze Python

```
ib_insync>=0.9.86
```

Aggiungere a `requirements.txt` / installare nel venv.

---

## Test pre-deploy

1. Connessione TWS demo funzionante (`ib.connect('127.0.0.1', 7497, clientId=10)`)
2. Risoluzione contratto per 1 ticker USA (es. AAPL) e 1 EU (es. ALV.DE)
3. Piazzamento bracket order in paper trading con quantità minima (1 azione)
4. Verifica che SL e TP compaiano su TWS
5. Verifica che chiudendo TWS gli ordini restino attivi su account demo IBKR
6. Run completo `main.py` in dry-run mode prima del deploy

---

## Out of scope

- Trailing stop (backtest separato già pianificato)
- VPS deployment (da valutare in futuro)
- Live trading (solo demo per ora)
