# montecarlo_combined.py
# Simulazione Monte Carlo — 3 bot combinati su 10.000 EUR
# Proiezione 5 anni con reinvestimento totale (nessun prelievo)

import numpy as np
import sys

# ── Parametri simulazione ─────────────────────────────────────────────────────
CAPITAL_TOTAL   = 10_000   # EUR totale
N_SIMULATIONS   = 10_000   # numero simulazioni
N_YEARS         = 5

# Allocazione capitale (come discusso)
ALLOC = {
    "GridMartingala": 0.50,   # 5.000 EUR — già calibrato su 5k
    "ForexBot1":      0.30,   # 3.000 EUR
    "StockBot":       0.20,   # 2.000 EUR
}

# ── Parametri annui per bot (media, std dev) ──────────────────────────────────
# GridMartingala: 2%/mese composto = 26.8%/anno, più stabile
# ForexBot1:      100% in 3 anni = ~26%/anno CAGR, più volatile
# StockBot:       14.8%/anno da backtest 2020-2025
#
# Std dev stimata da:
#   - GridMartingala: business stabile, DD max 10% → std ~9%
#   - ForexBot1: DD max 17%, alta volatilità → std ~18%
#   - StockBot: anno-per-anno da backtest (2020=+75%, 2021=+6%, 2022=-2%) → std ~20%
#     (ma in live il trade size scala col capitale → normalizzato a ~15% std)

BOTS = {
    "GridMartingala": {"mean": 0.268, "std": 0.090, "max_dd": 0.10},
    "ForexBot1":      {"mean": 0.260, "std": 0.180, "max_dd": 0.17},
    "StockBot":       {"mean": 0.148, "std": 0.150, "max_dd": 0.031},
}

# ── Correlazione tra bot ──────────────────────────────────────────────────────
# I due bot forex condividono esposizione macro → correlazione moderata ~0.35
# Stock bot poco correlato con forex → ~0.10
# Ordine: GridMartingala, ForexBot1, StockBot
CORR_MATRIX = np.array([
    [1.00, 0.35, 0.10],
    [0.35, 1.00, 0.10],
    [0.10, 0.10, 1.00],
])

# Cholesky decomposition per generare ritorni correlati
L = np.linalg.cholesky(CORR_MATRIX)


def simulate_portfolio():
    """
    Simula N_YEARS di rendimenti annui per il portafoglio combinato.
    Restituisce array [N_YEARS] con capitale alla fine di ogni anno.
    """
    capital = CAPITAL_TOTAL
    yearly_capitals = []

    for _ in range(N_YEARS):
        # Genera ritorni correlati per i 3 bot
        z = np.random.randn(3)
        corr_z = L @ z  # ritorni standardizzati correlati

        bots = list(BOTS.keys())
        returns = []
        for i, bot in enumerate(bots):
            r = BOTS[bot]["mean"] + BOTS[bot]["std"] * corr_z[i]
            returns.append(r)

        # Rendimento portafoglio = media pesata
        alloc = [ALLOC[b] for b in bots]
        portfolio_return = sum(a * r for a, r in zip(alloc, returns))

        # Applica rendimento al capitale (composto)
        capital = capital * (1 + portfolio_return)
        yearly_capitals.append(max(capital, 0))  # floor a 0

    return yearly_capitals


# ── Esegui simulazioni ────────────────────────────────────────────────────────
np.random.seed(42)
all_results = np.array([simulate_portfolio() for _ in range(N_SIMULATIONS)])
# all_results shape: (N_SIMULATIONS, N_YEARS)

# ── Calcola percentili per ogni anno ─────────────────────────────────────────
percentiles = [5, 25, 50, 75, 95]
pct_by_year = {}
for yr in range(N_YEARS):
    col = all_results[:, yr]
    pct_by_year[yr + 1] = {p: np.percentile(col, p) for p in percentiles}

# ── Rendimento medio atteso ───────────────────────────────────────────────────
bots_list = list(BOTS.keys())
alloc_list = [ALLOC[b] for b in bots_list]
mean_combined = sum(a * BOTS[b]["mean"] for a, b in zip(alloc_list, bots_list))
expected_5yr = CAPITAL_TOTAL * (1 + mean_combined) ** N_YEARS

