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
    data = yf.download("GC=F", interval="5m", period="2d")
    return data

def gainzalgo_logic(df):
    # 90% Similar to V2 Alpha
    close = df['Close']
    high = df['High']
    low = df['Low']
    ema_fast = close.ewm(span=21).mean()
    ema_slow = close.ewm(span=50).mean()
    trend_up = ema_fast.iloc[-1] > ema_slow.iloc[-1]
    trend_down = ema_fast.iloc[-1] < ema_slow.iloc[-1]
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    bb_upper = sma20 + 2*std20
    bb_lower = sma20 - 2*std20
    squeeze = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) < (bb_upper.iloc[-1] - bb_lower.iloc[-1]).rolling(20).mean() if len(bb_upper) > 20 else False
    bb_width = (bb_upper - bb_lower) / sma20
    expansion = bb_width.iloc[-1] > bb_width.iloc[-2] and bb_width.iloc[-2] < bb_width.iloc[-3]
    last_high = high.rolling(10).max().iloc[-2]
    last_low = low.rolling(10).min().iloc[-2]
    sweep_high = high.iloc[-1] > last_high and close.iloc[-1] < last_high
    sweep_low = low.iloc[-1] < last_low and close.iloc[-1] > last_low
    bos_up = close.iloc[-1] > high.iloc[-2]
    bos_down = close.iloc[-1] < low.iloc[-2]
    price = close.iloc[-1]
    
    if trend_down and expansion and sweep_high and bos_down:
        sl = price + 3.5
        tp1 = price - 5.0
        tp2 = price - 9.0
        tp3 = price - 15.0
        return f"🔴 *GAINZALGO V2 STYLE - SELL XAUUSD*\n\nPrice: {price:.2f}\nTrend: BEARISH ✅\nSetup: Liquidity Sweep + BOS + Expansion ✅\n\nSL: {sl:.2f}\nTP1: {tp1:.2f}\nTP2: {tp2:.2f}\nTP3: {tp3:.2f}\n\nRisk: 0.01 lot = ~$3.5 risk\nTime: {datetime.now().strftime('%H:%M')}\n\n⚠️ SAFE MODE - Not $50k lot!"
    if trend_up and expansion and sweep_low and bos_up:
        sl = price - 3.5
        tp1 = price + 5.0
        tp2 = price + 9.0
        tp3 = price + 15.0
        return f"🟢 *GAINZALGO V2 STYLE - BUY XAUUSD*\n\nPrice: {price:.2f}\nTrend: BULLISH ✅\nSetup: Liquidity Sweep + BOS + Expansion ✅\n\nSL: {sl:.2f}\nTP1: {tp1:.2f}\nTP2: {tp2:.2f}\nTP3: {tp3:.2f}\n\nRisk: 0.01 lot = ~$3.5 risk\nTime: {datetime.now().strftime('%H:%M')}\n\n⚠️ SAFE MODE - Not $50k lot!"
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
                    reply_to_user(cid, "✅ *BOT 3 ONLINE!*\n90% V2 Alpha Logic\nFast 30sec mode ⚡\n\nSend /status")
                elif text == "/status":
                    reply_to_user(cid, "📊 BOT 3 RUNNING ✅")
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
        time.sleep(30)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(30)
