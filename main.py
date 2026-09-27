import os, time, requests, threading
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

def reply_to_user(chat_id, msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})

def get_xau_data():
    data = yf.download("GC=F", interval="5m", period="2d", progress=False)
    # FIX for yfinance MultiIndex bug
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

def gainzalgo_logic(df):
    # 90% Similar to V2 Alpha - SAME LOGIC
    if len(df) < 30:
        return None
        
    close = df['Close']
    high = df['High']
    low = df['Low']
    
    ema_fast = close.ewm(span=21).mean()
    ema_slow = close.ewm(span=50).mean()
    
    trend_up = float(ema_fast.iloc[-1]) > float(ema_slow.iloc[-1])
    trend_down = float(ema_fast.iloc[-1]) < float(ema_slow.iloc[-1])
    
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    bb_upper = sma20 + 2*std20
    bb_lower = sma20 - 2*std20
    
    # FIXED: squeeze calculation
    bb_width = (bb_upper - bb_lower) / sma20
    # old buggy line removed
    
    expansion = float(bb_width.iloc[-1]) > float(bb_width.iloc[-2]) and float(bb_width.iloc[-2]) < float(bb_width.iloc[-3])
    
    last_high = float(high.rolling(10).max().iloc[-2])
    last_low = float(low.rolling(10).min().iloc[-2])
    
    curr_high = float(high.iloc[-1])
    curr_low = float(low.iloc[-1])
    curr_close = float(close.iloc[-1])
    prev_high = float(high.iloc[-2])
    prev_low = float(low.iloc[-2])
    
    sweep_high = curr_high > last_high and curr_close < last_high
    sweep_low = curr_low < last_low and curr_close > last_low
    bos_up = curr_close > prev_high
    bos_down = curr_close < prev_low
    price = curr_close
    
    if trend_down and expansion and sweep_high and bos_down:
        sl = price + 3.5
        tp1 = price - 5.0
        tp2 = price - 9.0
        tp3 = price - 15.0
        return f"🔴 *GAINZALGO V2 STYLE - SELL XAUUSD*\n\nPrice: {price:.2f}\nTrend: BEARISH ✅\nSetup: Liquidity Sweep + BOS + Expansion ✅\n\nSL: {sl:.2f}\nTP1: {tp1:.2f} (safe)\nTP2: {tp2:.2f}\nTP3: {tp3:.2f}\n\nRisk: 0.01 lot = ~$3.5 risk\nTime: {datetime.now().strftime('%H:%M')}\n\n⚠️ SAFE MODE"
    
    if trend_up and expansion and sweep_low and bos_up:
        sl = price - 3.5
        tp1 = price + 5.0
        tp2 = price + 9.0
        tp3 = price + 15.0
        return f"🟢 *GAINZALGO V2 STYLE - BUY XAUUSD*\n\nPrice: {price:.2f}\nTrend: BULLISH ✅\nSetup: Liquidity Sweep + BOS + Expansion ✅\n\nSL: {sl:.2f
