# Ricerca: Smart Money, Insider e Fondi Istituzionali

> Ricerca effettuata: **2026-05-26**  
> Obiettivo: integrare segnali di "smart money" nel Bloomberg V2 per migliorare la selezione delle 3 azioni settimanali

---

## TL;DR — Cosa possiamo fare concretamente

| Segnale | Impatto stimato | Costo | Difficoltà | Applicabile a |
|---------|----------------|-------|-----------|--------------|
| **Insider buying Form 4** | +4–8%/anno alpha | 🆓 Gratis | ⭐⭐ Media | USA (186 ticker) |
| **13F hedge fund holdings** | +2–4%/anno | 🆓 Gratis | ⭐⭐ Media | USA only |
| **Insider EU (MAR PDMR)** | +3–5%/anno | 💶 Parzialmente gratis | ⭐⭐⭐ Alta | EU (61 ticker) |
| **Dark pool / Options flow** | Variabile, alto rumore | 💰 $50–200/mese | ⭐⭐⭐⭐ Molto alta | USA mainly |
| **Cluster insider (3+ acquisti)** | Segnale più potente | 🆓 Gratis | ⭐⭐ Media | USA |

**Raccomandazione priorità:** Insider Form 4 (USA) → 13F holdings → Insider EU

---

## 1. Insider Buying — Form 4 SEC EDGAR (USA)

### Cos'è
Ogni CEO, CFO, direttore e manager con >10% delle azioni deve dichiarare ogni acquisto/vendita entro 2 giorni lavorativi tramite **SEC Form 4**. Sono dati pubblici, obbligatori, in tempo quasi reale.

### Perché funziona (evidenza accademica)
- Studio Lakonishok & Lee (2002): stocks con forte insider buying **+4.8%/anno** sopra il mercato nei 12 mesi successivi
- Studio Cohen, Malloy & Pomorski (2012): acquisti "opportunistici" (non routinari) → **+5.2% alpha a 6 mesi**
- **Cluster buying** (3+ insiders che comprano nello stesso periodo): segnale più forte di tutti
- Ricerca 2024: segnale positivo ma decrescente per azioni illiquide — funziona bene per i nostri large cap

### Cosa filtrare (qualità del segnale)
✅ **Segnale forte:**
- CEO, CFO, Presidente del CdA che ACQUISTA (non esercita opzioni)
- Importo > $50.000 in un singolo acquisto
- Cluster: 2+ insider che comprano entro 4 settimane
- Acquisto su mercato aperto (non piano di accumulo automatico)

❌ **Rumore da ignorare:**
- Esercizio di stock option (non è un acquisto discrezionale)
- Vendite di insider (spesso pianificate in anticipo, poco informative)
- Acquisti < $10.000 (routine, poco significativi)
- Director che comprano per la prima volta (possono essere obbligatori)

### Strumenti gratuiti

#### EdgarTools (🥇 Migliore per Python)
```python
pip install edgartools
```
```python
from edgar import Company

company = Company("NVDA")
filings = company.get_filings(form="4")
form4 = filings[0].obj()
print(form4.transactions)  # DataFrame con tutti gli acquisti/vendite
```
- Open source, nessuna API key, nessun rate limit
- Docs: https://edgartools.readthedocs.io/en/stable/guides/track-form4/

#### OpenInsider (sito web)
- Screener gratuito: http://www.openinsider.com/
- Filtra per cluster buying, importo, ruolo insider
- Non ha API ma è scrapabile

#### InsiderScreener (sito web)
- https://www.insiderscreener.com/en/l/sec-form-4
- Buon screener con filtri avanzati

### Come integrare nel Bloomberg V2
```python
# Aggiungere in bloomberg_enhanced_score():
insider_score = get_insider_score(ticker)  # da implementare
if insider_score >= 2:   bonus += 3.0   # cluster buying CEO/CFO
elif insider_score == 1: bonus += 1.5   # singolo insider senior
```

**Logica scoring:**
- +3.0 punti: cluster (2+ insiders, importo > $100k totale, ultimi 30gg)
- +1.5 punti: singolo acquisto CEO/CFO > $50k, ultimi 30gg
- +0.5 punti: director acquisto > $25k, ultimi 60gg
- 0: nessun segnale recente

---

## 2. Fondi Istituzionali — 13F Holdings (USA)

