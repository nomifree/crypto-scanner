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

# --- WATERFALL DATA SOURCES (NO API KEYS REQUIRED) ---

def get_binance_data(symbol):
    """Tier 1: Binance Raw Order Book"""
    url = "https://api.binance.com/api/v3/klines"
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
    """Tier 2: MEXC Raw Order Book"""
    url = "https://api.mexc.com/api/v3/klines"
    params = {"symbol": f"{symbol}USDT", "interval": "1d", "limit": 120}
    response = requests.get(url, params=params)
    if response.status_code != 200: return None
        
    data = response.json()
    if not data or isinstance(data, dict): return None
        
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    df.set_index('datetime', inplace=True)
    return df[['open', 'high', 'low', 'close']].astype(float)

def get_coingecko_data(coin_id):
    """Tier 3: CoinGecko Aggregated Fallback"""
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
    
    df['open'] = df['price'].astype(float)
    df['high'] = df['price'].astype(float)
    df['low'] = df['price'].astype(float)
    df['close'] = df['price'].astype(float)
    return df[['open', 'high', 'low', 'close']]

def get_waterfall_data(coin_id, symbol):
    """Attempts Binance -> MEXC -> CoinGecko"""
    df = get_binance_data(symbol)
    if df is not None: return df, "Binance"
        
    df = get_mexc_data(symbol)
    if df is not None: return df, "MEXC"
        
    df = get_coingecko_data(coin_id)
    if df is not None: return df, "CoinGecko"
        
    return None, "Failed"

# --- ICT SMC LOGIC ---

def check_ict_logic(df):
    if df is None or len(df) < 3: return False, None, None

    current_close = df['close'].iloc[-1]
    
    pC, pH, pL = df['close'].iloc[-2], df['high'].iloc[-2], df['low'].iloc[-2]
    p2H, p2L = df['high'].iloc[-3], df['low'].iloc[-3]

    # 1. SWEEPS (Failure to Displace)
    bullish_sweep = (pL < p2L) and (pC > p2L)
    bearish_sweep = (pH > p2H) and (pC < p2H)

    # 2. DISPLACEMENTS (Structure Shift)
    bullish_disp = pC > p2H
    bearish_disp = pC < p2L

    is_bullish = bullish_sweep or bullish_disp
    is_bearish = bearish_sweep or bearish_disp

    # 3. FIBONACCI 0.5 EQUILIBRIUM
    fib_05 = pL + ((pH - pL) * 0.5)
    pricing_text = "🟢 DISCOUNT (< 0.5)" if current_close < fib_05 else "🔴 PREMIUM (> 0.5)"

    if bullish_sweep: bias_text = "🟢 BULLISH (Sweep Trap)"
    elif bullish_disp: bias_text = "🟢 BULLISH (Displacement)"
    elif bearish_sweep: bias_text = "🔴 BEARISH (Sweep Trap)"
    elif bearish_disp: bias_text = "🔴 BEARISH (Displacement)"
    else: bias_text = "⚪ NEUTRAL / CHOP"

    qualified = is_bullish or is_bearish
    return qualified, bias_text, pricing_text

# --- SYSTEM EXECUTION & FP&A FORMATTING ---

def write_to_sheets(results):
    print("\n📤 Formatting and Writing to Google Sheets...")
    creds_dict = json.loads(CREDENTIALS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.sheet1
    worksheet.clear() 
    
    headers = ["Coin", "Symbol", "Source", "Timeframe", "Current Price ($)", "Market Structure", "Fib Pricing Zone"]
    worksheet.append_row(headers)
    
    if results:
        # Sort results: First by Timeframe (1M then 1W), then alphabetically by Symbol
        results.sort(key=lambda x: (x[3], x[1]))
        worksheet.append_rows(results)
        
        # Apply Clean FP&A Formatting
        worksheet.freeze(rows=1)
        worksheet.format('A1:G1', {
            "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2},
            "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "bold": True},
            "horizontalAlignment": "CENTER"
        })
        
        total_rows = len(results) + 1
        worksheet.format(f'A2:G{total_rows}', {"horizontalAlignment": "CENTER"})
        
        print(f"✅ Successfully wrote and formatted {len(results)} setups in Sheets.")
    else:
        worksheet.append_row(["No setups found.", "", "", "", "", "", ""])

def main():
    coins = get_top_200_coins()
    results = []
    
    print("🔍 Starting Waterfall SMC Scan (Binance -> MEXC -> CoinGecko)...")
    
    agg_rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
    
    for i, coin in enumerate(coins):
        coin_id = coin['id']
        symbol = coin['symbol'].upper()
        
        time.sleep(1) # Gentle buffer for API safety
        
        df_daily, source = get_waterfall_data(coin_id, symbol)
        
        if df_daily is None: continue
            
        # Monthly Scan (Top 200)
        df_m = df_daily.resample('ME').agg(agg_rules).dropna()
        m_q, m_b, m_p = check_ict_logic(df_m)
        if m_q:
            results.append([coin['name'], symbol, source, "1M", coin['current_price'], m_b, m_p])
            print(f"🚨 1M SETUP: {symbol} -> {m_b} | {m_p}")
            
        # Weekly Scan (Top 100)
        if i < 100:
            df_w = df_daily.resample('W-MON').agg(agg_rules).dropna()
            w_q, w_b, w_p = check_ict_logic(df_w)
            if w_q:
                results.append([coin['name'], symbol, source, "1W", coin['current_price'], w_b, w_p])
                print(f"🚨 1W SETUP: {symbol} -> {w_b} | {w_p}")
                
        if (i + 1) % 50 == 0:
            print(f"...Scanned {i + 1}/200 coins...")

    write_to_sheets(results)

if __name__ == "__main__":
    main()
