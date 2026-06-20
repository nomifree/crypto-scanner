from pathlib import Path

import pandas as pd

from crypto_scanner.market_data import MarketInstrument, load_market_data, normalize_market_csv


def make_instrument(data_dir: Path, csv_file: str = "TEST.csv", close_hour_pkt: int = 17) -> MarketInstrument:
    return MarketInstrument(
        symbol="TEST",
        display_name="Test Instrument",
        market_group="Test Sector",
        universe="Custom Watchlist",
        csv_file=csv_file,
        data_dir=str(data_dir),
        client_suitability="Scenario planning",
        shariah_status="Review",
        risk_note="Test risk note.",
        close_hour_pkt=close_hour_pkt,
        auto_symbol="TEST.KA",
    )


def write_daily_csv(path: Path, periods: int = 70, end: str = "2026-06-19") -> None:
    dates = pd.bdate_range(end=end, periods=periods)
    rows = []
    for i, date in enumerate(dates):
        base = 100 + i
        rows.append(
            {
                "Date": date.strftime("%Y-%m-%d"),
                "Open": base,
                "High": base + 3,
                "Low": base - 2,
                "Close": base + 1,
                "Volume": 1000 + i,
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def test_psx_style_csv_loads_correctly(tmp_path):
    csv_path = tmp_path / "TEST.csv"
    write_daily_csv(csv_path)

    df = normalize_market_csv(csv_path)

    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len(df) == 70
    assert df.iloc[-1]["close"] > 0


def test_missing_file_marks_missing_file(tmp_path):
    loaded = load_market_data(make_instrument(tmp_path), pd.Timestamp("2026-06-19 13:00:00Z"), auto_enabled=False)

    assert loaded.status == "Missing File"
    assert loaded.action_needed == "Add CSV export"


def test_bad_columns_marks_bad_columns(tmp_path):
    (tmp_path / "TEST.csv").write_text("Date,Price\n2026-06-19,100\n", encoding="utf-8")

    loaded = load_market_data(make_instrument(tmp_path), pd.Timestamp("2026-06-19 13:00:00Z"), auto_enabled=False)

    assert loaded.status == "Bad Columns"
    assert loaded.action_needed == "Fix CSV columns"


def test_insufficient_rows_marks_insufficient_history(tmp_path):
    write_daily_csv(tmp_path / "TEST.csv", periods=10)

    loaded = load_market_data(make_instrument(tmp_path), pd.Timestamp("2026-06-19 13:00:00Z"), auto_enabled=False)

    assert loaded.status == "Insufficient History"
    assert loaded.action_needed == "Fetch/export more history"


def test_current_active_candle_is_flagged_as_possibly_incomplete(tmp_path):
    write_daily_csv(tmp_path / "TEST.csv", periods=70, end="2026-06-19")
    now_before_close = pd.Timestamp("2026-06-19 08:00:00Z")

    loaded = load_market_data(make_instrument(tmp_path), now_before_close, auto_enabled=False)

    assert loaded.status == "Possibly Incomplete"
    assert loaded.expected_closed == "2026-06-18"


def test_auto_fetch_loads_without_csv(tmp_path, monkeypatch):
    csv_path = tmp_path / "AUTO.csv"
    write_daily_csv(csv_path)
    fetched_df = normalize_market_csv(csv_path)

    monkeypatch.setattr("crypto_scanner.market_data.fetch_yahoo_ohlc", lambda symbol: fetched_df)

    loaded = load_market_data(make_instrument(tmp_path, "MISSING.csv"), pd.Timestamp("2026-06-19 13:00:00Z"))

    assert loaded.status == "Fresh"
    assert loaded.source == "Yahoo Finance: TEST.KA"
    assert loaded.rows_loaded == 70


def test_csv_fallback_works_when_auto_fetch_fails(tmp_path, monkeypatch):
    write_daily_csv(tmp_path / "TEST.csv")

    def fail_fetch(symbol):
        raise ValueError("network unavailable")

    monkeypatch.setattr("crypto_scanner.market_data.fetch_yahoo_ohlc", fail_fetch)

    loaded = load_market_data(make_instrument(tmp_path), pd.Timestamp("2026-06-19 13:00:00Z"))

    assert loaded.status == "Fresh"
    assert loaded.source.endswith("TEST.csv")
