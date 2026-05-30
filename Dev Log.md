# Dev Log — [[Stock Market Bot]]

> Progressi di sviluppo, modifiche al codice e decisioni architetturali.
> Aggiornato automaticamente da Claude Code al termine di ogni sessione.

---

## 2026-05-19

### Sessione di recupero contesto
- Recuperato stato completo del progetto da vault Obsidian e sessioni Claude Code precedenti
- Identificata architettura attuale: v1 in produzione (`daemon.py` + `tracker.py`), v2 in sviluppo (`main_v2.py` + contesto macro/news)
- Configurata memoria persistente per future sessioni Claude Code
- Configurato hook per aggiornamento automatico di questo Dev Log

### Stato portafoglio al 19/05/2026 ore 19:09
| Ticker | Entry | Prezzo | P&L |
|--------|-------|--------|-----|
| BP.L | 547.20 | 569.91 | +4.15% |
| ALV.DE | 378.00 | 384.00 | +1.59% |
| PM | pending | — | in attesa apertura USA |

### Note
- Il daemon è attivo (lock file presente, ultima esecuzione ore 19:08)
- `Portfolio Status.md` aggiornato automaticamente ogni ora
- v2 NON apre posizioni reali: confronto segnali solo per osservazione

---
- [2026-05-19 19:20] Modificato: tracker.py
- [2026-05-19 22:02] Modificato: tracker.py
- [2026-05-19 22:03] Modificato: tracker.py
- [2026-05-20 19:52] Modificato: check_prices.py
- [2026-05-21 11:52] Modificato: simulate_v3.py
- [2026-05-21 12:03] Modificato: simulate_v3.py
- [2026-05-21 12:04] Modificato: simulate_v3.py
- [2026-05-21 13:03] Modificato: simulate_v3.py
- [2026-05-21 13:49] Modificato: simulate_watchlist_compare.py
- [2026-05-21 14:07] Modificato: config.py
- [2026-05-21 14:23] Modificato: stock_signal_generator.py
- [2026-05-21 14:24] Modificato: StockMarketBot.cs
- [2026-05-21 15:00] Modificato: stock_signal_generator.py
- [2026-05-21 15:10] Modificato: StockMarketBot.cs
- [2026-05-21 15:15] Modificato: StockMarketBot.cs
- [2026-05-21 15:17] Modificato: StockMarketBot.cs
- [2026-05-21 15:17] Modificato: StockMarketBot.cs
- [2026-05-21 15:17] Modificato: StockMarketBot.cs
- [2026-05-21 15:17] Modificato: StockMarketBot.cs
- [2026-05-21 15:24] Modificato: StockMarketBot.cs
- [2026-05-21 15:30] Modificato: StockMarketBot.cs
- [2026-05-21 15:34] Modificato: stock_signal_generator.py
- [2026-05-21 15:39] Modificato: StockMarketBot.cs
- [2026-05-21 15:40] Modificato: StockMarketBot.cs
- [2026-05-21 15:47] Modificato: StockMarketBot.cs
- [2026-05-21 15:47] Modificato: StockMarketBot.cs
- [2026-05-21 15:47] Modificato: StockMarketBot.cs
- [2026-05-21 15:48] Modificato: StockMarketBot.cs
- [2026-05-21 16:20] Modificato: StockMarketBot.cs
- [2026-05-21 16:20] Modificato: StockMarketBot.cs
- [2026-05-21 16:21] Modificato: portfolio_updater.py
- [2026-05-21 16:21] Modificato: portfolio_updater.py
- [2026-05-21 16:23] Modificato: StockMarketBot.cs
- [2026-05-21 16:23] Modificato: StockMarketBot.cs
- [2026-05-21 16:27] Modificato: StockMarketBot.cs
- [2026-05-21 16:28] Modificato: StockMarketBot.cs
- [2026-05-21 16:28] Modificato: StockMarketBot.cs
- [2026-05-21 17:45] Modificato: simulate_minscore_compare.py
- [2026-05-21 18:14] Modificato: backtest_minscore_all.py
- [2026-05-21 21:47] Modificato: StockMarketBot.cs
- [2026-05-21 22:00] Modificato: StockMarketBot.cs
- [2026-05-22 07:08] Modificato: StockMarketBot.cs
- [2026-05-22 07:14] Modificato: StockMarketBot.cs
- [2026-05-22 11:45] Modificato: backtest_commodities.py
- [2026-05-22 13:47] Modificato: backtest_v2_adx_ema200.py
- [2026-05-22 14:23] Modificato: backtest_v2_adx_ema200.py
- [2026-05-22 17:10] Modificato: portfolio_updater.py
- [2026-05-22 17:11] Modificato: Stock Market Bot.md
- [2026-05-23 11:07] Modificato: montecarlo_combined.py
- [2026-05-23 12:45] Modificato: sec_insider_fetcher.py
- [2026-05-23 12:46] Modificato: backtest_v3_insider.py
- [2026-05-23 12:47] Modificato: sec_insider_fetcher.py
- [2026-05-23 14:48] Modificato: sec_insider_fetcher.py
- [2026-05-23 16:22] Modificato: portfolio_updater.py
- [2026-05-23 16:24] Modificato: portfolio_updater.py
- [2026-05-23 18:21] Modificato: sec_insider_fetcher.py
- [2026-05-24 09:49] Modificato: export_for_claude.py
- [2026-05-24 09:49] Modificato: bloomberg_screen.md
- [2026-05-24 09:53] Modificato: sec_insider_fetcher.py
- [2026-05-24 09:57] Modificato: sec_insider_fetcher.py
- [2026-05-24 10:03] Modificato: sec_insider_fetcher.py
- [2026-05-24 11:45] Modificato: simulate_bloomberg.py
- [2026-05-24 12:07] Modificato: simulate_bloomberg.py
- [2026-05-24 12:30] Modificato: simulate_bloomberg.py
- [2026-05-24 12:30] Modificato: simulate_bloomberg.py
- [2026-05-24 12:31] Modificato: simulate_bloomberg.py
- [2026-05-24 12:31] Modificato: simulate_bloomberg.py
- [2026-05-24 12:31] Modificato: simulate_bloomberg.py
- [2026-05-24 12:44] Modificato: simulate_bloomberg.py
- [2026-05-24 13:13] Modificato: simulate_bloomberg.py
- [2026-05-24 13:18] Modificato: simulate_bloomberg.py