### Cos'è
Ogni fondo con >$100M in gestione deve dichiarare trimestralmente (entro 45 giorni dalla fine trimestre) tutte le posizioni long in azioni USA. Quindi: **dati trimestrali, con 45-135 giorni di ritardo**.

### Perché è utile (con i suoi limiti)
- Mostra l'accumulo strutturale da parte dei grandi fondi
- Quando molti fondi aumentano contemporaneamente una posizione → tendenza sostenuta
- **Limite critico:** i dati arrivano con 135 giorni di ritardo massimo (45gg fine quarter + 45gg filing + tempo di elaborazione)
- Utile come filtro di "qualità" del titolo, non come segnale di timing

### Cosa cercare
✅ **Segnale interessante:**
- Nuovo acquisto da parte di fund manager con track record (Berkshire, Ackman, Tepper)
- Aumento posizione >20% rispetto al trimestre precedente da parte di 3+ fondi
- Aumento del numero totale di fondi che detengono il titolo (breadth)

❌ **Ignorare:**
- Variazioni <5% (noise di ribilanciamento)
- ETF passivi (replicano indici, non danno segnale)

### Strumenti gratuiti

| Piattaforma | Cosa offre | URL |
|-------------|-----------|-----|
| **WhaleWisdom** | 13F tracking, hedge fund portfolios | https://whalewisdom.com/ |
| **TIKR.com** | Portfolio hedge fund gratuitamente | https://www.tikr.com |
| **HedgeFollow** | Segui portfolio di superinvestor | https://hedgefollow.com/ |
| **Dataroma** | Solo i migliori value investor (Buffett, Ackman) | https://www.dataroma.com |
| **13f.info** | Ricerca per ticker, vedi chi detiene cosa | https://13f.info/ |
| **SEC.gov raw data** | CSV ufficiali, dataset completo | https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets |

### API per integrazione Python
```python
# SEC EDGAR 13F via requests (gratis)
import requests
url = "https://data.sec.gov/submissions/CIK{cik}.json"
# oppure via edgartools:
from edgar import Company
company = Company("BRK-B")
filings_13f = company.get_filings(form="13F-HR")
```

### Limite per azioni EU
**I 13F coprono SOLO azioni quotate USA.** Per i titoli europei (ASML.AS, SAP.DE, etc.) non esiste un equivalente centralizzato.

---

## 3. Insider EU — MAR PDMR (Europa)

### Cos'è
In Europa vige il **Market Abuse Regulation (MAR)** dell'UE. I manager (PDMR = Persons Discharging Managerial Responsibilities) devono dichiarare le transazioni entro **3 giorni lavorativi**. La soglia minima è stata alzata da €5.000 a **€20.000 nel 2025**.

### Il problema: dati frammentati
I dati vengono dichiarati alle singole autorità nazionali:
- BaFin (Germania): https://www.bafin.de
- AFM (Olanda)
- AMF (Francia)
- CNMV (Spagna)
- FCA (UK)
- ESMA non centralizza ancora (previsto in futuro)

### Soluzione: InsiderScreener
**InsiderScreener** aggrega tutti i PDMR filing europei in un unico feed:
- URL: https://www.insiderscreener.com/en/l/insider-trading-europe
- Ha alert giornalieri e ranking performance
- Piano gratuito limitato, Pro ~€30/mese

### Alternativa: scraping diretto
Per i titoli .DE, .PA, .MC è possibile fare scraping delle disclosure nazionali. Complesso ma fattibile.

---

## 4. Dark Pool e Options Flow (USA)

### Cos'è
- **Dark pool:** transazioni OTC tra istituzionali non visibili in tempo reale sul mercato. ~40% del volume USA passa per dark pool.
- **Options flow:** acquisti inusuali di call/put che possono precedere movimenti importanti

### Strumenti (tutti a pagamento)

| Piattaforma | Prezzo | Punto di forza |
|-------------|--------|----------------|
| Unusual Whales | ~$50/mese | Dark pool + options, UI ottima |
| FlowAlgo | ~$100/mese | Real-time dark pool alerts |
| BlackBoxStocks | ~$100/mese | Options flow proprietario |
| Cheddar Flow | ~$80/mese | Sweep detection, momentum |

