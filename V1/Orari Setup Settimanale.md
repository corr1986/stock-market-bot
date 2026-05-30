# Orari Setup Settimanale — Stock Market Bot

> Fuso orario di riferimento: **Bali (WITA, UTC+8)**
> Ultimo aggiornamento: 2026-05-26 — confermato backtest S&P500 puro vs USA+EU combinato

---

## Schema Lunedì

| Orario Bali | Azione | PC | IB Gateway |
|-------------|--------|----|------------|
| 13:25 | PC deve essere già acceso | ✅ ON | ❌ non serve |
| 13:30 | `main.py` gira automaticamente (Task Scheduler) — scarica dati, calcola segnali Bloomberg V2, invia Telegram | ✅ ON | ❌ non serve |
| ~13:45 | main.py finito → Telegram ricevuto → PC può dormire/ibernare | 💤 ok | — |
| 16:05 | Riaccendi PC + apri IB Gateway | ✅ ON | ✅ APERTO |
| 16:10 | `place_orders_eu.py` gira — piazza ordini EU su IBKR (XETRA, AMS, PA, MC, MI) | ✅ ON | ✅ APERTO |
| ~16:30 | Ordini EU piazzati → puoi chiudere IB Gateway (SL/TP restano sul server IBKR) | 💤 ok | ✅ poi chiudi |
| 21:25 | Riapri IB Gateway (mercato US apre alle 21:30) | ✅ ON | ✅ APERTO |
| 21:35 | `place_orders_us.py` gira — piazza ordini US su IBKR (NYSE/NASDAQ) | ✅ ON | ✅ APERTO |
| ~22:00 | Ordini US piazzati → chiudi IB Gateway e tutto | 💤 ok | ✅ poi chiudi |

---

## Note importanti

- **main.py** usa yfinance (internet) per dati e tassi FX — IB Gateway NON è necessario
- **place_orders_eu/us.py** collegano a IB Gateway su porta 4002 — deve essere connesso e loggato
- Una volta piazzati SL e TP come ordini GTC su IBKR, il Gateway può essere chiuso: la gestione avviene lato server IBKR
- Se non ci sono segnali per la settimana, place_orders.py non fa nulla (nessun ordine = nessun problema)

## Orari mercati (riferimento)

| Mercato | Apertura locale | Apertura Bali |
|---------|-----------------|---------------|
| XETRA (DE) | 09:00 CET (estate CEST) | 15:00 Bali |
| XETRA (DE) | 09:00 CET (inverno) | 16:00 Bali |
| NYSE/NASDAQ (US) | 09:30 ET | 21:30 Bali (stabile tutto l'anno) |

> place_orders_eu è impostato alle **16:10 Bali** — sicuro sia in estate (CEST) che in inverno (CET)

---

## Strategia attiva

- **Bloomberg V2** — Top 3 segnali/settimana, SL = 2.0×ATR, R:R = 1:2
- Universo: **S&P500 Large Cap (247 ticker)** — solo USA, niente EU
- Capitale: 20.000 EUR | Trade size: 500 EUR | Max posizioni aperte: 3

### Perché solo S&P500 (backtest 2020–2026, SL=2.0 RR=2.0)

| Metrica | S&P500 247 | USA+EU Combinato |
|---------|-----------|-----------------|
| Win Rate | 46.3% | 46.5% |
| Ann. netto | **+3.626 EUR** | +3.427 EUR |
| Ann. % | **+18.1%** | +17.1% |
| Max Drawdown | **0.9%** | 2.9% |
| Max SL consec. | **13** | 18 |

> Aggiungere titoli EU non migliora il rendimento e triplica il drawdown. Universo invariato: S&P500 puro.
