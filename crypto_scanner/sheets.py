from __future__ import annotations

import json
from typing import Any

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:  # pragma: no cover - production installs these.
    gspread = None
    Credentials = None

from .config import BASE_HEADERS, RISK_HEADERS, SETTINGS, SUMMARY_HEADERS


def column_label(index: int) -> str:
    label = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        label = chr(65 + remainder) + label
    return label


def authorize_sheet():
    if gspread is None or Credentials is None:
        raise RuntimeError("gspread and google-auth must be installed for live Google Sheets delivery.")
    if not SETTINGS.spreadsheet_id or not SETTINGS.credentials_json:
        raise RuntimeError("SPREADSHEET_ID and GOOGLE_CREDENTIALS_JSON must be set.")
    creds_dict = json.loads(SETTINGS.credentials_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds).open_by_key(SETTINGS.spreadsheet_id)


def write_tab(sh, tab_name: str, headers: list[str], rows: list[list[Any]]) -> None:
    print(f"Writing {len(rows)} rows to tab: {tab_name}")
    row_count = str(max(len(rows) + 10, 500))
    col_count = str(max(len(headers) + 2, 10))
    try:
        ws = sh.worksheet(tab_name)
        ws.clear()
        ws.resize(rows=int(row_count), cols=int(col_count))
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab_name, rows=row_count, cols=col_count, index=0)
    ws.append_row(headers)
    if rows:
        ws.append_rows(rows)
    else:
        ws.append_row(["No setups found."] + [""] * (len(headers) - 1))
    ws.freeze(rows=1)
    last_col = column_label(len(headers))
    ws.format(
        f"A1:{last_col}1",
        {
            "backgroundColor": {"red": 0.1, "green": 0.1, "blue": 0.1},
            "textFormat": {
                "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                "bold": True,
            },
            "horizontalAlignment": "LEFT",
        },
    )


def deliver_outputs(
    base_tabs: dict[str, list[list[Any]]],
    risk_tabs: dict[str, list[list[Any]]],
    summary_tab_name: str,
    summary_rows: list[list[Any]],
) -> None:
    if SETTINGS.dry_run:
        print("DRY_RUN=true; Google Sheets write skipped.")
        for name, rows in {**base_tabs, **risk_tabs, summary_tab_name: summary_rows}.items():
            print(f"DRY_RUN {name}: {len(rows)} rows")
        return

    sh = authorize_sheet()
    for tab_name, rows in base_tabs.items():
        write_tab(sh, tab_name, BASE_HEADERS, rows)
    for tab_name, rows in risk_tabs.items():
        write_tab(sh, tab_name, RISK_HEADERS, rows)
    write_tab(sh, summary_tab_name, SUMMARY_HEADERS, summary_rows)