### Valutazione per il nostro uso
❌ **Non consigliato per ora.** Il segnale è rumoroso, richiede interpretazione in tempo reale, e i costi non si giustificano a questo stadio. Da rivalutare se vogliamo spostarci su timeframe intraday.

---

## 5. Come Combinare con Bloomberg V2

### Architettura proposta: "Bloomberg V3 con Smart Money Layer"

```
STEP 1: Pre-filtro tecnico (attuale)
  → score > 0 e MACD_hist > 0
  → Top 20 per score tecnico

STEP 2: Re-ranking Bloomberg Enhanced (attuale)
  → RSI 50-62: +1.5
  → Volume ratio ≥ 1.5: +2.0
  → Weekly change ≥ 2%: +1.5
  → Above SMA50: +1.0

STEP 3: Smart Money Bonus Layer (NUOVO)
  → Insider cluster buying (2+ insiders, 30gg): +3.0
  → Insider CEO/CFO singolo > $50k (30gg): +1.5
  → 13F: aumento posizione da 3+ hedge fund (trimestre): +1.5
  → 13F: nuovo acquisto da superinvestor noto: +2.0

STEP 4: Top 3 finali
```

### Impatto atteso
Combinare momentum tecnico + insider buying:
- Backtest TEJ 2019-2024: **+19.3%/anno, Sharpe 1.22**
- Vs solo tecnico (nostro attuale): +17-18%/anno
- Alpha aggiuntivo stimato: **+2-4% annuo**

---

## 6. Piano di Implementazione

### Fase 1 — Insider USA con EdgarTools (priorità alta, costo zero)
1. Installare `edgartools`
2. Scrivere `insider_signal.py`: scarica Form 4 degli ultimi 30 giorni per i 186 ticker USA
3. Calcola `insider_score` per ticker (cluster, ruolo, importo)
4. Integrare come bonus in `bloomberg_enhanced_score()`
5. Backtest comparativo: Bloomberg V2 vs Bloomberg V2 + Insider

### Fase 2 — 13F Holdings (priorità media, costo zero)
1. Download quarterly 13F dal SEC (CSV ufficiali)
2. Calcola "institutional momentum": aumento numero fondi e dimensione posizione
3. Aggiungere come bonus secondario al scoring
4. Backtest

### Fase 3 — Insider EU con InsiderScreener (priorità bassa)
1. Valutare costo piano Pro (~€30/mese)
2. Integrare API o scraping per .DE, .AS, .PA, .MC, .L
3. Backtest specifico titoli EU

---

## 7. Fonti e Link Utili

### Dati Insider USA
- [OpenInsider — screener gratuito Form 4](http://www.openinsider.com/)
- [EdgarTools — docs Form 4](https://edgartools.readthedocs.io/en/stable/guides/track-form4/)
- [SEC Form 4 Tracker — InsiderScreener](https://www.insiderscreener.com/en/l/sec-form-4)
- [GuruFocus Insider Summary](https://www.gurufocus.com/insider/summary)

### Dati 13F
- [WhaleWisdom — 13F gratuito](https://whalewisdom.com/)
- [HedgeFollow — portfolio superinvestor](https://hedgefollow.com/)
- [Dataroma — value investor tracker](https://www.dataroma.com)
- [SEC 13F raw datasets](https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets)
- [TIKR — hedge fund holdings](https://www.tikr.com/blog/7-best-free-websites-to-track-hedge-fund-portfolios)

### Insider Europa
- [InsiderScreener EU](https://www.insiderscreener.com/en/l/insider-trading-europe)
- [BaFin insider disclosures (Germania)](https://www.bafin.de/EN/Aufsicht/BoersenMaerkte/Emittentenleitfaden/Modul3/Kapitel1/kapitel1_node_en.html)

### Dark Pool / Options Flow
- [Unusual Whales](https://unusualwhales.com/)
- [FlowAlgo](https://flowalgo.com/)

### Ricerca Accademica
- [QuantPedia — Insider Trading Effect](https://quantpedia.com/strategy-tags/insider-trading-effect/)
- [Quiver Strategies — Insider Purchases backtest](https://www.quiverquant.com/strategies/s/Insider%20Purchases/)
- [Insider filings as trading signals — ScienceDirect 2024](https://www.sciencedirect.com/science/article/pii/S1544612324015435)
