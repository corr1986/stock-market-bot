import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from position_sizing import calculate_size, calculate_chandelier_stop, get_regime_config


def test_size_average_atr():
    # entry=100, atr=2.5 → sl_pct=5% → size=40/0.05=800
    assert calculate_size(100.0, 2.5) == 800.0


def test_size_low_atr_capped():
    # sl_pct=1% → size=4000 → cappato a 1500
    assert calculate_size(100.0, 0.5) == 1500.0


def test_size_high_atr_floored():
    # sl_pct=50% → size=80 → floor a 100
    assert calculate_size(100.0, 25.0) == 100.0


def test_chandelier_above_initial_sl():
    assert calculate_chandelier_stop(110.0, 2.5, 95.0) == 105.0


def test_chandelier_equal_initial_sl():
    assert calculate_chandelier_stop(100.0, 2.5, 95.0) == 95.0


def test_chandelier_never_below_initial_sl():
    assert calculate_chandelier_stop(96.0, 2.5, 95.0) == 95.0


def test_regime_risk_on():
    cfg = get_regime_config(15.0)
    assert cfg["allow_entry"] is True
    assert cfg["max_positions"] == 3


def test_regime_cautious():
    cfg = get_regime_config(22.5)
    assert cfg["allow_entry"] is True
    assert cfg["max_positions"] == 2


def test_regime_risk_off():
    cfg = get_regime_config(28.0)
    assert cfg["allow_entry"] is False
