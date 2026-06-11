from __future__ import annotations

import pandas as pd


def make_utc_naive_index(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    if index.tz is not None:
        return index.tz_convert("UTC").tz_localize(None)
    return index


def make_utc_naive_timestamp(timestamp: pd.Timestamp) -> pd.Timestamp:
    if timestamp.tzinfo is not None:
        return timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp


def remove_incomplete_period(df: pd.DataFrame | None, resolution: str, now_utc: pd.Timestamp) -> pd.DataFrame | None:
    if df is None or df.empty:
        return df

    clean = df.copy()
    clean.index = make_utc_naive_index(clean.index)
    now_clean = make_utc_naive_timestamp(now_utc)

    if resolution == "Monthly":
        current_period = now_clean.to_period("M")
        return clean[clean.index.to_period("M") < current_period]

    if resolution == "Weekly":
        current_period = now_clean.to_period("W-SUN")
        return clean[clean.index.to_period("W-SUN") < current_period]

    return clean


def resample_ohlc(df_daily: pd.DataFrame, resolution: str, now_utc: pd.Timestamp) -> pd.DataFrame:
    rules = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if resolution == "Monthly":
        df = df_daily.resample("ME").agg(rules).dropna()
    elif resolution == "Weekly":
        df = df_daily.resample("W-SUN").agg(rules).dropna()
    else:
        raise ValueError(f"Unsupported resolution: {resolution}")

    filtered = remove_incomplete_period(df, resolution, now_utc)
    return filtered if filtered is not None else pd.DataFrame(columns=["open", "high", "low", "close"])
