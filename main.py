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
    ticker = yf.Ticker("GC=F")
    df = ticker.history(interval="5m", period="2d")
    df = df.dropna()
    print(f"Data shape: {df.shape}, columns: {list(df.columns)}")
    return df

def gainzalgo_logic(df):
    if len(df) < 30:
        print("Not enough data")
        return None
    
    # USE VALUES - NO SERIES BUG EVER
    close_vals = df['Close'].values
    high_vals = df['High'].values
    low_vals = df['Low'].values

    # EMA manual calc to avoid Series
    def ema(values, span):
        return pd.Series(values).ewm(span=span).mean().values

    ema_fast_vals = ema(close_vals, 21)
    ema_slow_vals = ema(close_vals, 50)
    
    sma20 = pd.Series(close_vals).rolling(20).mean().values
    std20 = pd.Series(close_vals).rolling(20).std().values
    bb_upper = sma20 + 2*std20
    bb_lower = sma20 - 2*std20
    bb_width = (bb_upper - bb_lower) / sma20

    c = float(close_vals[-1])
    h = float(high_vals[-1])
    l = float(low_vals[-1])
    h_prev = float(high_vals[-2])
    l_prev = float(low_vals[-2])
    ef = float(ema_fast_vals[-1])
    es = float(ema_slow_vals[-1])
    bw = float(bb_width[-1])
    bw1 = float(bb_width[-2])
    bw2 = float(bb_width[-3])

    # rolling 10 max/min using numpy
    last_high = float(np.max(high_vals[-11:-1]))
    last_low = float(np.min(low_vals[-11:-1]))

    trend_up = ef > es
    trend_down = ef < es
    expansion = (bw > bw1) and (bw1 < bw2)
    sweep_high = (h > last_high) and (c < last_high)
    sweep_low = (l < last_low) and (c > last_low)
    bos_up = c > h_prev
    bos_down = c < l_prev

    print(f"Check: c={c:.2f} ef={ef:.2f} es={es:.2f} trend_down={trend_down} exp={expansion} sweepH={sweep_high} bosD={bos_down}")

    price = c
    if trend_down and expansion and sweep_high and bos_down:
        sl = price + 3.5
        tp1 = price - 5.0
        tp2 = price - 9.0
        tp3 = price - 15.0
        return f"🔴 *GAINZALGO V2 STYLE - SELL
