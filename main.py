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
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data = data.dropna()
    return data

def gainzalgo_logic(df):
    if len(df) < 30:
        return None

    close = df['Close']
    high = df['High']
    low = df['Low']
    
    ema_fast = close.ewm(span=21).mean()
    ema_slow = close.ewm(span=50).mean()
    
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    bb_upper = sma20 + 2*std20
    bb_lower = sma20 - 2*std20
    bb_width = (bb_upper - bb_lower) / sma20

    # Use .iloc[-1] as float to fix Series error
    c = float(close.iloc[-1])
    c_prev = float(close.iloc[-2])
    h = float(high.iloc[-1])
    l = float(low.iloc[-1])
    h_prev = float(high.iloc[-2])
    l_prev = float(low.iloc[-2])
    ef = float(ema_fast.iloc[-1])
    es = float(ema_slow.iloc[-1])
    bw = float(bb_width.iloc[-1])
    bw_prev1 = float(bb_width.iloc[-2])
    bw_prev2 = float(bb_width.iloc[-3])

    trend_up = ef > es
    trend_down = ef < es
    
    expansion = bw > bw_prev1 and bw_prev1 < bw_prev2
    
    last_high = float(high.rolling(10).max().iloc[-2])
    last_low = float(low.rolling(10).min().iloc[-2])

    sweep_high = h > last_high and c < last_high
    sweep_low = l < last_low and c > last_low
    bos_up = c > h_prev
    bos_down = c < l_prev

    price = c

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
        return f"🟢 *GAINZALGO V2 STYLE - BUY XAUUSD*\n\nPrice: {price:.2f}\nTrend: BULLISH ✅\nSetup: Liquidity Sweep + BOS + Expansion ✅\n\nSL: {sl:.2f}\nTP1: {tp1:.2f} (safe)\nTP2: {tp2:.2f}\nTP3: {tp3:.2f}\n\nRisk: 0.01 lot = ~$3.5 risk\nTime: {datetime.now().strftime('%H:%M')}\n\n⚠️ SAFE MODE"
    return None

def telegram_listener():
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            r = requests.get(url, timeout=35).json()
            for update in r.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = msg.get("text", "").lower()
                cid = msg.get("chat", {}).get("id")
                if text in ["/start", "start"]:
                    reply_to_user(cid, "✅ *BOT 3 FAST ONLINE!*\n90% V2 Alpha\nChecking every 30sec! ⚡")
                elif text == "/status":
                    reply_to_user(cid, "📊 RUNNING 30sec FAST MODE")
        except:
            time.sleep(5)

threading.Thread(target=telegram_listener, daemon=True).start()

print("BOT 3 GainzAlgo Safe Started - XAUUSD 5m")
last_signal_time = 0
while True:
    try:
        df = get_xau_data()
        signal = gainzalgo_logic(df)
        now = time.time()
        if signal and (now - last_signal_time) > 600:
            send_telegram(signal)
            print(signal)
            last_signal_time = now
        else:
            print(f"Checking... Price {float(df['Close'].iloc[-1]):.2f} - No setup")
        time.sleep(30)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(30)
