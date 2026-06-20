import pandas as pd

from crypto_scanner.bias_runner import scan_market_group, scan_markets
from crypto_scanner.market_data import MarketInstrument
from crypto_scanner.psx_config import psx_instruments


def make_instrument(tmp_path) -> MarketInstrument:
    return MarketInstrument(
        symbol="TEST",
        display_name="Test Stock",
        market_group="Technology",
        universe="Custom Watchlist",
        csv_file="TEST.csv",
        data_dir=str(tmp_path),
        client_suitability="Swing context only",
        shariah_status="Review",
        risk_note="Custom PSX name requires Shariah review.",
        close_hour_pkt=17,
    )


def write_bias_fixture(tmp_path) -> None:
    dates = pd.bdate_range(end="2026-06-19", periods=180)
    rows = []
    for i, date in enumerate(dates):
        base = 100 + (i * 0.5)
        rows.append(
            {
                "Date": date.strftime("%Y-%m-%d"),
                "Open": base,
                "High": base + 4,
                "Low": base - 3,
                "Close": base + 2,
                "Volume": 10000 + i,
            }
        )
    pd.DataFrame(rows).to_csv(tmp_path / "TEST.csv", index=False)


def test_scan_market_group_creates_bias_and_status_tabs(tmp_path):
    write_bias_fixture(tmp_path)
    now = pd.Timestamp("2026-06-19 13:00:00Z")

    bias_tabs, status_tabs = scan_market_group([make_instrument(tmp_path)], "PSX", now)

    assert set(bias_tabs) == {"PSX_Monthly_Bias", "PSX_Weekly_Bias"}
    assert set(status_tabs) == {"PSX_Update_Status"}
    assert len(bias_tabs["PSX_Monthly_Bias"][1]) == 1
    assert len(bias_tabs["PSX_Weekly_Bias"][1]) == 1
    assert status_tabs["PSX_Update_Status"][1][0][5] == "Fresh"


def test_psx_kmi_universe_marks_kmi_pass():
    instruments = {instrument.symbol: instrument for instrument in psx_instruments()}

    assert instruments["MEBL"].shariah_status == "KMI Pass"
    assert instruments["SYS"].shariah_status == "KMI Pass"


def test_scan_mode_markets_runs_pmex_and_psx_status_tabs(tmp_path, monkeypatch):
    monkeypatch.setenv("PMEX_DATA_DIR", str(tmp_path / "pmex"))
    monkeypatch.setenv("PSX_DATA_DIR", str(tmp_path / "psx"))

    tabs = scan_markets("markets", pd.Timestamp("2026-06-19 13:00:00Z"))

    assert "PMEX_Update_Status" in tabs
    assert "PSX_Update_Status" in tabs
    assert "PMEX_Monthly_Bias" in tabs
    assert "PSX_Monthly_Bias" in tabs


def test_scan_mode_psx_runs_only_psx_tabs():
    tabs = scan_markets("psx", pd.Timestamp("2026-06-19 13:00:00Z"))

    assert "PSX_Update_Status" in tabs
    assert "PMEX_Update_Status" not in tabs
