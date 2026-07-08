# Serenity Signals — Design

**Data:** 2026-07-08
**Stato:** Approvato dall'utente (chat 2026-07-08)
**Obiettivo:** Strategia di paper trading basata sui segnali pubblici di Serenity (@aleabitoreddit), analista X specializzato in supply chain AI/semiconduttori (~900k follower, "bottleneck theory").

## Decisioni prese

| Domanda | Decisione |
|---|---|
| Tipo di bot | Paper trading autonomo (come v3), portafoglio simulato separato |
| Collocazione | Repo `corr1986/stock-market-bot`, file nuovi `serenity_*`, zero modifiche a v1/v3 |
| LLM | Groq `llama-3.3-70b-versatile` (gratuito, già in config); modello in costante di config per futuro switch a Claude Haiku |
| Fonte dati tweet | Repo GitHub `yan-labs/serenity-aleabitoreddit` — archivio JSON aggiornato automaticamente ogni ora (verificato 2026-07-08) |
| Gate | Backtest 12 mesi PRIMA di costruire il bot live; si procede solo se i numeri sono accettabili per l'utente |

## 1. Fonte dati

- File: `data/aleabitoreddit_tweets.json` dal repo `yan-labs/serenity-aleabitoreddit` (branch `main`). ~6.000 tweet da lug 2025, campi: `id`, `text`, `createdAtISO`, `metrics`, ecc.
- Download via `git clone --depth 1` o raw URL (attenzione al rate limiting su raw.githubusercontent: preferire clone).
- Stato in `serenity_state.json`: `last_tweet_id` processato + timestamp ultimo run.
- **Guardia dati stantii:** se il download fallisce o l'ultimo tweet dell'archivio è più vecchio di 48h → notifica Telegram `[SERENITY] ALERT` e run saltato. Nessun trade su dati vecchi.

## 2. Motore segnali (run giornaliero, pre-apertura USA)

1. Estrai menzioni `$TICKER` dai tweet nuovi (regex `\$[A-Z]{1,5}\b`).
2. Groq classifica per ticker: stance `bullish|bearish|neutral` + conviction 1–5, dato il testo dei tweet che lo menzionano.
3. **BUY** quando: stance bullish, conviction ≥ 4, e ticker "fresco" = mai menzionato prima nell'archivio oppure silente da ≥ 30 giorni. (Il pattern è "Serenity scopre un nome nuovo" — il suo edge documentato.)
4. Filtri riusati da v3: `earnings_filter.has_earnings_soon(ticker, 14)` → skip; regime VIX (>25 → nessuna entry, riuso `get_regime_config`); check esistenza/liquidità su yfinance.
5. **SELL anticipato:** stance bearish (conviction ≥ 4) su posizione aperta → chiusura al prossimo run.

## 3. Portafoglio (parametri identici a v3 per confrontabilità)

- Balance virtuale 20.000 EUR, rischio fisso 40 EUR/trade, size dinamica via `position_sizing.calculate_size()`.
- SL iniziale 2×ATR; exit Chandelier (`calculate_chandelier_stop`), no TP fisso.
- Max 3 posizioni. Stato in `portfolio_serenity.json`.
- Tracker orario `serenity_tracker.py` sul modello di `tracker_v3.py`.
- Notifiche Telegram con tag `[SERENITY]` via `notifier.send_telegram`.

## 4. Esecuzione

- Workflow GitHub Actions solo `workflow_dispatch` (pattern consolidato del repo, trigger esterno cron-job.org):
  - `serenity_daily.yml` — segnali, 1×/giorno pre-apertura USA
  - `serenity_tracker.yml` — monitoraggio orario, minuti sfasati rispetto agli altri job per evitare push simultanei
- Step di commit: `git push || (git pull --rebase origin main && git push)` come gli altri workflow.
- **2 nuovi job cron-job.org richiesti** — risorsa condivisa: si configurano solo dopo ok esplicito dell'utente (o istruzioni manuali).

## 5. Backtest preliminare (FASE 1 — gate)

- `backtest_serenity.py`: applica le regole §2 all'archivio storico completo + prezzi yfinance, simula entry/exit con parametri §3.
- Classificazione stance dei ~6.000 tweet storici via Groq in batch (gratuito), cache su disco (`serenity_stance_cache.json`) per non riclassificare.
- Output: WR%, rendimento totale/annualizzato, MaxDD, n. trade, confronto con v1/v3 sullo stesso periodo.
- **Decisione utente sui numeri prima di implementare la FASE 2 (bot live).**

## 6. Error handling

- Fetch archivio fallito / dati stantii → alert Telegram + exit senza modifiche allo stato.
- Groq API errore → retry (3 tentativi, backoff), poi skip run con alert. Mai segnali parziali.
- Risposta LLM non parsabile → il ticker viene scartato (log), non inventato.
- yfinance senza dati per un ticker → segnale scartato con log.

## 7. Testing

- TDD (pytest), test in `tests/`, nessuna chiamata reale a rete/Telegram/Groq (mock).
- Coperti: parsing menzioni, regola freshness, logica segnali con risposte LLM mockate, aggiornamento stato, error handling parsing.

## Rischi noti

- **Dipendenza da repo terzo** (yan-labs): mitigata dalla guardia 48h; se il repo muore, si valuta fork/alternativa.
- **Qualità classificazione Groq**: se il backtest delude, controllare a campione le classificazioni prima di scartare la strategia; eventuale upgrade a Claude Haiku (~$0,30/mese) cambiando la costante modello.
- **Survivorship/hindsight nel backtest**: ticker delistati o dati yfinance mancanti vengono scartati — il risultato è indicativo, non definitivo.
