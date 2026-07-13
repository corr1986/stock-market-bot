# Serenity Signals — Report Backtest FASE 1 (anno completo)

**Data:** 2026-07-13
**Dati:** 1.023 eventi freshness classificati al 100% (Groq llama-3.3-70b), periodo lug 2025 → lug 2026
**Segnali operativi:** 356 BUY (stance bullish, conviction ≥4) su 264 ticker con dati yfinance
**Parametri base:** capitale 20.000 EUR, size 500 EUR/trade, azioni intere (min 1)

---

## 1. Confronto 5 modelli di exit (posizioni illimitate, no filtro VIX)

| Modello | Trade | WR% | PnL | Rendimento | MaxDD |
|---|---|---|---|---|---|
| B1 — v1 (SL −2ATR / TP +4ATR, 2:1) | 291 | 48,1% | +6.959 | +34,8% | 4,46% |
| B2 — v3 (trailing Chandelier 2ATR) | 291 | 45,7% | +4.489 | +22,5% | 3,49% |
| E1 — TP parziale (½ a 2:1, resto trail) | 291 | 45,7% | +4.173 | +20,9% | 2,40% |
| E2 — solo conviction 5/5 (exit v1) | 81 | 42,0% | +1.189 | +5,9% | 2,63% |
| **E3 — hold 60gg / esci su bearish** | 291 | 40,2% | **+12.477** | **+62,4%** | 4,09% |

**Vincitore netto: E3 (hold).** Rendimento quasi doppio rispetto a v1, con drawdown simile. Conferma su dati completi la tesi emersa dal parziale: **la leva è la DURATA del trade, non lo stop.** Tenere la posizione fino a 60 giorni cattura gli strappi dei nomi di Serenity; uscire a +4×ATR (v1) o col trailing (v3) li tronca troppo presto.

**E2 conferma il paradosso**: filtrare per conviction alta PEGGIORA tutto (da 291 a 81 trade, +5,9%). Serenity ha ragione più spesso di quanto la sua "conviction dichiarata" indichi — prendere tutti i segnali ≥4 è meglio.

## 2. Ottimizzazione parametro hold (illimitate)

| Variante | Trade | WR% | PnL | Rendimento | MaxDD | Aperti a fine |
|---|---|---|---|---|---|---|
| deadline 45gg | 291 | 44,0% | +10.138 | +50,7% | 5,43% | 5 |
| **deadline 60gg** | 291 | 40,2% | +12.477 | **+62,4%** | **4,09%** | 5 |
| deadline 90gg | 291 | 37,8% | +12.759 | +63,8% | 7,48% | 13 |
| deadline 120gg | 291 | 34,4% | +14.066 | +70,3% | 9,17% | 42 |
| trailing 3ATR (no deadline) | 291 | 46,4% | +7.880 | +39,4% | 4,03% |
| trailing 4ATR (no deadline) | 291 | 44,3% | +9.757 | +48,8% | 4,65% |

**60 giorni è il punto ottimale.** Deadline più lunghe (90/120gg) alzano il rendimento ma con drawdown sproporzionato E molte posizioni ancora aperte a fine periodo (42 su 120gg = guadagni non realizzati, gonfiati e a rischio). 60gg dà il miglior rapporto rendimento/rischio (Ret/MaxDD = 15,2) con solo 5 aperte.

## 3. Analisi del vincitore (hold 60gg)

- **Stress test correzione primavera 2026**: max drawdown solo **3,84%, raggiunto il 01/04/2026** — il modello ha retto benissimo il ribasso.
- **Profilo perdite/vincite asimmetrico corretto**: top vincitori MXL +2.048, BKKT +1.065, ARM +519; peggiori perdite minuscole (−173, −161, −154) grazie allo stop −2×ATR. Textbook "cut losses short, let winners run".
- **⚠️ CAVEAT CAPITALE**: con posizioni illimitate su size 500, il capitale max impegnato tocca **26.622 EUR = 133% di 20k**. Su un conto da 20k **non è fattibile**: si sforerebbe il capitale e si salterebbero trade. Il +62% presuppone di poter tenere ~27k in posizioni simultanee.

## 4. Effetto del tetto posizioni (modello Chandelier, CON filtro VIX)

| Max posizioni | Trade | WR% | PnL | Rendimento | MaxDD |
|---|---|---|---|---|---|
| 3 | 55 | 52,7% | +596 | +2,98% | 1,09% |
| 5 | 92 | 46,7% | +743 | +3,71% | 1,93% |
| 10 | 147 | 48,3% | +2.115 | +10,58% | 1,75% |
| illimitate | 284 | 45,8% | +3.077 | +15,38% | 2,26% |

(Numeri più bassi del blocco 1 perché il backtest base applica il filtro VIX>30 che blocca entry; l'harness esperimenti no. Entrambi validi, ipotesi diverse.)

## 5. Conclusioni e raccomandazione

1. **Modello vincente: hold 60 giorni** (entry open giorno dopo, SL −2×ATR, no TP, esci a 60gg o su stance bearish). +62% annuo, drawdown 4%, resiliente alla correzione.
2. **Vincolo pratico**: il pieno potenziale richiede ~27k di capitale disponibile. Opzioni:
   - **Conto 50k** (già discusso): i 27k ci stanno comodi → +62% pieno realizzabile.
   - **Conto 20k con tetto ~10 posizioni**: ~+10-15% con drawdown 1,7-2,3% (versione conservativa fattibile).
3. **Prendere tutti i segnali conviction ≥4** (non filtrare a 5).
4. **Caveat metodologici**: survivorship (18-20 ticker senza dati yfinance esclusi); no slippage/commissioni; classificazione stance da LLM gratuito (Groq) — verificabile a campione; il periodo è un singolo anno fortemente rialzista per l'AI/semi supply chain, non garanzia di ripetibilità.

**GATE**: si procede alla FASE 2 (bot live) SOLO se l'utente approva questi numeri e sceglie capitale + tetto posizioni.
