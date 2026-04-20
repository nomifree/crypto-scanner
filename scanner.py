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

def get_monthly_ohlc(coin_id):
    """Fetches 120 days of daily data and converts it to Monthly OHLC."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": "120", "interval": "daily"}
    
    response = requests.get(url, headers=HEADERS, params=params)
    
    # Rate limit protection
    if response.status_code == 429:
        print(f"Rate limited on {coin_id}. Sleeping for 30 seconds...")
        time.sleep(30)
        response = requests.get(url, headers=HEADERS, params=params)
        
    data = response.json()
    if 'prices' not in data or len(data['prices']) == 0:
        return None

    # Pandas Resampling
    df = pd.DataFrame(data['prices'], columns=['timestamp', 'price'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    
    monthly_ohlc = df['price'].resample('ME').ohlc()
    return monthly_ohlc

def check_alpha_insights_logic(df):
    """Applies the Pine Script SMC Logic."""
    if df is None or len(df) < 3:
        return False, "Not enough data"

    current_close = df['close'].iloc[-1]
    
    pC = df['close'].iloc[-2]
    pH = df['high'].iloc[-2]
    pL = df['low'].iloc[-2]
    
    p2H = df['high'].iloc[-3]
    p2L = df['low'].iloc[-3]

    logic1_bull = pC > p2H
    logic2_bull = (pL < p2L) and (pC > p2L)
    is_bullish = logic1_bull or logic2_bull

    eq_05 = (pH + pL) / 2
    is_discount = current_close < eq_05

    bias_text = "BULLISH" if is_bullish else "BEARISH / NEUTRAL"
    pricing_text = "DISCOUNT (< 0.5)" if is_discount else "PREMIUM (> 0.5)"
    
    # Edge Condition: Must be structurally Bullish AND in a Discount
    qualified = is_bullish and is_discount
    
    return qualified, f"{bias_text} | {pricing_text}"

def write_to_sheets(results):
    print("\n📤 Writing to Google Sheets...")
    creds_dict = json.loads(CREDENTIALS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.sheet1
    
    worksheet.clear() 
    
    headers = ["Coin", "Symbol", "Current Price", "Macro Bias & Pricing"]
    worksheet.append_row(headers)
    
    if results:
        worksheet.append_rows(results)
        print(f"✅ Successfully wrote {len(results)} setups to Sheets.")
    else:
        worksheet.append_row(["No qualified setups found this month.", "", "", ""])
        print("✅ No setups found. Wrote empty status to Sheets.")

def main():
    coins = get_top_200_coins()
    qualified_setups = []
    
    print("🔍 Starting Alpha Insights Market Scan...")
    
    for index, coin in enumerate(coins):
        coin_id = coin['id']
        symbol = coin['symbol'].upper()
        current_price = coin['current_price']
        
        # 3-second delay ensures we stay well under the 30 calls/min free limit
        time.sleep(3) 
        
        df = get_monthly_ohlc(coin_id)
        qualified, logic_text = check_alpha_insights_logic(df)
        
        if qualified:
            print(f"🚨 SETUP FOUND: {symbol} -> {logic_text}")
            qualified_setups.append([coin['name'], symbol, current_price, logic_text])
            
        if (index + 1) % 50 == 0:
            print(f"...Scanned {index + 1}/200 coins...")

    write_to_sheets(qualified_setups)

if __name__ == "__main__":
    main()
