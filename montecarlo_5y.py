"""
montecarlo_5y.py
----------------
Proiezione Monte Carlo a 5 anni per Bloomberg V2 — Config ottimale:
  SL = 2.0×ATR  |  R:R 1:2  |  Win rate storico 46.3%

Parametri ricavati dal backtest 2020-2026 (961 trade chiusi):
  WIN:  media +25.72%, std 9.43%
  LOSS: media -12.25%, std 3.66%
  TIMEOUT (5.6% dei trade): media +7.77%, std 10.41%
  152 trade/anno (3 segnali × ~50 settimane attive)

Costi modellati:
  - Trade Republic: 2 EUR round-trip (già inclusi nel pnl_pct storico)
  - Tasse: 26% sul profitto netto annuo positivo (fine anno)
  - Trade size: 500 EUR fisso

5.000 simulazioni × 5 anni (260 settimane, ~760 trade)
"""

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Parametri storici
# ---------------------------------------------------------------------------

CAPITAL_START  = 20_000
TRADE_SIZE     = 500
YEARS          = 5
TRADES_PER_YR  = 152        # media storica

WIN_RATE_MEAN  = 0.463      # 46.3% medio storico
WIN_RATE_STD   = 0.040      # incertezza sul win rate (~2 std entro 38-54%)

WIN_PCT_MEAN   = 25.72      # % guadagno medio per trade vincente (netto commissioni)
WIN_PCT_STD    =  9.43
LOSS_PCT_MEAN  = -12.25     # % perdita media per trade perdente (netto commissioni)
LOSS_PCT_STD   =  3.66
TO_PCT_MEAN    =  7.77      # % media per timeout
TO_PCT_STD     = 10.41
TO_RATE        =  0.056     # 5.6% dei trade sono timeout

TAX_RATE       = 0.26       # imposta italiana 26% su gain netto annuo
N_SIMS         = 5_000
RNG            = np.random.default_rng(42)

# ---------------------------------------------------------------------------
# Simulazione
# ---------------------------------------------------------------------------

def simulate_5years():
    """Simula 5 anni di trading. Restituisce array yearly capitals."""
    # Campiona win rate da distribuzione normale (incertezza strategia)
    wr = np.clip(RNG.normal(WIN_RATE_MEAN, WIN_RATE_STD), 0.25, 0.70)

    capital = CAPITAL_START
    yearly_caps = []
    annual_pnl_gross = 0  # accumulatore lordo per calcolo tasse

    for year in range(YEARS):
        annual_pnl_eur = 0

        for _ in range(TRADES_PER_YR):
            # Determina outcome del trade
            r = RNG.random()
            if r < TO_RATE:
                pnl_pct = RNG.normal(TO_PCT_MEAN, TO_PCT_STD)
            elif r < TO_RATE + wr:
                pnl_pct = max(5.0, RNG.normal(WIN_PCT_MEAN, WIN_PCT_STD))
            else:
                pnl_pct = min(-5.0, RNG.normal(LOSS_PCT_MEAN, LOSS_PCT_STD))

            pnl_eur = pnl_pct / 100 * TRADE_SIZE
            annual_pnl_eur += pnl_eur

        # Fine anno: applica tasse 26% sul profitto netto annuo (se positivo)
        if annual_pnl_eur > 0:
            tax = annual_pnl_eur * TAX_RATE
            annual_pnl_eur -= tax

        capital += annual_pnl_eur
        yearly_caps.append(capital)

    return yearly_caps


# ---------------------------------------------------------------------------
# Esegui simulazioni
# ---------------------------------------------------------------------------

print(f"Avvio {N_SIMS:,} simulazioni Monte Carlo — {YEARS} anni...")
print(f"Config: SL=2.0xATR R:R 1:2 | WR~{WIN_RATE_MEAN*100:.0f}% (±{WIN_RATE_STD*100:.0f}%) | {TRADES_PER_YR} trade/anno")
print(f"Capitale iniziale: {CAPITAL_START:,} EUR | Trade size: {TRADE_SIZE} EUR | Tasse: {TAX_RATE*100:.0f}%\n")

results = np.array([simulate_5years() for _ in range(N_SIMS)])
# results shape: (N_SIMS, YEARS)

final = results[:, -1]  # capitale finale anno 5

# ---------------------------------------------------------------------------
# Statistiche per anno
# ---------------------------------------------------------------------------

