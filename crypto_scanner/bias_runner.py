from __future__ import annotations

from typing import Any

import pandas as pd

from .config import MARKET_BIAS_HEADERS, MARKET_STATUS_HEADERS
from .ict import check_ict_logic
from .market_data import LoadedMarketData, MarketInstrument, load_market_data, status_row
from .pmex_config import pmex_instruments
from .psx_config import psx_instruments
from .session_status import freshness_is_usable, freshness_note
from .timeframes import resample_ohlc


def bias_strength(grade: str) -> str:
    if grade.startswith("A-Tier"):
        return "Strong"
    if grade.startswith("B-Tier"):
        return "Moderate"
    return "Weak"


def invalidation_reference(df: pd.DataFrame, bias: str) -> str:
    if df is None or df.empty:
        return ""
    candle = df.iloc[-1]
    if "Bullish" in bias:
        return f"Below last completed low {float(candle['low']):.4f}"
    if "Bearish" in bias:
        return f"Above last completed high {float(candle['high']):.4f}"
    return f"Range {float(candle['low']):.4f} - {float(candle['high']):.4f}"


def liquidity_note(df: pd.DataFrame | None, market_type: str) -> str:
    if df is None or df.empty or "volume" not in df.columns:
        return "Volume not available"
    volume = df["volume"].dropna().tail(20)
    if volume.empty:
        return "Volume not available"
    latest = float(volume.iloc[-1])
    avg = float(volume.mean())
    if latest >= avg:
        return "Volume at/above 20D average"
    return "Volume below 20D average"


def alignment(monthly_bias: str, weekly_bias: str, monthly_grade: str, weekly_grade: str) -> str:
    if monthly_grade.startswith("C-Tier") or weekly_grade.startswith("C-Tier"):
        return "Watch only"
    monthly_bull = "Bullish" in monthly_bias
    weekly_bull = "Bullish" in weekly_bias
    monthly_bear = "Bearish" in monthly_bias
    weekly_bear = "Bearish" in weekly_bias
    if monthly_bull and weekly_bull:
        return "Strongest bullish scenario"
    if monthly_bear and weekly_bear:
        return "Strongest bearish scenario"
    if monthly_bull and weekly_bear:
        return "Pullback / wait for confirmation"
    if monthly_bear and weekly_bull:
        return "Countertrend bounce / caution"
    return "Neutral / watch"


def market_risk_note(instrument: MarketInstrument, signal_grade: str, freshness: str) -> str:
    notes = [instrument.risk_note]
    if signal_grade.startswith("C-Tier"):
        notes.append("C-Tier means watch only; do not push as a trade idea.")
    if freshness != "Fresh":
        notes.append(freshness_note(freshness))
    return " ".join(notes)


def bias_row(
    loaded: LoadedMarketData,
    resolution: str,
    df_resampled: pd.DataFrame,
    signal,
    alignment_text: str,
    timestamp: str,
    market_type: str,
) -> list[Any]:
    instrument = loaded.instrument
    last_candle_date = ""
    last_close = ""
    last_volume = ""
    if df_resampled is not None and not df_resampled.empty:
        last_candle_date = pd.Timestamp(df_resampled.index[-1]).strftime("%Y-%m-%d")
        last_close = float(df_resampled.iloc[-1]["close"])
        if "volume" in df_resampled.columns and pd.notna(df_resampled.iloc[-1].get("volume")):
            last_volume = float(df_resampled.iloc[-1]["volume"])
    return [
        timestamp,
        instrument.symbol,
        instrument.display_name,
        instrument.market_group,
        instrument.universe,
        resolution,
        last_candle_date,
        last_close,
        last_volume,
        signal.bias,
        signal.valuation,
        signal.grade,
        bias_strength(signal.grade),
        alignment_text,
        instrument.client_suitability,
        invalidation_reference(df_resampled, signal.bias),
        liquidity_note(loaded.df, market_type),
        instrument.shariah_status,
        market_risk_note(instrument, signal.grade, loaded.status),
        str(instrument.csv_path),
        loaded.status,
    ]


def evaluate_market_instrument(
    loaded: LoadedMarketData,
    now_utc: pd.Timestamp,
    timestamp: str,
    market_type: str,
) -> tuple[list[Any] | None, list[Any] | None]:
    if loaded.df is None or not freshness_is_usable(loaded.status):
        return None, None
    monthly = resample_ohlc(loaded.df, "Monthly", now_utc)
    weekly = resample_ohlc(loaded.df, "Weekly", now_utc)
    monthly_signal = check_ict_logic(monthly)
    weekly_signal = check_ict_logic(weekly)
    align = alignment(monthly_signal.bias, weekly_signal.bias, monthly_signal.grade, weekly_signal.grade)
    return (
        bias_row(loaded, "Monthly", monthly, monthly_signal, align, timestamp, market_type),
        bias_row(loaded, "Weekly", weekly, weekly_signal, align, timestamp, market_type),
    )


def scan_market_group(
    instruments: list[MarketInstrument],
    market_type: str,
    now_utc: pd.Timestamp | None = None,
) -> tuple[dict[str, tuple[list[str], list[list[Any]]]], dict[str, tuple[list[str], list[list[Any]]]]]:
    now_utc = now_utc or pd.Timestamp.utcnow()
    now_pkt = now_utc.tz_convert("Asia/Karachi")
    timestamp = now_pkt.strftime("%Y-%m-%d")
    prefix = market_type.upper()
    monthly_rows: list[list[Any]] = []
    weekly_rows: list[list[Any]] = []
    status_rows: list[list[Any]] = []

    for instrument in instruments:
        loaded = load_market_data(instrument, now_utc)
        status_rows.append(status_row(loaded, timestamp))
        monthly_row, weekly_row = evaluate_market_instrument(loaded, now_utc, timestamp, market_type)
        if monthly_row:
            monthly_rows.append(monthly_row)
        if weekly_row:
            weekly_rows.append(weekly_row)

    bias_tabs = {
        f"{prefix}_Monthly_Bias": (MARKET_BIAS_HEADERS, monthly_rows),
        f"{prefix}_Weekly_Bias": (MARKET_BIAS_HEADERS, weekly_rows),
    }
    status_tabs = {f"{prefix}_Update_Status": (MARKET_STATUS_HEADERS, status_rows)}
    return bias_tabs, status_tabs


def scan_pmex(now_utc: pd.Timestamp | None = None):
    return scan_market_group(pmex_instruments(), "PMEX", now_utc)


def scan_psx(now_utc: pd.Timestamp | None = None):
    return scan_market_group(psx_instruments(), "PSX", now_utc)


def scan_markets(mode: str, now_utc: pd.Timestamp | None = None) -> dict[str, tuple[list[str], list[list[Any]]]]:
    tabs: dict[str, tuple[list[str], list[list[Any]]]] = {}
    if mode in {"pmex", "markets", "all"}:
        bias, status = scan_pmex(now_utc)
        tabs.update(bias)
        tabs.update(status)
    if mode in {"psx", "markets", "all"}:
        bias, status = scan_psx(now_utc)
        tabs.update(bias)
        tabs.update(status)
    return tabs
