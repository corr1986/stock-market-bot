# Stock Market Bot v3 — Design Spec
**Data:** 2026-05-30  
**Stato:** Approvato dall'utente

---

## Obiettivo

Costruire v3 come branch parallela a v1 (produzione) per paper trading separato. v3 introduce 5 miglioramenti strutturali con l'obiettivo di portare la performance da ~18%/anno verso ~21-23%/anno.

---

## Architettura

### File nuovi
| File | Ruolo |
|---|---|
| `main_v3.py` | Entry point lunedì mattina, orchestra selezione v3 |
| `tracker_v3.py` | Monitoring orario SL/Chandelier, aggiorna `portfolio_v3.json` |
| `earnings_filter.py` | Fetch earnings dates via yfinance, restituisce bool |
| `portfolio_v3.json` | Stato portafoglio v3 (separato da `portfolio.json`) |

### File riusati senza modifiche
`analyzer.py`, `macro_analyzer.py`, `news_fetcher.py`, `claude_analyst_v2.py`, `notifier.py`, `config.py`

### Isolamento
- v1 (`main.py`, `tracker.py`, `portfolio.json`) rimane intatta e in produzione
- v3 non legge né scrive su file v1
- Telegram: prefisso `[V3]` su tutti i messaggi v3

---

## Cambiamento 1 — Chandelier Exit (sostituisce TP fisso)

**Problema risolto:** il TP fisso lascia soldi sul tavolo sui trend forti. Mediana trade attuale: +3.9%.

**Logica:**
```python
chandelier_stop = max_high_since_entry - 2.0 × atr_entry
active_stop     = max(chandelier_stop, initial_sl)
# chiude posizione se H1_low <= active_stop
```

**Regole:**
- `atr_entry` è l'ATR weekly calcolato al momento dell'entry (fisso per tutta la vita del trade)
- `max_high_since_entry` si aggiorna ad ogni barra H1
- Il livello di stop non può mai scendere sotto `initial_sl` (entry - 2×ATR)
- Nessun TP fisso — il Chandelier è l'unica uscita in profitto

**Campi aggiuntivi in `portfolio_v3.json` per ogni posizione:**
```json
{
  "atr_entry": 3.25,
  "initial_sl": 145.50,
  "max_high_since_entry": 162.30,
  "chandelier_stop": 155.80
}
```

---

## Cambiamento 2 — Market Regime Filter

**Problema risolto:** il bot apre posizioni anche in bear market (2022: -1.228 EUR).

**Fonte:** `macro_analyzer.py` già esistente → `get_macro_context()["vix_value"]`

**Soglie:**
| VIX | Regime | Max posizioni aperte | Nuove entry |
|---|---|---|---|
| < 20 | Risk-On | 3 | Sì |
| 20–25 | Cautious | 2 | Sì |
| > 25 | Risk-Off | — | No |

**Comportamento Risk-Off:**
- Nessuna nuova posizione aperta
- Posizioni aperte gestite normalmente (Chandelier attivo)
- Telegram notifica: `[V3] ⚠️ Risk-Off (VIX=XX) — nessuna nuova entry questa settimana`

---

## Cambiamento 3 — Sizing Dinamico (rischio costante)

**Problema risolto:** con 500 EUR fissi, un titolo con ATR 4% rischia il doppio di uno con ATR 2%.

**Formula:**
```python
RISK_TARGET_EUR  = 40    # 0.2% del portfolio 20k
MAX_POSITION_EUR = 1500
SL_MULT          = 2.0   # coerente con Bloomberg V2

sl_pct = (SL_MULT × atr_entry) / entry_price
size   = min(RISK_TARGET_EUR / sl_pct, MAX_POSITION_EUR)
size   = max(size, 100)  # floor: mai sotto 100 EUR
```

**Esempi:**
| ATR weekly | SL% | Size |
|---|---|---|
| 1% | 2% | 1.500 EUR (cap) |
| 2.5% | 5% | 800 EUR |
| 4% | 8% | 500 EUR |

---

## Cambiamento 4 — Earnings Filter

**Problema risolto:** il bot può entrare il lunedì su un titolo con earnings il mercoledì.

**Implementazione:** `earnings_filter.py`

```python
def has_earnings_soon(ticker: str, days: int = 14) -> bool:
    """True se il ticker ha earnings nei prossimi `days` giorni."""
    # usa yf.Ticker(ticker).calendar
    # gestisce eccezioni e dati mancanti (default: False → non filtra)
```

**Integrazione in `main_v3.py`:**
```python
signals = get_top_signals(snapshot, n=10)  # prende top-10 invece di top-3
filtered = [s for s in signals if not has_earnings_soon(s["ticker"])]
final = filtered[:max_positions]  # prende i primi N dopo il filtro
```

**Fallback:** se `yfinance` non restituisce earnings date → il titolo non viene filtrato (non penalizzare per dati mancanti).

---

## Cambiamento 5 — Analyst Consensus nel Prompt LLM

**Problema risolto:** l'LLM in v2 non sa se gli analisti sono bullish o bearish sul titolo.

**Fonte:** `yf.Ticker(ticker).info` → campi `recommendationKey`, `targetMeanPrice`

**Dati aggiuntivi per ogni candidato:**
```python
"analyst": {
    "recommendation": "buy",    # strong_buy / buy / hold / sell / strong_sell
    "target_price": 185.0,
    "upside_pct": +12.3         # (target - price) / price * 100
}
```

**Utilizzo nel prompt:**
- L'LLM usa il consensus per rinforzare o scontare un segnale tecnico
- Non sostituisce la tecnica — è un input aggiuntivo
- Se dati non disponibili → campo omesso dal prompt, LLM ignora

---

## Flusso completo v3

```
LUNEDÌ MATTINA — main_v3.py
  1. get_macro_context() → VIX regime
  2. Se Risk-Off → notifica Telegram, exit
  3. build_market_snapshot() → 247 ticker
  4. get_top_signals(n=10) → top-10 Bloomberg V2 + 13F
  5. earnings_filter → rimuove ticker con earnings entro 14gg
  6. fetch analyst consensus via yfinance per i rimasti
  7. fetch news via news_fetcher per i rimasti
  8. claude_analyst_v2 → seleziona 0-N segnali (N = max_positions dal regime, passato nel prompt)
  9. apply dynamic sizing → calcola size per ogni segnale
 10. add_to_portfolio_v3() → aggiunge pending a portfolio_v3.json
 11. notifica Telegram [V3]

OGNI ORA — tracker_v3.py (9:00-22:00 lun-ven)
  1. activate_pending() → entry_price, atr_entry, initial_sl, chandelier_stop
  2. Per ogni posizione attiva:
     a. scarica H1 recenti via yfinance
     b. aggiorna max_high_since_entry
     c. ricalcola chandelier_stop
     d. Se H1_low <= active_stop → chiudi, notifica [V3]
  3. Aggiorna portfolio_v3.json
```

---

## Testing e confronto

- v3 gira in parallelo a v1 per **8-12 settimane** di paper trading
- Confronto metrico: WR%, Ann%, MaxDD, mediana trade
- Dopo validazione: decisione se sostituire v1 o continuare parallelo

---

## Non incluso in questo scope

- Backtest storico di v3 (opzionale, passo successivo)
- Integrazione con broker reale
- Modifiche a v1
