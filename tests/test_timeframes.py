import pandas as pd

from crypto_scanner.timeframes import resample_ohlc


def daily_frame(start="2026-05-01", periods=45):
    idx = pd.date_range(start, periods=periods, freq="D", tz="UTC")
    values = range(1, periods + 1)
    return pd.DataFrame(
        {
            "open": list(values),
            "high": [v + 1 for v in values],
            "low": [v - 1 for v in values],
            "close": list(values),
        },
        index=idx,
    )


def test_monthly_excludes_current_month():
    df = daily_frame("2026-05-01", 45)
    out = resample_ohlc(df, "Monthly", pd.Timestamp("2026-06-11T00:00:00Z"))
    assert len(out) == 1
    assert out.index[0].month == 5


def test_weekly_uses_sunday_close_and_excludes_current_week():
    df = daily_frame("2026-05-25", 15)
    out = resample_ohlc(df, "Weekly", pd.Timestamp("2026-06-01T12:00:00Z"))
    assert len(out) == 1
    assert out.index[0].strftime("%Y-%m-%d") == "2026-05-31"


def test_june_first_monday_gets_previous_closed_week():
    df = daily_frame("2026-05-18", 22)
    out = resample_ohlc(df, "Weekly", pd.Timestamp("2026-06-01T00:17:00Z"))
    assert out.index[-1].strftime("%Y-%m-%d") == "2026-05-31"
