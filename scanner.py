import os
import time
import json
import requests
import datetime
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
CREDENTIALS_JSON = os.getenv('GOOGLE_CREDENTIALS_JSON')
CG_API_KEY = os.getenv('COINGECKO_API_KEY')

CG_HEADERS = {"accept": "application/json"}
if CG_API_KEY:
    CG_HEADERS["x-cg-demo-api-key"] = CG_API_KEY

def get_top_200_coins():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 200, "page": 1}
    response = requests.get(url, headers=CG_HEADERS, params=params)
    response.raise_for_status()
    return response.json()

# --- WATERFALL DATA (365 DAYS FOR HISTORICAL) ---
def get_binance_data(symbol):
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": f"{symbol}USDT", "interval": "1d", "limit": 365}
    response = requests.get(url, params=params)
    if response.status_code != 200: return None
    data = response.json()
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'tbbav', 'tbqav', 'ignore'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    return df[['open', 'high', 'low', 'close']].astype(float)

def get_mexc_data(symbol):
    url = "https://api.mexc.com/api/v3/klines"
    params = {"symbol": f"{symbol}USDT", "interval": "1d", "limit": 365}
    response = requests.get(url, params=params)
    if response.status_code != 200: return None
    data = response.json()
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    return df[['open', 'high', 'low', 'close']].astype(float)

def get_coingecko_data(coin_id):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": "365", "interval": "daily"}
    response = requests.get(url, headers=CG_HEADERS, params=params)
    data = response.json()
    df = pd.DataFrame(data['prices'], columns=['timestamp', 'price'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    df['open'] = df['high'] = df['low'] = df['close'] = df['price'].astype(float)
    return df[['open', 'high', 'low', 'close']]

def get_waterfall_data(coin_id, symbol):
    df = get_binance_data(symbol)
    if df is not None: return df, "Binance"
    df = get_mexc_data(symbol)
    if df is not None: return df, "MEXC"
    df = get_coingecko_data(coin_id)
    if df is not None: return df, "CoinGecko"
    return None, "Failed"

# --- SMC LOGIC (A/B/C Tiers) ---
def check_ict_logic(df):
    if df is None or len(df) < 3: return False, None, None, None
    current_close = df['close'].iloc[-1]
    pC, pH, pL = df['close'].iloc[-2], df['high'].iloc[-2], df['low'].iloc[-2]
    p2H, p2L = df['high'].iloc[-3], df['low'].iloc[-3]
    
    bullish_sweep = (pL < p2L) and (pC > p2L)
    bearish_sweep = (pH > p2H) and (pC < p2H)
    bullish_disp = pC > p2H
    bearish_disp = pC < p2L
    
    fib_05 = pL + ((pH - pL) * 0.5)
    val = "Discount" if current_close < fib_05 else "Premium"
    
    if bullish_sweep: bias, tier = "Bullish Sweep", ("A-Tier" if val == "Discount" else "C-Tier")
    elif bullish_disp: bias, tier = "Bullish Disp", ("B-Tier" if val == "Discount" else "C-Tier")
    elif bearish_sweep: bias, tier = "Bearish Sweep", ("A-Tier" if val == "Premium" else "C-Tier")
    elif bearish_disp: bias, tier = "Bearish Disp", ("B-Tier" if val == "Premium" else "C-Tier")
    else: return False, None, None, None
    
    return True, bias, val, tier

def write_to_sheet(results, tab_name):
    creds = Credentials.from_service_account_info(json.loads(CREDENTIALS_JSON), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    sh = gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
    try: ws = sh.worksheet(tab_name)
    except: ws = sh.add_worksheet(title=tab_name, rows="300", cols="10")
    ws.clear()
    ws.append_row(["Date", "Ticker", "Exchange", "TF", "Price", "Bias", "Valuation", "Grade"])
    if results: ws.append_rows(results)

def main():
    # FOCUS: February 1st state (Jan and Dec are the triggers)
    target_date = "2026-02-01"
    coins = get_top_200_coins()
    results = []
    
    for coin in coins:
        symbol = coin['symbol'].upper()
        df_daily, src = get_waterfall_data(coin['id'], symbol)
        if df_daily is None: continue
        
        # SLICE: Only see data up to Feb 1
        df_hist = df_daily[df_daily.index <= target_date]
        if len(df_hist) < 60: continue
        
        # Monthly Resample
        df_m = df_hist.resample('ME').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
        found, bias, val, tier = check_ict_logic(df_m)
        if found:
            results.append([target_date, symbol, src, "Monthly", float(coin['current_price']), bias, val, tier])
        time.sleep(0.5)

    write_to_sheet(results, "Feb26_Monthly_Historical")

if __name__ == "__main__":
    main()
