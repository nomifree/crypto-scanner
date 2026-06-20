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
    loaded = load_market_data(make_instrument(tmp_path), pd.Timestamp("2026-06-19 13:00:00Z"))

    assert loaded.status == "Missing File"
    assert loaded.action_needed == "Add CSV export"


def test_bad_columns_marks_bad_columns(tmp_path):
    (tmp_path / "TEST.csv").write_text("Date,Price\n2026-06-19,100\n", encoding="utf-8")

    loaded = load_market_data(make_instrument(tmp_path), pd.Timestamp("2026-06-19 13:00:00Z"))

    assert loaded.status == "Bad Columns"
    assert loaded.action_needed == "Fix CSV columns"


def test_insufficient_rows_marks_insufficient_history(tmp_path):
    write_daily_csv(tmp_path / "TEST.csv", periods=10)

    loaded = load_market_data(make_instrument(tmp_path), pd.Timestamp("2026-06-19 13:00:00Z"))

    assert loaded.status == "Insufficient History"
    assert loaded.action_needed == "Export more history"


def test_current_active_candle_is_flagged_as_possibly_incomplete(tmp_path):
    write_daily_csv(tmp_path / "TEST.csv", periods=70, end="2026-06-19")
    now_before_close = pd.Timestamp("2026-06-19 08:00:00Z")

    loaded = load_market_data(make_instrument(tmp_path), now_before_close)

    assert loaded.status == "Possibly Incomplete"
    assert loaded.expected_closed == "2026-06-18"
