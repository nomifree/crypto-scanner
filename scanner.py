import os
import time
import json
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
CREDENTIALS_JSON = os.getenv('GOOGLE_CREDENTIALS_JSON')
CG_API_KEY = os.getenv('COINGECKO_API_KEY')

HEADERS = {"accept": "application/json"}
if CG_API_KEY:
    HEADERS["x-cg-demo-api-key"] = CG_API_KEY

def get_top_200_coins():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 200, "page": 1}
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()

def get_daily_data(coin_id):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": "120", "interval": "daily"}
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code == 429:
        time.sleep(30)
        response = requests.get(url, headers=HEADERS, params=params)
    data = response.json()
    if 'prices' not in data: return None
    df = pd.DataFrame(data['prices'], columns=['timestamp', 'price'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    return df

def check_alpha_insights_logic(df):
    if df is None or len(df) < 3: return False, None, None
    
    current_close = df['close'].iloc[-1]
    pC, pH, pL = df['close'].iloc[-2], df['high'].iloc[-2], df['low'].iloc[-2]
    p2H, p2L = df['high'].iloc[-3], df['low'].iloc[-3]

    # Structure Logic
    is_bullish = (pC > p2H) or ((pL < p2L) and (pC > p2L))
    is_bearish = (pC < p2L) or ((pH > p2H) and (pC < p2H))

    # Fibonacci 0.5 Math
    fib_05 = pL + ((pH - pL) * 0.5)
    pricing_text = "DISCOUNT (< 0.5)" if current_close < fib_05 else "PREMIUM (> 0.5)"
    
    bias_text = "BULLISH" if is_bullish else "BEARISH" if is_bearish else "NEUTRAL"
    
    # Trigger if EITHER logic (Bull or Bear) is satisfied
    qualified = is_bullish or is_bearish
    return qualified, bias_text, pricing_text

def main():
    coins = get_top_200_coins()
    results = []
    print("🔍 Starting Dual-Timeframe Scan (PKT 05:15 Schedule)...")
    
    for i, coin in enumerate(coins):
        time.sleep(3) # Stay under free-tier limits
        df_daily = get_daily_data(coin['id'])
        if df_daily is None: continue
        
        # Monthly (Top 200)
        df_m = df_daily['price'].resample('ME').ohlc()
        m_q, m_b, m_p = check_alpha_insights_logic(df_m)
        if m_q:
            results.append([coin['name'], coin['symbol'].upper(), "1M", coin['current_price'], m_b, m_p])
            
        # Weekly (Top 100)
        if i < 100:
            df_w = df_daily['price'].resample('W-MON').ohlc()
            w_q, w_b, w_p = check_alpha_insights_logic(df_w)
            if w_q:
                results.append([coin['name'], coin['symbol'].upper(), "1W", coin['current_price'], w_b, w_p])

    # Standard Write to Sheets Logic here...
    # (Use the same write_to_sheets function from your previous version)
