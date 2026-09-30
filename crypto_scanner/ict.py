from __future__ import annotations

import pandas as pd

from .models import IctSignal


def check_ict_logic(df: pd.DataFrame | None) -> IctSignal:
    """Simple 2-candle ICT detector.

    Patterns (last completed candle vs the one before it):

    A-Tier (Sniper) -- Liquidity Sweep at the right zone
      Bullish: candle dipped below prev low (stop hunt on shorts), closed back
               above it, and closed in the LOWER half of its own range (discount).
      Bearish: candle spiked above prev high (stop hunt on longs), closed back
               below it, and closed in the UPPER half of its own range (premium).

    B-Tier (Standard) -- Displacement (clean breakout/breakdown)
      Bullish: close > previous high (price broke out).
      Bearish: close < previous low (price broke down).
      That's it. No extra body/wick/zone filters -- a close past the prior
      barrier is itself the proof of momentum.

    C-Tier (Ignore) -- everything else.
      Sweeps that fired but closed in the wrong half (bullish at premium or
      bearish at discount) still report their bias but stay C-Tier ("wait for
      price to come back to the value zone").
    """
    if df is None or len(df) < 2:
        return IctSignal(False, "Neutral", None, "C-Tier (Ignore)")

    candle = df.iloc[-1]
    prev = df.iloc[-2]
    candle_range = float(candle["high"] - candle["low"])
    if candle_range <= 0:
        return IctSignal(False, "Neutral", None, "C-Tier (Ignore)")

    # Sweep: stop-hunt + reclaim/reject
    swept_low = candle["low"] < prev["low"]
    reclaimed_low = candle["close"] > prev["low"]
    swept_high = candle["high"] > prev["high"]
    rejected_high = candle["close"] < prev["high"]

    bullish_sweep = bool(swept_low and reclaimed_low)
    bearish_sweep = bool(swept_high and rejected_high)

    # Displacement: simple close beyond prior high/low
    bullish_displacement = bool(candle["close"] > prev["high"])
    bearish_displacement = bool(candle["close"] < prev["low"])

    # Valuation (just for context/reporting)
    midpoint = candle["low"] + candle_range * 0.5
    valuation = "Discount" if candle["close"] < midpoint else "Premium"

    # --- Tier grading (priority order: A -> B -> C) ---
    # A-Tier: sweep in the favorable half (stop-hunt + reclaim + good zone)
    if bullish_sweep and valuation == "Discount":
        return IctSignal(True, "Bullish Liquidity Sweep", valuation, "A-Tier (Sniper)")
    if bearish_sweep and valuation == "Premium":
        return IctSignal(True, "Bearish Liquidity Sweep", valuation, "A-Tier (Sniper)")

    # B-Tier: simple close beyond prev high/low (displacement / breakout)
    # This fires even if a sweep happened on the other side -- closing past the
    # prior barrier confirms momentum regardless of whether there was a wick.
    if bullish_displacement:
        return IctSignal(True, "Bullish Displacement", valuation, "B-Tier (Standard)")
    if bearish_displacement:
        return IctSignal(True, "Bearish Displacement", valuation, "B-Tier (Standard)")

    # C-Tier: sweep happened but price is in the wrong half (bias known,
    # wait for a pullback to the value zone), or no pattern at all.
    if bullish_sweep:
        return IctSignal(True, "Bullish Liquidity Sweep", valuation, "C-Tier (Ignore)")
    if bearish_sweep:
        return IctSignal(True, "Bearish Liquidity Sweep", valuation, "C-Tier (Ignore)")

    return IctSignal(False, "Neutral", valuation, "C-Tier (Ignore)")
