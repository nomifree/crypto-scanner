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
    print("Fetching Top 200 list from CoinGecko...")
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 200, "page": 1}
    response = requests.get(url, headers=CG_HEADERS, params=params)
    response.raise_for_status()
    return response.json()

# --- WATERFALL DATA SOURCES (GLOBAL ENDPOINTS) ---
def get_binance_data(symbol):
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": f"{symbol}USDT", "interval": "1d", "limit": 120}
    response = requests.get(url, params=params)
    if response.status_code != 200: return None
    data = response.json()
    if not data or isinstance(data, dict): return None
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'tbbav', 'tbqav', 'ignore'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    return df[['open', 'high', 'low', 'close']].astype(float)

def get_mexc_data(symbol):
    url = "https://api.mexc.com/api/v3/klines"
    params = {"symbol": f"{symbol}USDT", "interval": "1d", "limit": 120}
    response = requests.get(url, params=params)
    if response.status_code != 200: return None
    data = response.json()
    if not data or isinstance(data, dict): return None
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    return df[['open', 'high', 'low', 'close']].astype(float)

def get_coingecko_data(coin_id):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": "120", "interval": "daily"}
    response = requests.get(url, headers=CG_HEADERS, params=params)
    if response.status_code == 429:
        time.sleep(30)
        response = requests.get(url, headers=CG_HEADERS, params=params)
    data = response.json()
    if 'prices' not in data or len(data['prices']) == 0: return None
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

# --- ICT SMC LOGIC & SETUP GRADING ---
def check_ict_logic(df):
    if df is None or len(df) < 3: return False, None, None, None

    current_close = df['close'].iloc[-1]
    pC, pH, pL = df['close'].iloc[-2], df['high'].iloc[-2], df['low'].iloc[-2]
    p2H, p2L = df['high'].iloc[-3], df['low'].iloc[-3]

    bullish_sweep = (pL < p2L) and (pC > p2L)
    bearish_sweep = (pH > p2H) and (pC < p2H)
    bullish_disp = pC > p2H
    bearish_disp = pC < p2L

    is_bullish = bullish_sweep or bullish_disp
    is_bearish = bearish_sweep or bearish_disp

    fib_05 = pL + ((pH - pL) * 0.5)
    valuation = "Discount" if current_close < fib_05 else "Premium"

    if bullish_sweep: bias = "Bullish Sweep"
    elif bullish_disp: bias = "Bullish Displacement"
    elif bearish_sweep: bias = "Bearish Sweep"
    elif bearish_disp: bias = "Bearish Displacement"
    else: bias = "Neutral"

    # Strict Institutional Grading System
    grade = "C-Tier (Ignore)"
    if is_bullish and valuation == "Discount":
        grade = "A-Tier (Sniper)" if bullish_sweep else "B-Tier (Standard)"
    elif is_bearish and valuation == "Premium":
        grade = "A-Tier (Sniper)" if bearish_sweep else "B-Tier (Standard)"

    return (is_bullish or is_bearish), bias, valuation, grade

# --- DYNAMIC TAB GENERATION & FP&A FORMATTING ---
def write_to_dynamic_tab(results, tab_name):
    print(f"\n📤 Writing data to new tab: {tab_name}...")
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
    
    # Updated Headers with Setup Grade
    headers = ["Timestamp", "Ticker", "Exchange", "Resolution", "Price USD", "Directional Bias", "Valuation", "Setup Grade"]
    ws.append_row(headers)
    
    if results:
        results.sort(key=lambda x: x[1])
        ws.append_rows(results)
        
        ws.freeze(rows=1)
        ws.format('A1:H1', {
            "backgroundColor": {"red": 0.1, "green": 0.1, "blue": 0.1},
            "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "bold": True},
            "horizontalAlignment": "LEFT"
        })
        print(f"✅ Created {tab_name} with {len(results)} rows.")
    else:
        ws.append_row(["No setups found.", "", "", "", "", "", "", ""])

def main():
    # Sync time to Pakistan Standard Time (PKT)
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=5)
    month_yr = now.strftime("%b%y") 
    week_num = (now.day - 1) // 7 + 1
    today_str = now.strftime("%Y-%m-%d")
    
    is_monthly_run = (now.day == 1)
    is_weekly_run = (now.weekday() == 0) # 0 = Monday
    
    if not is_monthly_run and not is_weekly_run:
        is_monthly_run = True
        is_weekly_run = True

    coins = get_top_200_coins()
    monthly_results = []
    weekly_results = []
    
    print("🔍 Starting Data Extraction...")
    agg_rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
    
    for i, coin in enumerate(coins):
        coin_id = coin['id']
        symbol = coin['symbol'].upper()
        current_price = float(coin['current_price'])
        
        time.sleep(1) 
        df_daily, source = get_waterfall_data(coin_id, symbol)
        if df_daily is None: continue
            
        if is_monthly_run:
            df_m = df_daily.resample('ME').agg(agg_rules).dropna()
            m_q, m_b, m_val, m_grade = check_ict_logic(df_m)
            if m_q:
                monthly_results.append([today_str, symbol, source, "Monthly", current_price, m_b, m_val, m_grade])
                
        if is_weekly_run and i < 100:
            df_w = df_daily.resample('W-MON').agg(agg_rules).dropna()
            w_q, w_b, w_val, w_grade = check_ict_logic(df_w)
            if w_q:
                weekly_results.append([today_str, symbol, source, "Weekly", current_price, w_b, w_val, w_grade])

    if is_monthly_run:
        tab_name = f"{month_yr}_Monthly"
        write_to_dynamic_tab(monthly_results, tab_name)
        
    if is_weekly_run:
        tab_name = f"{month_yr}_W{week_num}"
        write_to_dynamic_tab(weekly_results, tab_name)

if __name__ == "__main__":
    main()
