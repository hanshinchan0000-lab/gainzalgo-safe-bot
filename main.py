import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
import os
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_bbw(series, period=20, std=2):
    sma = series.rolling(period).mean()
    stdev = series.rolling(period).std()
    upper = sma + std*stdev
    lower = sma - std*stdev
    bbw = (upper - lower) / sma
    return bbw

def send_tg(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
        print(f"Sent: {msg}")
    except Exception as e:
        print(f"TG Error: {e}")

print("XAU Bot 3 Started - XAUUSD SPOT ONLY (NOT GC1!)")

while True:
    try:
        # === XAUUSD SPOT ONLY - NOT GC1! ===
        df = yf.download("XAUUSD=X", period="5d", interval="5m", auto_adjust=True, progress=False)
        
        if df.empty or len(df) < 50:
            print("No XAUUSD spot data")
            time.sleep(60)
            continue
        
        close = df['Close']
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:,0]
        
        curr_price = float(close.iloc[-1])
        rsi_series = calc_rsi(close)
        bbw_series = calc_bbw(close)
        
        rsi = float(rsi_series.iloc[-1])
        bbw = float(bbw_series.iloc[-1])
        
        # Sweep + BOS check (simple)
        high_20 = float(close.rolling(20).max().iloc[-2])
        low_10 = float(close.rolling(10).min().iloc[-2])
        sweep = float(df['High'].iloc[-1]) > high_20 if 'High' in df else True
        bos = curr_price < low_10
        
        # CONFIDENCE
        conf = 50
        if 30 <= rsi <= 70: conf += 20
        if bbw > 0.010: conf += 15
        if sweep and bos: conf += 15
        
        print(f"{datetime.now()} XAUUSD SPOT: {curr_price:.2f} RSI:{rsi:.1f} BBW:{bbw:.4f} Conf:{conf}%")

        # === XAUUSD ONLY FILTERS - YOUR FIX ===
        if rsi < 30:
            print(f"SKIP SELL - RSI {rsi:.1f} oversold (like your 19.3 case)")
            time.sleep(300)
            continue
        
        if bbw < 0.010:  # Allow your 0.0108 signal, block tighter
            print(f"SKIP - BBW {bbw:.4f} too tight squeeze")
            time.sleep(300)
            continue

        # SELL SIGNAL
        if sweep and bos and rsi < 70 and conf >= 75:
            msg = f"""🚨 XAUUSD SELL Signal - SPOT

XAUUSD:{curr_price:.2f} RSI:{rsi:.1f} Mom:NEUTRAL BBW:{bbw:.4f}
✅ Sweep+BOS Conf:{conf}%

Feed: XAUUSD=X SPOT (NOT GC1!)
Time: {datetime.now().strftime('%H:%M %d-%m')}
#GainzAlgo #XAUUSD #ALPHA"""
            send_tg(msg)

        time.sleep(300) # check every 5m
        
    except Exception as e:
        print(f"Loop error: {e}")
        time.sleep(60)