---

## 2026-05-24 — Bloomberg Screen + Backtest Parametrico

### Cosa è stato fatto

#### 1. Bloomberg Screen (layer qualitativo)
Creato sistema a due livelli per il filtering delle azioni:
- **`export_for_claude.py`** — esporta i top-20 candidati tecnici in formato testo pronto da incollare in Claude.ai
- **`prompts/bloomberg_screen.md`** — system prompt per Claude.ai Project che simula un'analisi qualitativa Bloomberg (news, earnings, consensus analisti, macro settoriale)
- Workflow: bot genera top-20 tecnici → export → incolla in Claude.ai → Claude dà rating STRONG BUY / BUY / WATCH / SKIP → si eseguono solo i STRONG BUY

#### 2. Bloomberg V2 — Re-ranking qualitativo
Invece di un filtro hard (che riduce troppo il numero di trade), implementato un **re-ranking** nel backtest:
- Prende i top-20 tecnici
- Li ri-ordina per `bloomberg_enhanced_score()` (bonus per volume_ratio ≥ 1.5, RSI 50-62, weekly_change ≥ 2%, above_sma50)
- Seleziona sempre i top-3 — stesso volume trade di V1, selezione qualitativamente diversa

Funzione aggiunta in `simulate_bloomberg.py`:
```python
def bloomberg_enhanced_score(ind):
    base = score_stock(ind)
    bonus += 2.0  # vol >= 1.5
    bonus += 1.5  # RSI 50-62
    bonus += 1.5  # weekly_change >= 2%
    bonus += 1.0  # above_sma50
    bonus -= 2.0  # RSI > 65 (penalità ipercomprato)
    return base + bonus
```

