SL_MULT          = 2.0
RISK_TARGET_EUR  = 100.0
MAX_POSITION_EUR = 1500.0
MIN_POSITION_EUR = 100.0


def calculate_size(
    entry_price: float,
    atr_entry: float,
    risk_target: float = RISK_TARGET_EUR,
    max_size: float = MAX_POSITION_EUR,
    sl_mult: float = SL_MULT,
) -> float:
    """Dimensione posizione in EUR a rischio costante (40 EUR default)."""
    sl_pct = (sl_mult * atr_entry) / entry_price
    if sl_pct <= 0:
        return MIN_POSITION_EUR
    size = risk_target / sl_pct
    return max(MIN_POSITION_EUR, min(size, max_size))


def calculate_chandelier_stop(
    max_high: float,
    atr_entry: float,
    initial_sl: float,
    sl_mult: float = SL_MULT,
) -> float:
    """Chandelier stop: max(trail, initial_sl). Non scende mai sotto initial_sl."""
    trail = max_high - sl_mult * atr_entry
    return max(trail, initial_sl)


def get_regime_config(vix: float) -> dict:
    """Restituisce configurazione operativa in base al VIX."""
    if vix < 20:
        return {"allow_entry": True,  "max_positions": 3, "regime": "risk-on"}
    elif vix <= 30:
        return {"allow_entry": True,  "max_positions": 2, "regime": "cautious"}
    else:
        return {"allow_entry": False, "max_positions": 0, "regime": "risk-off"}
