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
    auto_symbol: str | None = None
    auto_source: str = "Yahoo Finance"

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
    source: str


DATE_ALIASES = {"date", "time", "datetime", "<date>", "timestamp"}
OPEN_ALIASES = {"open", "<open>"}
HIGH_ALIASES = {"high", "<high>"}
LOW_ALIASES = {"low", "<low>"}
CLOSE_ALIASES = {"close", "<close>"}
VOLUME_ALIASES = {"volume", "tick_volume", "real_volume", "<tickvol>", "<vol>", "vol"}
YAHOO_CHART_URLS = [
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
    "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
]
YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
}


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


def fetch_yahoo_ohlc(symbol: str, range_period: str = "2y") -> pd.DataFrame:
    import requests

    errors = []
    payload = None
    for template in YAHOO_CHART_URLS:
        url = template.format(symbol=symbol)
        try:
            response = requests.get(
                url,
                params={"range": range_period, "interval": "1d", "includePrePost": "false", "events": "history"},
                headers=YAHOO_HEADERS,
                timeout=30,
            )
            if response.status_code != 200:
                errors.append(f"{response.url} returned HTTP {response.status_code}: {response.text[:120]}")
                continue
            payload = response.json()
            break
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    if payload is None:
        raise ValueError("; ".join(errors) or "Yahoo request failed")

    result = payload.get("chart", {}).get("result") or []
    if not result:
        error = payload.get("chart", {}).get("error")
        raise ValueError(f"No Yahoo chart result: {error}")

    chart = result[0]
    timestamps = chart.get("timestamp") or []
    quote_data = (chart.get("indicators", {}).get("quote") or [{}])[0]
    if not timestamps or not quote_data:
        raise ValueError("No Yahoo OHLC data")

    df = pd.DataFrame(
        {
            "datetime": pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(None),
            "open": quote_data.get("open"),
            "high": quote_data.get("high"),
            "low": quote_data.get("low"),
            "close": quote_data.get("close"),
            "volume": quote_data.get("volume"),
        }
    )
    df = df.dropna(subset=["datetime", "open", "high", "low", "close"])
    if df.empty:
        raise ValueError("Empty Yahoo OHLC data")
    df.set_index("datetime", inplace=True)
    return df.sort_index()[["open", "high", "low", "close", "volume"]]


def fetch_yfinance_ohlc(symbol: str) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(
        symbol,
        period="2y",
        interval="1d",
        progress=False,
        auto_adjust=False,
        threads=False,
    )
    if raw is None or raw.empty:
        raise ValueError("yfinance returned no rows")
    if isinstance(raw.columns, pd.MultiIndex):
        raw = raw.droplevel(-1, axis=1)

    columns = {str(column).strip().lower(): column for column in raw.columns}
    required = ["open", "high", "low", "close"]
    if any(column not in columns for column in required):
        raise ValueError(f"yfinance missing OHLC columns: {list(raw.columns)}")

    df = pd.DataFrame(
        {
            "open": pd.to_numeric(raw[columns["open"]], errors="coerce"),
            "high": pd.to_numeric(raw[columns["high"]], errors="coerce"),
            "low": pd.to_numeric(raw[columns["low"]], errors="coerce"),
            "close": pd.to_numeric(raw[columns["close"]], errors="coerce"),
            "volume": pd.to_numeric(raw[columns["volume"]], errors="coerce") if "volume" in columns else pd.NA,
        },
        index=pd.to_datetime(raw.index),
    )
    df = df.dropna(subset=["open", "high", "low", "close"])
    if df.empty:
        raise ValueError("yfinance OHLC rows were empty after cleanup")
    df.index = pd.DatetimeIndex(df.index).tz_localize(None) if pd.DatetimeIndex(df.index).tz is not None else df.index
    return df.sort_index()[["open", "high", "low", "close", "volume"]]


def fetch_auto_ohlc(symbol: str) -> tuple[pd.DataFrame, str]:
    errors = []
    try:
        return fetch_yahoo_ohlc(symbol), "Yahoo Finance"
    except Exception as exc:
        errors.append(f"chart={exc}")

    try:
        return fetch_yfinance_ohlc(symbol), "Yahoo Finance yfinance"
    except Exception as exc:
        errors.append(f"yfinance={exc}")

    raise ValueError("; ".join(errors))


def _assess_loaded_dataframe(
    instrument: MarketInstrument,
    df: pd.DataFrame,
    expected: pd.Timestamp,
    source: str,
    min_rows: int,
) -> LoadedMarketData:
    rows_loaded = len(df)
    last_date = pd.Timestamp(df.index.max()).normalize()
    expected_naive = expected.tz_localize(None) if expected.tzinfo else expected
    if rows_loaded < min_rows:
        status = "Insufficient History"
        action = "Fetch/export more history"
    elif last_date > expected_naive:
        status = "Possibly Incomplete"
        action = "Confirm latest candle is closed"
    elif last_date == expected_naive:
        status = "Fresh"
        action = "OK"
    else:
        status = "Stale"
        action = "Check data provider or update CSV"

    return LoadedMarketData(
        instrument,
        df,
        status,
        "OK" if status in {"Fresh", "Stale", "Possibly Incomplete"} else status,
        action,
        last_date.strftime("%Y-%m-%d"),
        expected.strftime("%Y-%m-%d"),
        rows_loaded,
        source,
    )


def _missing_loaded(instrument: MarketInstrument, expected: pd.Timestamp, action: str, quality: str = "Missing File") -> LoadedMarketData:
    return LoadedMarketData(
        instrument,
        None,
        "Missing File",
        quality,
        action,
        "",
        expected.strftime("%Y-%m-%d"),
        0,
        quality,
    )


def load_market_data(
    instrument: MarketInstrument,
    now_utc: pd.Timestamp,
    min_rows: int = 60,
    auto_enabled: bool = True,
) -> LoadedMarketData:
    expected = expected_latest_closed_date(now_utc, instrument.close_hour_pkt)
    auto_error = ""
    if auto_enabled and instrument.auto_symbol:
        try:
            df, source = fetch_auto_ohlc(instrument.auto_symbol)
            return _assess_loaded_dataframe(
                instrument,
                df,
                expected,
                f"{source}: {instrument.auto_symbol}",
                min_rows,
            )
        except Exception as exc:
            auto_error = str(exc)

    path = instrument.csv_path
    if not path.exists():
        action = f"Auto fetch failed: {auto_error[:180]}; add CSV export" if auto_error else "Add CSV export"
        quality = "Auto Fetch Failed" if auto_error else "Missing File"
        return _missing_loaded(instrument, expected, action, quality)

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
            str(path),
        )

    return _assess_loaded_dataframe(instrument, df, expected, str(path), min_rows)


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
        loaded.source,
        loaded.action_needed,
    ]
