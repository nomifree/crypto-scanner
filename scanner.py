import os
import time
import json
import requests

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials


# --- CONFIGURATION ---
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
CG_API_KEY = os.getenv("COINGECKO_API_KEY")

CG_HEADERS = {"accept": "application/json"}
if CG_API_KEY:
    CG_HEADERS["x-cg-demo-api-key"] = CG_API_KEY

REQUEST_TIMEOUT = 20
DAILY_LIMIT = 240
MONTHLY_COIN_LIMIT = 350
WEEKLY_COIN_LIMIT = 100


def safe_get_json(url, headers=None, params=None, retries=2, pause=5):
    for attempt in range(retries + 1):
        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            if response.status_code == 429 and attempt < retries:
                time.sleep(max(pause, 30))
                continue
            if response.status_code != 200:
                return None
            return response.json()
        except requests.RequestException:
            if attempt >= retries:
                return None
            time.sleep(pause)
    return None


def get_top_coins(limit):
    print(f"Fetching Top {limit} list from CoinGecko...")
    url = "https://api.coingecko.com/api/v3/coins/markets"
    coins = []
    page = 1

    while len(coins) < limit:
        per_page = min(250, limit - len(coins))
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": page,
        }
        data = safe_get_json(url, headers=CG_HEADERS, params=params)
        if not data:
            break
        coins.extend(data)
        page += 1
        time.sleep(1)

    if not coins:
        raise RuntimeError(f"CoinGecko top-{limit} request failed.")
    return coins[:limit]


# --- WATERFALL DATA SOURCES ---
def normalize_ohlc_frame(data, columns):
    if not data or isinstance(data, dict):
        return None

    df = pd.DataFrame(data, columns=columns)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("datetime", inplace=True)
    df = df[["open", "high", "low", "close"]].astype(float)
    return df.sort_index()


def get_binance_data(symbol):
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": f"{symbol}USDT", "interval": "1d", "limit": DAILY_LIMIT}
    data = safe_get_json(url, params=params)
    return normalize_ohlc_frame(
        data,
        [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "qav",
            "num_trades",
            "tbbav",
            "tbqav",
            "ignore",
        ],
    )


def get_mexc_data(symbol):
    url = "https://api.mexc.com/api/v3/klines"
    params = {"symbol": f"{symbol}USDT", "interval": "1d", "limit": DAILY_LIMIT}
    data = safe_get_json(url, params=params)
    return normalize_ohlc_frame(
        data,
        ["timestamp", "open", "high", "low", "close", "volume", "close_time", "qav"],
    )


def get_kucoin_data(symbol):
    url = "https://api.kucoin.com/api/v1/market/candles"
    params = {"symbol": f"{symbol}-USDT", "type": "1day"}
    data = safe_get_json(url, params=params)
    rows = data.get("data") if isinstance(data, dict) else None
    if not rows:
        return None

    df = pd.DataFrame(
        rows,
        columns=["timestamp", "open", "close", "high", "low", "volume", "turnover"],
    )
    df["datetime"] = pd.to_datetime(df["timestamp"].astype(float), unit="s", utc=True)
    df.set_index("datetime", inplace=True)
    df = df[["open", "high", "low", "close"]].astype(float)
    return df.sort_index().tail(DAILY_LIMIT)