# ── Probabilità di perdita ────────────────────────────────────────────────────
prob_loss_yr1   = (all_results[:, 0] < CAPITAL_TOTAL).mean() * 100
prob_loss_yr5   = (all_results[:, 4] < CAPITAL_TOTAL).mean() * 100
prob_double_yr5 = (all_results[:, 4] > CAPITAL_TOTAL * 2).mean() * 100
prob_triple_yr5 = (all_results[:, 4] > CAPITAL_TOTAL * 3).mean() * 100

# ── Output ────────────────────────────────────────────────────────────────────
sep = "=" * 72
print(f"\n{sep}")
print(f"  MONTE CARLO — 3 Bot combinati | 10.000 EUR | {N_SIMULATIONS:,} simulazioni")
print(f"  Allocazione: GridMartingala 50% | ForexBot1 30% | StockBot 20%")
print(f"  Rendimento medio atteso: {mean_combined*100:.1f}%/anno")
print(sep)

print(f"\n  {'Anno':<6} {'Pessimista':>14} {'25°pct':>12} {'MEDIANA':>12} {'75°pct':>12} {'Ottimista':>12}")
print(f"  {'':6} {'(5° pct)':>14} {'':>12} {'':>12} {'':>12} {'(95° pct)':>12}")
print("  " + "-" * 70)
for yr in range(1, N_YEARS + 1):
    p = pct_by_year[yr]
    print(f"  Anno {yr}  "
          f"{p[5]:>12,.0f}€  "
          f"{p[25]:>12,.0f}€  "
          f"{p[50]:>12,.0f}€  "
          f"{p[75]:>12,.0f}€  "
          f"{p[95]:>12,.0f}€")

print(sep)
print(f"\n  SCENARIO DETERMINISTICO (rendimenti medi esatti ogni anno):")
cap = CAPITAL_TOTAL
print(f"  {'Anno':<6} {'Capitale':>12}  {'Guadagno':>12}  {'Rendimento cumulato':>20}")
print("  " + "-" * 55)
for yr in range(1, N_YEARS + 1):
    cap_prev = CAPITAL_TOTAL * (1 + mean_combined) ** (yr - 1)
    cap_now  = CAPITAL_TOTAL * (1 + mean_combined) ** yr
    guadagno = cap_now - cap_prev
    cum_ret  = (cap_now / CAPITAL_TOTAL - 1) * 100
    print(f"  Anno {yr}  {cap_now:>12,.0f}€  {guadagno:>+12,.0f}€  {cum_ret:>18.1f}%")

print(sep)
print(f"\n  PROBABILITA' (su {N_SIMULATIONS:,} simulazioni):")
print(f"  Perdita dopo anno 1:         {prob_loss_yr1:.1f}%")
print(f"  Perdita dopo anno 5:         {prob_loss_yr5:.1f}%")
print(f"  Raddoppio (>20k) in 5 anni:  {prob_double_yr5:.1f}%")
print(f"  Triplicato (>30k) in 5 anni: {prob_triple_yr5:.1f}%")
print(sep)

print(f"\n  PARAMETRI BOT USATI:")
print(f"  {'Bot':<18} {'Mean/anno':>10} {'Std':>8} {'Max DD':>8} {'Alloc':>8}")
print("  " + "-" * 55)
for bot, p in BOTS.items():
    print(f"  {bot:<18} {p['mean']*100:>9.1f}%  {p['std']*100:>7.1f}%  "
          f"{p['max_dd']*100:>7.1f}%  {ALLOC[bot]*100:>7.0f}%")
print(f"\n  Correlazione forex-forex: 0.35 | forex-stock: 0.10")
print(sep)
print(f"\n  AVVERTENZA: stime basate su backtest — performance passata")
print(f"  non garantisce risultati futuri. Il GridMartingala ha rischio")
print(f"  coda non catturato dalla distribuzione normale (martingale).")
print(sep)
