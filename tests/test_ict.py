import pandas as pd

from crypto_scanner.ict import check_ict_logic


def frame(rows):
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"])


def test_bullish_sweep_discount_is_a_tier():
    df = frame(
        [
            [100, 110, 90, 100],
            [100, 105, 95, 100],
            [100, 104, 90, 96],
        ]
    )
    signal = check_ict_logic(df)
    assert signal.qualified
    assert signal.bias == "Bullish Liquidity Sweep"
    assert signal.grade == "A-Tier (Sniper)"


def test_bullish_displacement_requires_strong_body_and_top_close():
    df = frame(
        [
            [100, 110, 90, 100],
            [100, 105, 95, 100],
            [96, 112, 95, 111],
        ]
    )
    signal = check_ict_logic(df)
    assert signal.qualified
    assert signal.bias == "Bullish Displacement"


def test_weak_close_above_high_is_not_displacement():
    df = frame(
        [
            [100, 110, 90, 100],
            [100, 105, 95, 100],
            [104, 112, 95, 106],
        ]
    )
    signal = check_ict_logic(df)
    assert not signal.qualified


def test_c_tier_signal_is_retained_when_valuation_misaligned():
    df = frame(
        [
            [100, 110, 90, 100],
            [100, 105, 95, 100],
            [100, 125, 94, 121],
        ]
    )
    signal = check_ict_logic(df)
    assert signal.qualified
    assert signal.grade == "C-Tier (Ignore)"