#### 3. Sweep parametrico R:R 3:1 / 4:1 / 5:1
Riscritto `simulate_bloomberg.py` con loop su `RR_VALUES = [3, 4, 5]` per confronto diretto V1 vs Bloomberg V2 a parità di R:R.

### Risultati backtest 2020-2026 (253 ticker, 247 scaricati)

| R:R | V1 Profitto | BL V2 Profitto | Delta | V1 DD | BL DD | V1 CL | BL CL |
|-----|------------|----------------|-------|-------|-------|-------|-------|
| 3:1 | +28.805€ | +31.193€ | +2.388€ | 42.2% | 62.8% | 15 | 20 |
| 4:1 | +34.802€ | +36.762€ | +1.960€ | 44.7% | 61.9% | 18 | 20 |
| 5:1 | +38.947€ | +41.123€ | +2.176€ | 48.7% | 65.3% | 19 | 21 |

*Simulazione su capitale 5.000€, posizioni 500€, SL = 1.5× ATR weekly*

**Conclusioni:**
- Bloomberg V2 batte sempre V1 di ~2.000-2.400€ sul periodo, indipendentemente dal R:R
- Il R:R più alto aumenta il profitto assoluto ma NON riduce il drawdown (DD cresce leggermente)
- Bloomberg V2 ha sempre ~20 punti DD in più di V1 → causa: **correlation clustering** (i criteri momentum selezionano titoli pro-ciclici che perdono insieme)
- Aumentare il R:R non risolve il DD perché il problema è strutturale (correlazione), non il sizing

### Analisi drawdown reale per account size

Il DD del 63% è calcolato su 5.000€ simulati con posizioni da 500€ fissi.
Su un conto reale il DD assoluto è sempre ~3.100€ indipendentemente dalla size del conto:

| Conto | Posizione (1/40) | DD reale % | DD reale EUR | Profitto annuo | Rend. annuo |
|-------|-----------------|------------|--------------|----------------|-------------|
| 5.000€ | 125€ | 63% | ~3.150€ | ~1.230€ | ~24,6% |
| 10.000€ | 250€ | 31% | ~3.150€ | ~2.460€ | ~24,6% |
| 20.000€ | 500€ | 16% | ~3.150€ | ~4.928€ | ~24,6% |
| 100.000€ | 2.500€ | 3,1% | ~15.700€ | ~24.640€ | ~24,6% |

*Riferimento: Bloomberg V2, RR 3:1*

### Analisi account size con FP Markets cTrader

**Broker: FP Markets | Leva conto: 1:500 (forex) / ~1:20 (stock CFD)**

Vincoli pratici per trading stock CFD:
- **Minimo 1 share** (no fractional shares)
- **Commissioni USA: $2/lato minimo** ($4 round-trip)
- Leva 1:500 vale solo per forex — per stock CFD è cappata a ~1:20

| Conto | Posizione | Titoli accessibili | Commissione % | Verdict |
|-------|-----------|-------------------|---------------|---------|
| 5.000€ | 125€ | Solo titoli < $135 (~50% watchlist) | ~2,9% | ❌ Inefficiente |
| 10.000€ | 250€ | Titoli < $270 (~75% watchlist) | ~1,4% | ⚠️ Marginal |
| 20.000€ | 500€ | Titoli < $550 (~90% watchlist) | ~0,7% | ✅ Ottimale |
| 100.000€ | 2.500€ | Tutto (1:20 leva copre anche BKNG) | ~0,14% | ✅ Ottimale |

**Account ottimale per questa strategia con FP Markets: 20.000€**

### File salvati
- `simulate_bloomberg.py` — backtest completo V1 vs Bloomberg V2 con sweep RR
- `backtest_v1_rr{3,4,5}_results.csv` — trade V1 per ogni R:R
- `backtest_bloomberg_v2_rr{3,4,5}_results.csv` — trade Bloomberg V2 per ogni R:R
- `export_for_claude.py` — export top-20 per Claude.ai
- `prompts/bloomberg_screen.md` — system prompt Bloomberg Screen