SEP = "=" * 78
print(SEP)
print(f"  PROIEZIONE MONTE CARLO — Bloomberg V2  SL=2.0xATR R:R 1:2")
print(f"  {N_SIMS:,} simulazioni | Capitale iniziale {CAPITAL_START:,} EUR | Trade size {TRADE_SIZE} EUR")
print(SEP)

print(f"\n  {'Anno':<6} {'P10':>9} {'P25':>9} {'MEDIANA':>9} {'P75':>9} {'P90':>9} {'MEDIA':>9} {'P(>0)':>8}")
print(f"  {'-'*68}")

for yr in range(YEARS):
    col = results[:, yr]
    p10  = np.percentile(col, 10)
    p25  = np.percentile(col, 25)
    med  = np.percentile(col, 50)
    p75  = np.percentile(col, 75)
    p90  = np.percentile(col, 90)
    mean = col.mean()
    prob = (col > CAPITAL_START).mean() * 100

    print(f"  Anno {yr+1:<2} {p10:>+9.0f} {p25:>+9.0f} {med:>+9.0f} {p75:>+9.0f} {p90:>+9.0f} {mean:>+9.0f} {prob:>7.1f}%")

print(f"  {'-'*68}")

# Riga rendimento % per anno 5
print(f"\n  Anno 5 — capitale finale ({N_SIMS:,} simulazioni):")
p10  = np.percentile(final, 10)
p25  = np.percentile(final, 25)
med  = np.percentile(final, 50)
p75  = np.percentile(final, 75)
p90  = np.percentile(final, 90)
mean = final.mean()

print(f"  Pessimista  (P10):  {p10:>8.0f} EUR  ({(p10-CAPITAL_START)/CAPITAL_START*100:+.1f}%  totale, {((p10/CAPITAL_START)**(1/YEARS)-1)*100:+.1f}%/anno)")
print(f"  Cauto       (P25):  {p25:>8.0f} EUR  ({(p25-CAPITAL_START)/CAPITAL_START*100:+.1f}%  totale, {((p25/CAPITAL_START)**(1/YEARS)-1)*100:+.1f}%/anno)")
print(f"  Mediana     (P50):  {med:>8.0f} EUR  ({(med-CAPITAL_START)/CAPITAL_START*100:+.1f}%  totale, {((med/CAPITAL_START)**(1/YEARS)-1)*100:+.1f}%/anno)")
print(f"  Ottimista   (P75):  {p75:>8.0f} EUR  ({(p75-CAPITAL_START)/CAPITAL_START*100:+.1f}%  totale, {((p75/CAPITAL_START)**(1/YEARS)-1)*100:+.1f}%/anno)")
print(f"  Molto ottim.(P90):  {p90:>8.0f} EUR  ({(p90-CAPITAL_START)/CAPITAL_START*100:+.1f}%  totale, {((p90/CAPITAL_START)**(1/YEARS)-1)*100:+.1f}%/anno)")
print(f"  Media attesa:       {mean:>8.0f} EUR  ({(mean-CAPITAL_START)/CAPITAL_START*100:+.1f}%  totale)")

prob_profit = (final > CAPITAL_START).mean() * 100
prob_2x     = (final > CAPITAL_START * 2).mean() * 100
prob_loss   = (final < CAPITAL_START).mean() * 100
prob_dd20   = (final < CAPITAL_START * 0.80).mean() * 100

print(f"\n  Probabilita' di chiudere in profitto dopo 5 anni: {prob_profit:.1f}%")
print(f"  Probabilita' di raddoppiare (>40.000 EUR):        {prob_2x:.1f}%")
print(f"  Probabilita' di perdere capitale:                 {prob_loss:.1f}%")
print(f"  Probabilita' di perdere >20% (sotto 16.000 EUR):  {prob_dd20:.1f}%")

# ---------------------------------------------------------------------------
# Distribuzione scenari anno per anno
# ---------------------------------------------------------------------------

print(f"\n{SEP}")
print(f"  DISTRIBUZIONE SCENARI — guadagno netto annuo atteso (netto tasse 26%)")
print(SEP)

hist_annual_net = [2346, 3308, 3423, -931, 2563]  # dati reali 2021-2025 (escludi 2020 outlier)
# Nota: 2020 fu +11.348 EUR (anno eccezionale COVID rally)
print(f"  Storico reale 2021-2025 (escl. 2020 outlier): {', '.join([f'{x:+.0f}EUR' for x in hist_annual_net])}")
print(f"  Media storica (escl. 2020): {sum(hist_annual_net)/len(hist_annual_net):+.0f} EUR/anno")

