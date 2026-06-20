from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class MarketInstrument:
    symbol: str
    display_name: str
    market_group: str
    universe: str
    csv_file: str
    data_dir: str
    client_suitability: str
    shariah_status: str
    risk_note: str
    close_hour_pkt: int

    @property
    def csv_path(self) -> Path:
        return Path(self.data_dir) / self.csv_file


@dataclass
class LoadedMarketData:
    instrument: MarketInstrument
    df: pd.DataFrame | None
    status: str
    data_quality: str
    action_needed: str
    last_available: str
    expected_closed: str
    rows_loaded: int


DATE_ALIASES = {"date", "time", "datetime", "<date>", "timestamp"}
OPEN_ALIASES = {"open", "<open>"}
HIGH_ALIASES = {"high", "<high>"}
LOW_ALIASES = {"low", "<low>"}
CLOSE_ALIASES = {"close", "<close>"}
VOLUME_ALIASES = {"volume", "tick_volume", "real_volume", "<tickvol>", "<vol>", "vol"}


def previous_weekday(day: pd.Timestamp) -> pd.Timestamp:
    candidate = day - pd.Timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= pd.Timedelta(days=1)
    return candidate


def expected_latest_closed_date(now_utc: pd.Timestamp, close_hour_pkt: int) -> pd.Timestamp:
    now_pkt = now_utc.tz_convert("Asia/Karachi")
    today = now_pkt.normalize()
    if today.weekday() >= 5:
        return previous_weekday(today)
    if now_pkt.hour < close_hour_pkt:
        return previous_weekday(today)
    return today


def _find_column(columns: list[str], aliases: set[str]) -> str | None:
    normalized = {column.strip().lower(): column for column in columns}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return None


def normalize_market_csv(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    columns = list(raw.columns)
    date_col = _find_column(columns, DATE_ALIASES)
    open_col = _find_column(columns, OPEN_ALIASES)
    high_col = _find_column(columns, HIGH_ALIASES)
    low_col = _find_column(columns, LOW_ALIASES)
    close_col = _find_column(columns, CLOSE_ALIASES)
    volume_col = _find_column(columns, VOLUME_ALIASES)
    required = [date_col, open_col, high_col, low_col, close_col]
    if any(column is None for column in required):
        raise ValueError("Bad Columns")

    df = pd.DataFrame(
        {
            "datetime": pd.to_datetime(raw[date_col], errors="coerce"),
            "open": pd.to_numeric(raw[open_col], errors="coerce"),
            "high": pd.to_numeric(raw[high_col], errors="coerce"),
            "low": pd.to_numeric(raw[low_col], errors="coerce"),
            "close": pd.to_numeric(raw[close_col], errors="coerce"),
            "volume": pd.to_numeric(raw[volume_col], errors="coerce") if volume_col else pd.NA,
        }
    )
    df = df.dropna(subset=["datetime", "open", "high", "low", "close"])
    if df.empty:
        raise ValueError("Bad Columns")
    df["datetime"] = pd.to_datetime(df["datetime"], utc=False)
    df.set_index("datetime", inplace=True)
    df = df.sort_index()
    return df[["open", "high", "low", "close", "volume"]]


def load_market_data(instrument: MarketInstrument, now_utc: pd.Timestamp, min_rows: int = 60) -> LoadedMarketData:
    expected = expected_latest_closed_date(now_utc, instrument.close_hour_pkt)
    path = instrument.csv_path
    if not path.exists():
        return LoadedMarketData(
            instrument,
            None,
            "Missing File",
            "Missing File",
            "Add CSV export",
            "",
            expected.strftime("%Y-%m-%d"),
            0,
        )

    try:
        df = normalize_market_csv(path)
    except (OSError, ValueError):
        return LoadedMarketData(
            instrument,
            None,
            "Bad Columns",
            "Bad Columns",
            "Fix CSV columns",
            "",
            expected.strftime("%Y-%m-%d"),
            0,
        )

    rows_loaded = len(df)
    last_date = pd.Timestamp(df.index.max()).normalize()
    expected_naive = expected.tz_localize(None) if expected.tzinfo else expected
    if rows_loaded < min_rows:
        status = "Insufficient History"
        action = "Export more history"
    elif last_date > expected_naive:
        status = "Possibly Incomplete"
        action = "Confirm latest candle is closed"
    elif last_date == expected_naive:
        status = "Fresh"
        action = "OK"
    else:
        status = "Stale"
        action = "Update CSV Export"

    return LoadedMarketData(
        instrument,
        df,
        status,
        "OK" if status in {"Fresh", "Stale", "Possibly Incomplete"} else status,
        action,
        last_date.strftime("%Y-%m-%d"),
        expected.strftime("%Y-%m-%d"),
        rows_loaded,
    )


def status_row(loaded: LoadedMarketData, timestamp: str) -> list[Any]:
    return [
        timestamp,
        loaded.instrument.symbol,
        str(loaded.instrument.csv_path),
        loaded.last_available,
        loaded.expected_closed,
        loaded.status,
        loaded.rows_loaded,
        loaded.data_quality,
        loaded.action_needed,
    ]