### Prossimi passi suggeriti
- [ ] Validare Bloomberg Screen su dati live qualche settimana prima di integrare
- [ ] Rimuovere ticker delisted dalla watchlist (SPLK, SQ, DFS, MMC, ATVI, REL.AS)
- [ ] Decidere R:R definitivo per il bot (suggerito: 4:1 per miglior profitto/DD ratio)
- [ ] Eventuale integrazione Bloomberg Screen nel daemon (passa da Claude.ai a API Anthropic)
- [2026-05-24 15:20] Modificato: simulate_costs_rr4.py
- [2026-05-24 15:30] Modificato: claude_analyst_v3.py
- [2026-05-24 15:30] Modificato: config.py
- [2026-05-24 15:30] Modificato: main.py
- [2026-05-24 15:31] Modificato: .env
- [2026-05-24 15:33] Modificato: main.py
- [2026-05-24 15:36] Modificato: analyzer.py
- [2026-05-24 15:40] Modificato: analyzer.py
- [2026-05-24 15:41] Modificato: tracker.py
- [2026-05-24 15:44] Modificato: stock_signal_generator.py
- [2026-05-24 15:44] Modificato: stock_signal_generator.py
- [2026-05-24 15:44] Modificato: stock_signal_generator.py
- [2026-05-24 15:44] Modificato: stock_signal_generator.py
- [2026-05-24 15:50] Modificato: __init__.py
- [2026-05-24 15:51] Modificato: main.py
- [2026-05-24 17:45] Modificato: 2026-05-25-ibkr-integration-design.md
- [2026-05-24 18:09] Modificato: ibkr_executor.py
- [2026-05-24 18:09] Modificato: main.py
- [2026-05-24 18:09] Modificato: main.py
- [2026-05-24 18:10] Modificato: ibkr_executor.py
- [2026-05-24 18:14] Modificato: ibkr_executor.py
- [2026-05-24 18:14] Modificato: ibkr_executor.py
- [2026-05-24 18:20] Modificato: config.py
- [2026-05-24 18:20] Modificato: portfolio_updater.py
- [2026-05-25 11:27] Modificato: main.py
- [2026-05-25 11:27] Modificato: main.py
- [2026-05-25 13:34] Modificato: ibkr_executor.py
- [2026-05-25 13:38] Modificato: main.py
- [2026-05-25 13:38] Modificato: main.py
- [2026-05-25 13:42] Modificato: ibkr_executor.py
- [2026-05-25 13:49] Modificato: ibkr_executor.py
- [2026-05-25 13:52] Modificato: ibkr_executor.py
- [2026-05-25 13:59] Modificato: main.py
- [2026-05-25 14:00] Modificato: main.py
- [2026-05-25 14:00] Modificato: place_orders.py
- [2026-05-25 14:00] Modificato: place_orders.py
- [2026-05-25 14:01] Modificato: ibkr_executor.py
- [2026-05-25 14:02] Modificato: signals.json
- [2026-05-25 14:12] Modificato: portfolio.json
- [2026-05-25 14:44] Modificato: config.py
- [2026-05-25 14:44] Modificato: main.py
- [2026-05-25 14:45] Modificato: main.py
- [2026-05-25 14:50] Modificato: config.py
- [2026-05-25 14:51] Modificato: config.py
- [2026-05-25 14:51] Modificato: ibkr_executor.py
- [2026-05-25 14:51] Modificato: main.py
- [2026-05-25 14:53] Modificato: ibkr_executor.py
- [2026-05-25 15:10] Modificato: config.py
- [2026-05-25 15:11] Modificato: main.py
- [2026-05-25 16:16] Modificato: sl_optimization.py
- [2026-05-25 17:49] Modificato: backtest_fixed_pct.py
- [2026-05-25 18:41] Modificato: backtest_trailing.py
- [2026-05-25 20:55] Modificato: montecarlo_5y.py
- [2026-05-25 21:38] Modificato: ibkr_executor.py
- [2026-05-25 21:59] Modificato: ibkr_executor.py
- [2026-05-25 22:05] Modificato: ibkr_diag.py
- [2026-05-25 22:06] Modificato: ibkr_executor.py
- [2026-05-25 22:06] Modificato: ibkr_executor.py
- [2026-05-25 22:06] Modificato: ibkr_executor.py
- [2026-05-25 22:07] Modificato: ibkr_executor.py
- [2026-05-25 22:15] Modificato: ibkr_executor.py
- [2026-05-25 22:17] Modificato: ibkr_executor.py
- [2026-05-25 22:23] Modificato: ibkr_executor.py
- [2026-05-25 22:39] Modificato: ibkr_executor.py
- [2026-05-25 22:49] Modificato: ibkr_executor.py
- [2026-05-25 22:49] Modificato: ibkr_executor.py
- [2026-05-25 22:51] Modificato: ibkr_executor.py
- [2026-05-26 06:23] Modificato: backtest_midcap.py
- [2026-05-26 06:41] Modificato: backtest_mixed.py
- [2026-05-26 06:51] Modificato: config.py
- [2026-05-26 06:52] Modificato: status_bot.py
- [2026-05-26 06:52] Modificato: notifier.py
- [2026-05-26 07:04] Modificato: _add_pending.py
- [2026-05-26 07:05] Modificato: tracker.py
- [2026-05-26 07:05] Modificato: portfolio_updater.py
- [2026-05-26 07:05] Modificato: portfolio_updater.py
- [2026-05-26 09:05] Modificato: backtest_eu_combined.py
- [2026-05-26 09:07] Modificato: main.py
- [2026-05-26 09:16] Modificato: Orari Setup Settimanale.md
- [2026-05-26 11:00] Modificato: Orari Setup Settimanale.md
- [2026-05-26 11:00] Modificato: Orari Setup Settimanale.md
- [2026-05-26 11:11] Modificato: config.py
- [2026-05-26 11:12] Modificato: config.py
- [2026-05-26 11:12] Modificato: config.py
- [2026-05-26 11:16] Modificato: analyze_universe.py
- [2026-05-26 11:18] Modificato: Analisi Universo 247 Ticker.md
- [2026-05-26 11:24] Modificato: Ricerca Smart Money e Insider.md
- [2026-05-26 11:40] Modificato: backtest_insider.py
- [2026-05-26 12:16] Modificato: backtest_13f.py
- [2026-05-26 12:20] Modificato: backtest_13f.py
- [2026-05-26 12:21] Modificato: backtest_13f.py
- [2026-05-26 12:22] Modificato: backtest_13f.py
- [2026-05-26 12:22] Modificato: backtest_13f.py
- [2026-05-26 12:28] Modificato: backtest_13f.py
- [2026-05-26 12:41] Modificato: backtest_13f.py
- [2026-05-26 12:43] Modificato: backtest_13f.py
- [2026-05-26 12:44] Modificato: backtest_13f.py
- [2026-05-26 12:46] Modificato: backtest_13f.py
- [2026-05-26 12:47] Modificato: backtest_13f.py
- [2026-05-26 12:52] Modificato: backtest_13f.py
- [2026-05-26 13:03] Modificato: backtest_13f.py
- [2026-05-26 13:37] Modificato: Backtest 13F Institutional Signal.md
- [2026-05-26 14:50] Modificato: backtest_13f.py
- [2026-05-26 14:51] Modificato: backtest_13f.py
- [2026-05-26 14:51] Modificato: backtest_13f.py
- [2026-05-26 15:01] Modificato: backtest_13f.py
- [2026-05-26 18:43] Modificato: backtest_13f.py
- [2026-05-26 18:43] Modificato: backtest_13f.py
- [2026-05-26 21:29] Modificato: ibkr_diag.py
- [2026-05-26 21:36] Modificato: ibkr_open_signals.py
- [2026-05-26 21:37] Modificato: ibkr_open_signals.py
- [2026-05-26 22:08] Modificato: ibkr_executor.py
- [2026-05-26 22:15] Modificato: ibkr_executor.py
- [2026-05-26 22:42] Modificato: backtest_13f.py
- [2026-05-26 22:42] Modificato: analyzer.py
- [2026-05-26 22:42] Modificato: rebuild_13f_cache.py
- [2026-05-26 22:46] Modificato: run_monday_signals.bat
- [2026-05-27 06:49] Modificato: launch_rebuild.ps1
- [2026-05-27 06:49] Modificato: launch_rebuild.ps1
- [2026-05-27 07:09] Modificato: config.py
- [2026-05-27 07:09] Modificato: main.py
- [2026-05-27 07:10] Modificato: main.py
- [2026-05-27 07:10] Modificato: portfolio.json
- [2026-05-30 17:25] Modificato: 2026-05-30-v3-design.md
- [2026-05-30 17:25] Modificato: 2026-05-30-v3-design.md
- [2026-05-30 17:32] Modificato: 2026-05-30-stock-bot-v3.md
- [2026-05-30 17:35] Modificato: test_earnings_filter.py
- [2026-05-30 17:38] Modificato: position_sizing.py
- [2026-05-30 17:40] Modificato: tracker_v3.py
- [2026-05-30 17:40] Modificato: main_v3.py
- [2026-05-30 17:42] Modificato: claude_analyst_v3.py
- [2026-05-30 17:42] Modificato: main_v3.py
- [2026-05-30 17:42] Modificato: __init__.py
- [2026-05-30 17:43] Modificato: test_position_sizing.py
- [2026-05-30 17:43] Modificato: test_tracker_v3.py
- [2026-05-30 17:43] Modificato: run_v3.bat
- [2026-05-30 17:43] Modificato: run_tracker_v3.bat
- [2026-05-30 17:44] Modificato: tracker_v3.py
- [2026-05-30 17:44] Modificato: main_v3.py
- [2026-05-30 17:44] Modificato: test_tracker_v3.py
- [2026-05-30 17:49] Modificato: backtest_v3.py
- [2026-05-30 17:50] Modificato: backtest_v3.py
- [2026-05-30 17:50] Modificato: backtest_v3.py
- [2026-05-30 18:07] Modificato: position_sizing.py
- [2026-05-30 18:07] Modificato: v3_weekly.yml
- [2026-05-30 18:09] Modificato: v3_weekly.yml
- [2026-05-30 18:09] Modificato: v3_tracker.yml
- [2026-05-30 18:10] Modificato: v3_weekly.yml
- [2026-05-30 18:10] Modificato: v3_tracker.yml
- [2026-05-30 18:11] Modificato: portfolio_v3.json
- [2026-05-30 18:11] Modificato: .gitignore
- [2026-05-30 18:12] Modificato: SETUP_GITHUB.md
- [2026-05-30 18:13] Modificato: .gitignore
- [2026-05-30 18:29] Modificato: claude_analyst_v2.py
- [2026-05-30 18:29] Modificato: main_v3.py
- [2026-05-30 18:29] Modificato: v3_weekly.yml
- [2026-05-30 18:33] Modificato: sync_v3_obsidian.py
- [2026-05-30 19:06] Modificato: v1_weekly.yml
- [2026-05-30 19:06] Modificato: v1_tracker.yml
- [2026-05-30 19:06] Modificato: sync_obsidian.py
- [2026-05-30 19:35] Modificato: run_sync_obsidian.bat
- [2026-05-31 04:54] Modificato: v1_tracker.yml
- [2026-05-31 04:55] Modificato: main_v3.py
- [2026-05-31 04:55] Modificato: position_sizing.py
- [2026-05-31 04:59] Modificato: position_sizing.py
- [2026-05-31 04:59] Modificato: test_position_sizing.py
- [2026-05-31 07:38] Modificato: Portfolio V1.md
- [2026-05-31 07:38] Modificato: Portfolio V3.md
- [2026-05-31 07:38] Modificato: Portfolio Insider.md
