import os, time, requests, threading
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def reply_to_user(chat_id, msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def get_xau_data():
    # NO MORE yf.download -> NO 100% bug
    ticker = yf.Ticker("GC=F")
    df = ticker.history(interval="5m", period="2d")
    return df.dropna()

def gainzalgo_logic(df):
    if len(df) < 30: return None
    close = df['Close'].values
    high = df['High'].values
    low = df['Low'].values
    ef = pd.Series(close).ewm(span=21).mean().values
    es = pd.Series(close).ewm(span=50).mean().values
    sma = pd.Series(close).rolling(20).mean().values
    std = pd.Series(close).rolling(20).std().values
    bw = ( (sma+2*std) - (sma-2*std) ) / sma

    c = float(close[-1]); h = float(high[-1]); l = float(low[-1])
    hp = float(high[-2]); lp = float(low[-2])
    ef1 = float(ef[-1]); es1 = float(es[-1])
    bw0 = float(bw[-1]); bw1 = float(bw[-2]); bw2 = float(bw[-3])
    lastH = float(np.max(high[-11:-1])); lastL = float(np.min(low[-11:-1]))

    trend_down = ef1 < es1
    trend_up = ef1 > es1
    expand = (bw0 > bw1) and (bw1 < bw2)
    sweepH = (h > lastH) and (c < lastH)
    sweepL = (l < lastL) and (c > lastL)
    bosD = c < lp
    bosU = c > hp
    price = c

    if trend_down and expand and sweepH and bosD:
        return f"🔴 *SELL XAUUSD*\nPrice: {price:.2f}\nSL: {price+3.5:.2f}\nTP1: {price-5:.2f}\nTP2: {price-9:.2f}\nTime: {datetime.now().strftime('%H:%M')} SAFE"
    if trend_up and expand and sweepL and bosU:
        return f"🟢 *BUY XAUUSD*\nPrice: {price:.2f}\nSL: {price-3.5:.2f}\nTP1: {price+5:.2f}\nTP2: {price+9:.2f}\nTime: {datetime.now().strftime('%H:%M')} SAFE"
    return None

def telegram_listener():
    offset=0
    while True:
        try:
            url=f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            r=requests.get(url, timeout=35).json()
            for u in r.get("result", []):
                offset=u["update_id"]+1
                txt=u.get("message",{}).get("text","").lower()
                cid=u.get("message",{}).get("chat",{}).get("id")
                if "/start" in txt: reply_to_user(cid,"✅ BOT 3 FIXED ONLINE! 30sec check ⚡")
        except: time.sleep(5)

threading.Thread(target=telegram_listener, daemon=True).start()
print("BOT 3 GainzAlgo Safe Started - XAUUSD 5m - FIXED NO DOWNLOAD")
last=0
while True:
    try:
        df=get_xau_data()
        sig=gainzalgo_logic(df)
        if sig and time.time()-last>600:
            send_telegram(sig); last=time.time(); print("Signal!")
        else: print(f"Checking... {float(df['Close'].values[-1]):.2f} No setup")
        time.sleep(30)
    except Exception as e:
        print(f"Error: {e}"); time.sleep(30)
