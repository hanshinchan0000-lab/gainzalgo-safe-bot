import os, time, requests, threading
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(msg):
    try:
        if not BOT_TOKEN or not CHAT_ID: return
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Send error: {e}")

def reply_to_user(chat_id, msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        print(f"Replied to {chat_id}")
    except Exception as e:
        print(f"Reply error: {e}")

def get_xau_data():
    # FIXED - NO yf.download = NO 100% bug
    ticker = yf.Ticker("GC=F")
    df = ticker.history(interval="5m", period="2d", auto_adjust=True)
    df = df.dropna()
    if len(df) < 30:
        raise ValueError("Not enough data")
    return df

def gainzalgo_logic(df):
    close = df['Close'].values
    high = df['High'].values
    low = df['Low'].values
    ef = pd.Series(close).ewm(span=21).mean().values
    es = pd.Series(close).ewm(span=50).mean().values
    sma = pd.Series(close).rolling(20).mean().values
    std = pd.Series(close).rolling(20).std().values
    # fix div by zero
    sma_safe = np.where(sma==0, 1, sma)
    bw = (2*std*2) / sma_safe

    c = float(close[-1]); h = float(high[-1]); l = float(low[-1])
    hp = float(high[-2]); lp = float(low[-2])
    ef1 = float(ef[-1]); es1 = float(es[-1])
    bw0 = float(bw[-1]) if not np.isnan(bw[-1]) else 0
    bw1 = float(bw[-2]) if not np.isnan(bw[-2]) else 0
    bw2 = float(bw[-3]) if not np.isnan(bw[-3]) else 0
    lastH = float(np.max(high[-11:-1])); lastL = float(np.min(low[-11:-1]))
    price = c

    trend_down = ef1 < es1
    trend_up = ef1 > es1
    expand = (bw0 > bw1) and (bw1 < bw2) if bw1!=0 and bw2!=0 else False
    sweepH = (h > lastH) and (c < lastH)
    sweepL = (l < lastL) and (c > lastL)
    bosD = c < lp
    bosU = c > hp

    if trend_down and expand and sweepH and bosD:
        return f"🔴 *SELL XAUUSD*\nPrice: {price:.2f}\nSL: {price+3.5:.2f}\nTP1: {price-5:.2f}\nTP2: {price-9:.2f}\nTime: {datetime.now().strftime('%H:%M')} SAFE"
    if trend_up and expand and sweepL and bosU:
        return f"🟢 *BUY XAUUSD*\nPrice: {price:.2f}\nSL: {price-3.5:.2f}\nTP1: {price+5:.2f}\nTP2: {price+9:.2f}\nTime: {datetime.now().strftime('%H:%M')} SAFE"
    return None

def telegram_listener():
    offset=0
    print("Telegram listener started")
    while True:
        try:
            if not BOT_TOKEN:
                time.sleep(10); continue
            url=f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=20"
            r=requests.get(url, timeout=25).json()
            if not r.get("ok"):
                print(f"Telegram API error: {r}"); time.sleep(5); continue
            for u in r.get("result", []):
                offset=u["update_id"]+1
                msg = u.get("message",{})
                txt = msg.get("text","").lower()
                cid = msg.get("chat",{}).get("id")
                print(f"Got msg: {txt} from {cid}")
                if "/start" in txt and cid:
                    reply_to_user(cid,"✅ *BOT 3 FIXED 19:15 ONLINE!* 30sec check ⚡\nPrice tracking live!")
        except Exception as e:
            print(f"Listener error: {e}"); time.sleep(5)

# Auto delete webhook stuck
try:
    if BOT_TOKEN:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=True", timeout=5)
        print(f"Webhook deleted, BOT_TOKEN OK: {bool(BOT_TOKEN)} CHAT_ID OK: {bool(CHAT_ID)}")
except Exception as e:
    print(f"Webhook error: {e}")

threading.Thread(target=telegram_listener, daemon=True).start()
print("BOT 3 GainzAlgo Safe Started - XAUUSD 5m - FIXED 19:15 NO DOWNLOAD")

last=0
while True:
    try:
        df=get_xau_data()
        sig=gainzalgo_logic(df)
        if sig and time.time()-last>600:
            send_telegram(sig); last=time.time(); print(f"Signal sent: {sig[:20]}")
        else:
            print(f"Checking... {float(df['Close'].values[-1]):.2f} No setup - Token OK: {bool(BOT_TOKEN)}")
        time.sleep(30)
    except Exception as e:
        print(f"Error: {e}"); time.sleep(30)
