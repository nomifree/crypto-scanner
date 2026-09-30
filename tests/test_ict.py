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


def test_bullish_displacement_fires_on_close_beyond_prior_high():
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
    assert signal.grade == "B-Tier (Standard)"


def test_close_above_prior_high_is_displacement_even_with_small_body_or_poor_position():
    df = frame(
        [
            [100, 110, 90, 100],
            [100, 105, 95, 100],
            [104, 112, 95, 106],
        ]
    )
    signal = check_ict_logic(df)
    assert signal.qualified
    assert signal.bias == "Bullish Displacement"
    assert signal.grade == "B-Tier (Standard)"
    assert signal.valuation == "Premium"


def test_sweep_at_premium_is_c_tier_with_bias_preserved():
    # Bullish sweep (wick below prev low then close back above) but close sits
    # in the TOP half of the candle's range (premium) and does NOT break the
    # prior high -> C-Tier; bias is still surfaced for watchlists.
    df = frame(
        [
            [100, 110, 90, 100],
            [100, 110, 95, 105],
            [102, 108, 90, 105],
        ]
    )
    signal = check_ict_logic(df)
    assert signal.qualified
    assert signal.bias == "Bullish Liquidity Sweep"
    assert signal.grade == "C-Tier (Ignore)"
    assert signal.valuation == "Premium"


def test_neutral_when_no_sweep_and_no_displacement():
    df = frame(
        [
            [100, 110, 90, 100],
            [100, 105, 95, 100],
            [99, 104, 96, 101],
        ]
    )
    signal = check_ict_logic(df)
    assert not signal.qualified