def get_okx_data(symbol):
    url = "https://www.okx.com/api/v5/market/candles"
    params = {"instId": f"{symbol}-USDT", "bar": "1Dutc", "limit": str(DAILY_LIMIT)}
    data = safe_get_json(url, params=params)
    rows = data.get("data") if isinstance(data, dict) else None
    if not rows:
        return None

    df = pd.DataFrame(
        rows,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "volume_ccy",
            "volume_quote",
            "confirm",
        ],
    )
    df["datetime"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms", utc=True)
    df.set_index("datetime", inplace=True)
    df = df[["open", "high", "low", "close"]].astype(float)
    return df.sort_index()


def get_bybit_data(symbol):
    url = "https://api.bybit.com/v5/market/kline"
    params = {
        "category": "spot",
        "symbol": f"{symbol}USDT",
        "interval": "D",
        "limit": str(DAILY_LIMIT),
    }
    data = safe_get_json(url, params=params)
    rows = data.get("result", {}).get("list") if isinstance(data, dict) else None
    if not rows:
        return None

    df = pd.DataFrame(
        rows,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "turnover",
        ],
    )
    df["datetime"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms", utc=True)
    df.set_index("datetime", inplace=True)
    df = df[["open", "high", "low", "close"]].astype(float)
    return df.sort_index()


def get_coingecko_ohlc_data(coin_id):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    params = {"vs_currency": "usd", "days": "180"}
    data = safe_get_json(url, headers=CG_HEADERS, params=params, retries=1)
    if not data or isinstance(data, dict):
        return None

    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("datetime", inplace=True)
    return df[["open", "high", "low", "close"]].astype(float).sort_index()


def get_waterfall_data(coin_id, symbol):
    for source_name, getter in (
        ("Binance", lambda: get_binance_data(symbol)),
        ("MEXC", lambda: get_mexc_data(symbol)),
        ("KuCoin", lambda: get_kucoin_data(symbol)),
        ("OKX", lambda: get_okx_data(symbol)),
        ("Bybit", lambda: get_bybit_data(symbol)),
        ("CoinGecko OHLC", lambda: get_coingecko_ohlc_data(coin_id)),
    ):
        df = getter()
        if df is not None and len(df) >= 30:
            return df, source_name
    return None, "Failed"


# --- ICT SMC LOGIC & SETUP GRADING ---
def remove_incomplete_period(df, resolution, now_utc):
    if df is None or df.empty:
        return df

    if resolution == "Monthly":
        current_period = now_utc.to_period("M")
        return df[df.index.to_period("M") < current_period]

    if resolution == "Weekly":
        current_period = now_utc.to_period("W-MON")
        return df[df.index.to_period("W-MON") < current_period]

    return df


def resample_ohlc(df_daily, resolution, now_utc):
    rules = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if resolution == "Monthly":
        df = df_daily.resample("ME").agg(rules).dropna()
    elif resolution == "Weekly":
        df = df_daily.resample("W-MON").agg(rules).dropna()
    else:
        raise ValueError(f"Unsupported resolution: {resolution}")

    return remove_incomplete_period(df, resolution, now_utc)


def check_ict_logic(df):
    if df is None or len(df) < 2:
        return False, "Neutral", None, "C-Tier (Ignore)"

    candle = df.iloc[-1]
    prev = df.iloc[-2]

    swept_low = candle["low"] < prev["low"]
    reclaimed_low = candle["close"] > prev["low"]
    swept_high = candle["high"] > prev["high"]
    rejected_high = candle["close"] < prev["high"]

    bullish_sweep = swept_low and reclaimed_low
    bearish_sweep = swept_high and rejected_high

    bullish_displacement = candle["close"] > prev["high"]
    bearish_displacement = candle["close"] < prev["low"]

    midpoint = candle["low"] + ((candle["high"] - candle["low"]) * 0.5)
    valuation = "Discount" if candle["close"] < midpoint else "Premium"

    if bullish_sweep:
        bias = "Bullish Liquidity Sweep"
    elif bullish_displacement:
        bias = "Bullish Displacement"
    elif bearish_sweep:
        bias = "Bearish Liquidity Sweep"
    elif bearish_displacement:
        bias = "Bearish Displacement"
    else:
        return False, "Neutral", valuation, "C-Tier (Ignore)"

    is_bullish = bullish_sweep or bullish_displacement
    is_bearish = bearish_sweep or bearish_displacement

    grade = "C-Tier (Ignore)"
    if is_bullish and valuation == "Discount":
        grade = "A-Tier (Sniper)" if bullish_sweep else "B-Tier (Standard)"
    elif is_bearish and valuation == "Premium":
        grade = "A-Tier (Sniper)" if bearish_sweep else "B-Tier (Standard)"

    return True, bias, valuation, grade


# --- DYNAMIC TAB GENERATION & FP&A FORMATTING ---
def write_to_dynamic_tab(results, tab_name):
    print(f"\nWriting data to tab: {tab_name}...")
    if not SPREADSHEET_ID or not CREDENTIALS_JSON:
        raise RuntimeError("SPREADSHEET_ID and GOOGLE_CREDENTIALS_JSON must be set.")

    creds_dict = json.loads(CREDENTIALS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)

    sh = gc.open_by_key(SPREADSHEET_ID)

    try:
        ws = sh.worksheet(tab_name)
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab_name, rows="300", cols="10", index=0)

    headers = [
        "Timestamp",
        "Ticker",
        "Exchange",
        "Resolution",
        "Price USD",
        "Directional Bias",
        "Valuation",
        "Setup Grade",
    ]
    ws.append_row(headers)

    if results:
        results.sort(key=lambda row: (row[7], row[1]))
        ws.append_rows(results)
    else:
        ws.append_row(["No setups found.", "", "", "", "", "", "", ""])

    ws.freeze(rows=1)
    ws.format(
        "A1:H1",
        {
            "backgroundColor": {"red": 0.1, "green": 0.1, "blue": 0.1},
            "textFormat": {
                "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                "bold": True,
            },
            "horizontalAlignment": "LEFT",
        },
    )
    print(f"Finished {tab_name} with {len(results)} setup rows.")


def should_run(now_pkt):
    is_monthly_run = now_pkt.day == 1
    is_weekly_run = now_pkt.weekday() == 0

    # Manual runs should still produce useful output.
    if not is_monthly_run and not is_weekly_run:
        return True, True
    return is_monthly_run, is_weekly_run


def main():
    now_utc = pd.Timestamp.utcnow()
    now_pkt = now_utc.tz_convert("Asia/Karachi")
    month_yr = now_pkt.strftime("%b%y")
    week_num = ((now_pkt.day - 1) // 7) + 1
    today_str = now_pkt.strftime("%Y-%m-%d")

    is_monthly_run, is_weekly_run = should_run(now_pkt)
    coins = get_top_coins(MONTHLY_COIN_LIMIT)
    monthly_results = []
    weekly_results = []

    print("Starting data extraction...")

    for i, coin in enumerate(coins):
        coin_id = coin["id"]
        symbol = coin["symbol"].upper()
        current_price = float(coin["current_price"])

        time.sleep(1)
        df_daily, source = get_waterfall_data(coin_id, symbol)
        if df_daily is None:
            continue

        if is_monthly_run:
            df_m = resample_ohlc(df_daily, "Monthly", now_utc)
            m_qualified, m_bias, m_val, m_grade = check_ict_logic(df_m)
            if m_qualified:
                monthly_results.append(
                    [today_str, symbol, source, "Monthly", current_price, m_bias, m_val, m_grade]
                )

        if is_weekly_run and i < WEEKLY_COIN_LIMIT:
            df_w = resample_ohlc(df_daily, "Weekly", now_utc)
            w_qualified, w_bias, w_val, w_grade = check_ict_logic(df_w)
            if w_qualified:
                weekly_results.append(
                    [today_str, symbol, source, "Weekly", current_price, w_bias, w_val, w_grade]
                )

    if is_monthly_run:
        write_to_dynamic_tab(monthly_results, f"{month_yr}_Monthly")

    if is_weekly_run:
        write_to_dynamic_tab(weekly_results, f"{month_yr}_W{week_num}")


if __name__ == "__main__":
    main()
