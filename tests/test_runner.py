import pandas as pd

from crypto_scanner.runner import should_run, tab_names


def test_manual_non_schedule_runs_both():
    assert should_run(pd.Timestamp("2026-06-11T12:00:00", tz="Asia/Karachi")) == (True, True)


def test_monday_runs_weekly():
    assert should_run(pd.Timestamp("2026-06-08T05:17:00", tz="Asia/Karachi")) == (False, True)


def test_first_runs_monthly():
    assert should_run(pd.Timestamp("2026-07-01T05:17:00", tz="Asia/Karachi")) == (True, False)


def test_first_monday_runs_both_once():
    assert should_run(pd.Timestamp("2026-06-01T05:17:00", tz="Asia/Karachi")) == (True, True)


def test_tab_names():
    monthly, weekly, summary = tab_names(pd.Timestamp("2026-06-11T05:17:00", tz="Asia/Karachi"))
    assert monthly == "Jun26_Monthly"
    assert weekly == "Jun26_W2"
    assert summary == "Jun26_Risk_Summary"
