from __future__ import annotations

import pandas as pd

from .models import IctSignal


def check_ict_logic(df: pd.DataFrame | None) -> IctSignal:
    if df is None or len(df) < 2:
        return IctSignal(False, "Neutral", None, "C-Tier (Ignore)")

    candle = df.iloc[-1]
    prev = df.iloc[-2]
    candle_range = float(candle["high"] - candle["low"])
    body = abs(float(candle["close"] - candle["open"]))

    if candle_range <= 0:
        return IctSignal(False, "Neutral", None, "C-Tier (Ignore)")

    swept_low = candle["low"] < prev["low"]
    reclaimed_low = candle["close"] > prev["low"]
    swept_high = candle["high"] > prev["high"]
    rejected_high = candle["close"] < prev["high"]

    bullish_sweep = bool(swept_low and reclaimed_low)
    bearish_sweep = bool(swept_high and rejected_high)

    strong_body = body >= candle_range * 0.60
    close_top_quarter = candle["close"] >= candle["low"] + (candle_range * 0.75)
    close_bottom_quarter = candle["close"] <= candle["low"] + (candle_range * 0.25)

    bullish_displacement = bool(candle["close"] > prev["high"] and strong_body and close_top_quarter)
    bearish_displacement = bool(candle["close"] < prev["low"] and strong_body and close_bottom_quarter)

    midpoint = candle["low"] + (candle_range * 0.5)
    valuation = "Discount" if candle["close"] < midpoint else "Premium"

    if bullish_sweep:
        bias = "Bullish Liquidity Sweep"
    elif bullish_displacement:
        bias = "Bullish Displacement"
    elif bearish_sweep:
        bias = "Bearish Liquidity Sweep"
    elif bearish_displacement:
        bias = "Bearish Displacement"
    else:
        return IctSignal(False, "Neutral", valuation, "C-Tier (Ignore)")

    grade = "C-Tier (Ignore)"
    if (bullish_sweep or bullish_displacement) and valuation == "Discount":
        grade = "A-Tier (Sniper)" if bullish_sweep else "B-Tier (Standard)"
    elif (bearish_sweep or bearish_displacement) and valuation == "Premium":
        grade = "A-Tier (Sniper)" if bearish_sweep else "B-Tier (Standard)"

    return IctSignal(True, bias, valuation, grade)
