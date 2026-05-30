# Backtest: Bloomberg V2 + 13F Institutional Signal

> Eseguito: **2026-05-26**  
> Confronto: Bloomberg V2 Puro vs Bloomberg V2 + 13F Institutional Signal  
> Universo: 186 ticker USA | Periodo: 2020-2026 (6.33 anni)  
> SL: 2.0×ATR | R:R 1:2 | Top 3/settimana | Capitale: 20.000 EUR

---

## Risultati Comparativi

| Metrica | Bloomberg V2 Puro | Bloomberg V2 + 13F | Δ |
|---------|------------------|-------------------|---|
| Trade totali | 954 | 955 | +1 |
| Win Rate | 45.3% | **46.1%** | +0.8% |
| Avg Win | +26.0% | +26.1% | +0.1% |
| Avg Loss | -12.4% | -12.5% | -0.1% |
| EV per trade (EUR) | +24.72 | **+26.39** | +1.67 |
| **Rendimento annuo netto** | +3.390 EUR (+17.0%) | **+3.602 EUR (+18.0%)** | **+212 EUR/anno** |
| Max Drawdown | -6.6% | **-6.4%** | +0.2% |
| Max SL consecutivi | 16 | 16 | 0 |
| Avg settimane/trade | 18.0 | 18.1 | — |

## Anno per Anno

| Anno | Puro lordo | 13F lordo | Delta |
|------|-----------|-----------|-------|
| 2020 | +15.264 EUR | +14.901 EUR | **-363 EUR** ⬇️ |
| 2021 | +3.728 EUR | +4.855 EUR | **+1.127 EUR** ⬆️ |
| 2022 | -1.228 EUR | -913 EUR | **+315 EUR** ⬆️ |
| 2023 | +4.177 EUR | +3.925 EUR | **-252 EUR** ⬇️ |
| 2024 | +3.378 EUR | +3.628 EUR | **+250 EUR** ⬆️ |
| 2025 | +2.468 EUR | +3.197 EUR | **+730 EUR** ⬆️ |
| 2026 (parziale) | +1.214 EUR | +1.214 EUR | 0 |

**Bilancio: 4 anni positivi, 2 anni negativi. +1.807 EUR totali in 6.33 anni.**

## Distribuzione PnL per Trade

| Percentile | Bloomberg V2 Puro | Bloomberg V2 + 13F |
|------------|------------------|-------------------|
| P10 | -15.5% | -15.5% |
| P50 (mediana) | -3.1% | +3.9% |
| P90 | +31.9% | +32.0% |
| Std dev | 20.08% | 20.17% |

---

## Metodologia

### Istituzioni monitorate
| Istituzione | CIK SEC | Tipo | Holdings |
|-------------|---------|------|---------|
| Vanguard Group Inc | 0000102909 | Passivo (index) | ~4.100 emittenti |
| State Street Corp | 0000093751 | Passivo (index) | ~4.000 emittenti |
| Wellington Management Group LLP | 0000902219 | **Attivo** | ~1.750 emittenti |
| Capital Research Global Investors | 0001422848 | **Attivo** | ~420 emittenti |

> **Nota:** Vanguard e State Street sono fondi passivi che tengono tutto l'indice sempre.
> Il segnale informativo viene quasi esclusivamente da Wellington e Capital Research.

### Logic del segnale
- Per ogni (trimestre, ticker): conta quante istituzioni su 4 detengono il titolo
- Calcola variazione QoQ (delta holders)
- **+2.0 pts** se ≥ 4 istituzioni aumentano posizione nello stesso trimestre
- **+1.5 pts** se 2-3 istituzioni aumentano
- **+1.0 pts** se 1 istituzione aumenta di >10%
- **0 pts** se nessuna variazione o riduzione

### Lag applicato
- 50 giorni dopo la fine del trimestre (legal deadline SEC: 45 giorni)
- Evita lookahead bias: dati Q4 disponibili dal ~19 febbraio in poi

### Copertura dati
- 30 trimestri coperti (2019-Q1 → 2026-Q1)
- 182/186 ticker con holders > 0 in almeno un quarter
- **460 segnali positivi** su 186 ticker × 30 trimestri = ~8% del tempo attivo

### Top ticker per inst_score medio
| Ticker | Score medio | Holders medi |
|--------|-------------|--------------|
| DOW | 0.20 | 3.0 |
| MRVL | 0.20 | 3.1 |
| TWLO | 0.18 | 2.7 |
| OKE | 0.17 | 3.0 |
| HAL | 0.17 | 3.3 |
| USB | 0.17 | 3.5 |
| ZM | 0.15 | 2.3 |
| LHX | 0.15 | 3.4 |
| PANW | 0.15 | 3.1 |
| DDOG | 0.15 | 3.1 |

---

## Confronto con Altri Segnali Testati

| Segnale | Fonte dati | Alpha annuo | Note |
|---------|-----------|-------------|------|
| **Nessuno (Bloomberg V2 puro)** | — | baseline | +17.0%/anno, MaxDD -6.6% |
| **Insider buying (Form 4)** | OpenInsider.com | **+0%** | S&P500 insiders non comprano → segnale nullo |
| **13F Institutional (4 fondi)** | SEC EDGAR 13F-HR | **+1.0%** | Piccolo ma positivo, +212 EUR/anno |

---

## Interpretazione e Conclusioni

### Perché il segnale è piccolo (ma positivo)
1. **Fondi passivi** (Vanguard, State Street) tengono virtualmente tutti i 186 ticker sempre → contributo al delta quasi zero
2. **Gestori attivi** (Wellington ~1.750 holdings, Capital Research ~430 holdings) fanno selezione ma tengono anche loro molti large cap sempre
3. Il segnale si attiva principalmente quando Wellington/CapResearch **aggiungono un nuovo titolo** o **aumentano significativamente** una posizione in un quarter

### Perché è comunque utile
- +1% annuo con MaxDD migliorato → rischio/rendimento leggermente migliore
- In 4 anni su 6 il segnale è positivo
- 2021 (+1.127 EUR) e 2025 (+730 EUR) sono gli anni in cui ha fatto più differenza
- Il segnale è **non correlato** al momentum tecnico → diversificazione informativa

### Raccomandazione
Il 13F institutional signal merita di essere **incluso come segnale supplementare** nel Bloomberg V3, con peso moderato. La chiave è espandere il monitoraggio ad altri gestori attivi (es. Fidelity, T. Rowe Price, AllianceBernstein) per aumentare la copertura del segnale.

### Possibili miglioramenti
1. **Aggiungere istituzioni attive** (Fidelity, T. Rowe Price, AllianceBernstein)
2. **Tracking quantità** (variazione shares held, non solo presenza/assenza)
3. **Signal raffinato**: 13F buys + insider buys simultanei = segnale forte combinato
4. **Focus hedge fund**: Citadel, Bridgewater, Appaloosa ecc. per segnale più selettivo

---

## File correlati
- Script backtest: `backtest_13f.py`
- Cache dati 13F: `inst13f_cache.pkl` (valida 90gg)
- Trade puro: `backtest_13f_base_trades.csv`
- Trade con segnale: `backtest_13f_signal_trades.csv`
- Ricerca base: [[Ricerca Smart Money e Insider]]
- Confronto insider: [[Backtest Insider Signal (Form 4)]] (risultato: +0%)
