"""
Crypto Monthly Price Action Scanner
Runs on the 1st of each month, scans Top 200 coins by market cap.

Condition A (Breakout):    M2 close > M1 high
Condition B (Sweep+Recovery): M2 low < M1 low AND M2 close > M1 low

Writes qualifying coins to Google Sheets.
"""

import os
import time
import requests
from datetime import datetime, timezone
from google.oauth2.service_account import Credentials
import gspread
import json

# ── Config ────────────────────────────────────────────────────────────────────
COINGECKO_API_KEY = os.environ.get("COINGECKO_API_KEY", "")  # optional, free tier works without
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
TOP_N_COINS = 200
DELAY_BETWEEN_REQUESTS = 1.5  # seconds — stay within CoinGecko free tier rate limits

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_top_coins(n=200):
    """Fetch top N coins by market cap from CoinGecko."""
    coins = []
    pages = (n // 250) + 1
    per_page = min(n, 250)
    for page in range(1, pages + 1):
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": page,
            "sparkline": False,
        }
        if COINGECKO_API_KEY:
            params["x_cg_demo_api_key"] = COINGECKO_API_KEY
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        coins.extend(resp.json())
        time.sleep(DELAY_BETWEEN_REQUESTS)
        if len(coins) >= n:
            break
    return coins[:n]


def get_monthly_ohlc(coin_id: str, months_needed: int = 3):
    """
    Fetch monthly OHLC for a coin via CoinGecko /coins/{id}/ohlc.
    Returns list of [timestamp, open, high, low, close] sorted oldest→newest.
    We fetch ~90 days (3 months) to reliably get the last 2 complete candles.
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    params = {"vs_currency": "usd", "days": 90}
    if COINGECKO_API_KEY:
        params["x_cg_demo_api_key"] = COINGECKO_API_KEY

    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code == 429:
        print(f"  Rate limited on {coin_id}, waiting 60s...")
        time.sleep(60)
        resp = requests.get(url, params=params, timeout=30)
    if resp.status_code != 200:
        return None

    raw = resp.json()  # [[ts, o, h, l, c], ...]

    # Group candles into months
    monthly = {}
    for candle in raw:
        ts, o, h, l, c = candle
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        key = (dt.year, dt.month)
        if key not in monthly:
            monthly[key] = {"open": o, "high": h, "low": l, "close": c, "ts": ts}
        else:
            monthly[key]["high"] = max(monthly[key]["high"], h)
            monthly[key]["low"] = min(monthly[key]["low"], l)
            monthly[key]["close"] = c  # last candle in month = close

    # Sort keys and return last 2 complete months (exclude current partial month)
    now = datetime.now(tz=timezone.utc)
    current_key = (now.year, now.month)
    sorted_keys = sorted([k for k in monthly.keys() if k != current_key])

    if len(sorted_keys) < 2:
        return None

    m1_key = sorted_keys[-2]  # two months ago
    m2_key = sorted_keys[-1]  # last completed month

    return {
        "m1": monthly[m1_key],
        "m2": monthly[m2_key],
        "m1_label": datetime(m1_key[0], m1_key[1], 1).strftime("%B %Y"),
        "m2_label": datetime(m2_key[0], m2_key[1], 1).strftime("%B %Y"),
    }


def evaluate_conditions(m1: dict, m2: dict):
    """
    Returns (condition, description) or (None, None) if no condition met.
    Condition A: M2 close > M1 high  (Breakout)
    Condition B: M2 low < M1 low AND M2 close > M1 low  (Sweep + Recovery)
    """
    cond_a = m2["close"] > m1["high"]
    cond_b = m2["low"] < m1["low"] and m2["close"] > m1["low"]

    if cond_a and cond_b:
        return "A + B", "Breakout above M1 high AND swept M1 low with recovery"
    elif cond_a:
        return "A", "Breakout — M2 closed above M1 high"
    elif cond_b:
        return "B", "Sweep + Recovery — M2 swept M1 low, closed back above"
    return None, None


def write_to_sheets(results: list, run_date: str, m1_label: str, m2_label: str):
    """Write scanner results to Google Sheets."""
    creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)

    # Create or get sheet named by run month
    sheet_name = run_date  # e.g. "2025-05-01"
    try:
        ws = sh.worksheet(sheet_name)
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=300, cols=12)

    # Headers
    headers = [
        "Rank", "Coin", "Symbol", "Condition", "Description",
        f"{m1_label} Open", f"{m1_label} High", f"{m1_label} Low", f"{m1_label} Close",
        f"{m2_label} Open", f"{m2_label} High", f"{m2_label} Low", f"{m2_label} Close",
        "M2 % Move",
    ]
    ws.append_row(headers)

    # Data rows
    for r in results:
        m2_pct = round(((r["m2"]["close"] - r["m2"]["open"]) / r["m2"]["open"]) * 100, 2)
        row = [
            r["rank"], r["name"], r["symbol"].upper(), r["condition"], r["description"],
            round(r["m1"]["open"], 6), round(r["m1"]["high"], 6),
            round(r["m1"]["low"], 6), round(r["m1"]["close"], 6),
            round(r["m2"]["open"], 6), round(r["m2"]["high"], 6),
            round(r["m2"]["low"], 6), round(r["m2"]["close"], 6),
            f"{m2_pct}%",
        ]
        ws.append_row(row)
        time.sleep(0.1)

    print(f"✅ Written {len(results)} coins to sheet '{sheet_name}'")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    run_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    print(f"🚀 Crypto Scanner starting — {run_date}")
    print(f"📊 Fetching Top {TOP_N_COINS} coins by market cap...")

    coins = get_top_coins(TOP_N_COINS)
    print(f"✅ Got {len(coins)} coins. Scanning monthly candles...\n")

    results = []
    m1_label, m2_label = "", ""

    for i, coin in enumerate(coins, 1):
        coin_id = coin["id"]
        name = coin["name"]
        symbol = coin["symbol"]
        rank = coin.get("market_cap_rank", i)

        print(f"  [{i}/{TOP_N_COINS}] {name} ({symbol.upper()})...", end=" ")

        try:
            data = get_monthly_ohlc(coin_id)
            time.sleep(DELAY_BETWEEN_REQUESTS)
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        if not data:
            print("skip (insufficient data)")
            continue

        m1_label = data["m1_label"]
        m2_label = data["m2_label"]
        condition, description = evaluate_conditions(data["m1"], data["m2"])

        if condition:
            results.append({
                "rank": rank, "name": name, "symbol": symbol,
                "condition": condition, "description": description,
                "m1": data["m1"], "m2": data["m2"],
            })
            print(f"✅ QUALIFIES — Condition {condition}")
        else:
            print("✗")

    print(f"\n📋 {len(results)} coins qualified out of {TOP_N_COINS} scanned.")

    if results and GOOGLE_CREDENTIALS_JSON and SPREADSHEET_ID:
        print("📤 Writing to Google Sheets...")
        write_to_sheets(results, run_date, m1_label, m2_label)
    elif not GOOGLE_CREDENTIALS_JSON:
        print("⚠️  GOOGLE_CREDENTIALS_JSON not set — printing results only:")
        for r in results:
            print(f"  {r['rank']}. {r['name']} ({r['symbol'].upper()}) — Condition {r['condition']}")
    
    print("\n✅ Scanner complete.")


if __name__ == "__main__":
    main()