ann_gains = (results[:, 1:] - results[:, :-1])  # diff anno per anno
ann_gains = np.hstack([results[:, 0:1] - CAPITAL_START, ann_gains])

print(f"\n  {'Anno':<6} {'Anni neg.':>9} {'P10':>9} {'P25':>9} {'MEDIA':>9} {'P75':>9} {'P90':>9}")
print(f"  {'-'*62}")
for yr in range(YEARS):
    col = ann_gains[:, yr]
    neg_pct = (col < 0).mean() * 100
    print(f"  Anno {yr+1:<2} {neg_pct:>8.1f}% {np.percentile(col,10):>+9.0f} "
          f"{np.percentile(col,25):>+9.0f} {col.mean():>+9.0f} "
          f"{np.percentile(col,75):>+9.0f} {np.percentile(col,90):>+9.0f}")

# ---------------------------------------------------------------------------
# Worst case analysis
# ---------------------------------------------------------------------------

print(f"\n{SEP}")
print(f"  ANALISI WORST CASE")
print(SEP)

worst_final = np.sort(final)[:500]  # bottom 10%
print(f"  Bottom 10% scenari — capitale finale medio:  {worst_final.mean():>8.0f} EUR")
print(f"  Peggior scenario in assoluto (minimo):       {final.min():>8.0f} EUR")

# Anno peggiore simulato (max drawdown da picco in ciascuna simulazione)
max_dds = []
for sim in results:
    cap_path = np.concatenate([[CAPITAL_START], sim])
    peaks = np.maximum.accumulate(cap_path)
    dd = ((peaks - cap_path) / peaks).max()
    max_dds.append(dd)
max_dds = np.array(max_dds)

print(f"\n  Max drawdown intra-simulazione (da picco):")
print(f"  Mediano:   {np.percentile(max_dds,50)*100:.1f}%")
print(f"  P75:       {np.percentile(max_dds,75)*100:.1f}%")
print(f"  P90:       {np.percentile(max_dds,90)*100:.1f}%")
print(f"  P99:       {np.percentile(max_dds,99)*100:.1f}%")

# ---------------------------------------------------------------------------
# Confronto con alternativa passiva (BTP 3.5%, ETF 7%)
# ---------------------------------------------------------------------------

print(f"\n{SEP}")
print(f"  CONFRONTO CON INVESTIMENTI PASSIVI (stesso capitale {CAPITAL_START:,} EUR)")
print(SEP)

btp_5y   = CAPITAL_START * (1 + 0.035) ** YEARS
etf_5y   = CAPITAL_START * (1 + 0.07)  ** YEARS
etf_5y_t = CAPITAL_START + (etf_5y - CAPITAL_START) * (1 - 0.26)  # ETF con tasse 26%
bot_med  = med
bot_p25  = p25

print(f"  BTP / CD 3.5%/anno (netto ~2.6%):   {CAPITAL_START*(1+0.026)**YEARS:>9.0f} EUR  ({(CAPITAL_START*(1+0.026)**YEARS/CAPITAL_START-1)*100:+.1f}% totale)")
print(f"  ETF world 7%/anno (lordo):           {etf_5y:>9.0f} EUR  ({(etf_5y/CAPITAL_START-1)*100:+.1f}% totale)")
print(f"  ETF world 7%/anno (netto tasse 26%): {etf_5y_t:>9.0f} EUR  ({(etf_5y_t/CAPITAL_START-1)*100:+.1f}% totale)")
print(f"  ---")
print(f"  Bloomberg V2  P25 (cauto):           {bot_p25:>9.0f} EUR  ({(bot_p25/CAPITAL_START-1)*100:+.1f}% totale)")
print(f"  Bloomberg V2  mediana:               {bot_med:>9.0f} EUR  ({(bot_med/CAPITAL_START-1)*100:+.1f}% totale)")

print(SEP)
print(f"\n  Nota: la simulazione usa win rate storico 46.3% ± 4% (campionato per ogni run).")
print(f"  Anni reali negativi nella storia: 1/6 (solo 2022, -931 EUR netti).")
print(f"  2020 escluso dalle medie per eccezionalita' (COVID crash + rally = +11.348 EUR).")
print(SEP)

# Salva risultati
df_out = pd.DataFrame(results, columns=[f"anno_{i+1}" for i in range(YEARS)])
df_out.to_csv("montecarlo_5y_results.csv", index=False)
print(f"\nRisultati salvati in: montecarlo_5y_results.csv")
