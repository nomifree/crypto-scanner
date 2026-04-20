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
    print("Fetching Top 200 coins...")
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 200,
        "page": 1,
        "sparkline": "false"
    }
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()

def get_daily_data(coin_id):
    """Fetches 120 days of daily data to be mathematically converted later."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": "120", "interval": "daily"}
    
    response = requests.get(url, headers=HEADERS, params=params)
    
    if response.status_code == 429:
        print(f"Rate limited on {coin_id}. Sleeping for 30 seconds...")
        time.sleep(30)
        response = requests.get(url, headers=HEADERS, params=params)
        
    data = response.json()
    if 'prices' not in data or len(data['prices']) == 0:
        return None

    df = pd.DataFrame(data['prices'], columns=['timestamp', 'price'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    
    return df

def check_alpha_insights_logic(df):
    """Applies the Pine Script SMC Logic."""
    if df is None or len(df) < 3:
        return False, None, None

    current_close = df['close'].iloc[-1]
    
    pC = df['close'].iloc[-2]
    pH = df['high'].iloc[-2]
    pL = df['low'].iloc[-2]
    
    p2H = df['high'].iloc[-3]
    p2L = df['low'].iloc[-3]

    # Structural Logic
    logic1_bull = pC > p2H
    logic2_bull = (pL < p2L) and (pC > p2L)
    is_bullish = logic1_bull or logic2_bull

    logic1_bear = pC < p2L
    logic2_bear = (pH > p2H) and (pC < p2H)
    is_bearish = logic1_bear or logic2_bear

    # Strict Fibonacci 0.5 Retracement Math
    # Formula: Swing Low + (Distance from High to Low * 0.5)
    fib_05 = pL + ((pH - pL) * 0.5)
    
    # Pricing Zone
    is_discount = current_close < fib_05

    if is_bullish:
        bias_text = "🟢 BULLISH"
    elif is_bearish:
        bias_text = "🔴 BEARISH"
    else:
        bias_text = "⚪ NEUTRAL"

    pricing_text = "🟢 DISCOUNT (< 0.5)" if is_discount else "🔴 PREMIUM (> 0.5)"
    
    # NEW RULE: If it has ANY valid structure (Bullish OR Bearish), flag it. 
    # Ignore whether it is Premium or Discount for the filter, leave that to the user.
    qualified = is_bullish or is_bearish
    
    return qualified, bias_text, pricing_text

def write_to_sheets(results):
    print("\n📤 Writing to Google Sheets...")
    creds_dict = json.loads(CREDENTIALS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.sheet1
    
    worksheet.clear() 
    
    # Upgraded Headers
    headers = ["Coin", "Symbol", "Timeframe", "Current Price", "Market Structure", "Fib Pricing Zone"]
    worksheet.append_row(headers)
    
    if results:
        worksheet.append_rows(results)
        print(f"✅ Successfully wrote {len(results)} setups to Sheets.")
    else:
        worksheet.append_row(["No setups found.", "", "", "", "", ""])

def main():
    coins = get_top_200_coins()
    qualified_setups = []
    
    print("🔍 Starting Multi-Timeframe SMC Scan...")
    
    for index, coin in enumerate(coins):
        coin_id = coin['id']
        symbol = coin['symbol'].upper()
        current_price = coin['current_price']
        
        time.sleep(3) # API protection
        
        df_daily = get_daily_data(coin_id)
        if df_daily is None:
            continue
            
        # 1. MONTHLY SCAN (Top 200 - All Coins)
        df_monthly = df_daily['price'].resample('ME').ohlc()
        m_qual, m_bias, m_price = check_alpha_insights_logic(df_monthly)
        
        if m_qual:
            print(f"🚨 MONTHLY SETUP: {symbol} -> {m_bias} | {m_price}")
            qualified_setups.append([coin['name'], symbol, "1M", current_price, m_bias, m_price])
            
        # 2. WEEKLY SCAN (Top 100 Only)
        if index < 100:
            df_weekly = df_daily['price'].resample('W-MON').ohlc() # Weekly starting on Monday
            w_qual, w_bias, w_price = check_alpha_insights_logic(df_weekly)
            
            if w_qual:
                print(f"🚨 WEEKLY SETUP: {symbol} -> {w_bias} | {w_price}")
                qualified_setups.append([coin['name'], symbol, "1W", current_price, w_bias, w_price])
            
        if (index + 1) % 50 == 0:
            print(f"...Scanned {index + 1}/200 coins...")

    write_to_sheets(qualified_setups)

if __name__ == "__main__":
    main()
