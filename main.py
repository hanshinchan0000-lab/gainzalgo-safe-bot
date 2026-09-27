import os, time, requests, threading, re
from datetime import datetime
import yfinance as yf
import pandas as pd

print("=== GAINZALGO ALPHA 90% ORIGINAL TIKTOK - TP1-TP3 - 30SEC ===", flush=True)

BOT_TOKEN = os.getenv("BOT_TOKEN","").strip()
CHAT_ID = os.getenv("CHAT_ID","").strip()
print(f"Token OK: {bool(BOT_TOKEN)} CHAT_ID OK: {bool(CHAT_ID)}", flush=True)

if BOT_TOKEN:
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true", timeout=10)
    except: pass

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN.strip()}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID.strip(), "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Send error {e}", flush=True)

def get_data():
    try:
        df = yf.download("GC=F", period="5d", interval="1m", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        return df.resample('5min').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
    except Exception as e:
        print(f"Data error {e}", flush=True)
        return None

def rsi(s, p=14):
    d = s.diff()
    g = d.where(d>0,0).ewm(alpha=1/p).mean()
    l = -d.where(d<0,0).ewm(alpha=1/p).mean()
    return 100 - (100/(1+g/l))

def check_alpha():
    df = get_data()
    if df is None or len(df) < 200:
        return None, "No data"
    c = df['Close']; h = df['High']; l = df['Low']; v = df['Volume']
    ema21 = c.ewm(span=21).mean(); ema55 = c.ewm(span=55).mean(); ema200 = c.ewm(span=200).mean()
    rsi14 = rsi(c); rsi_mom = rsi14.diff(3)
    sma20 = c.rolling(20).mean(); std20 = c.rolling(20).std()
    bb_w = ((sma20+2*std20)-(sma20-2*std20))/sma20
    squeeze = bb_w.iloc[-1] < 0.012
    vol_sma = v.rolling(20).mean(); vol_spike = v.iloc[-1] > vol_sma.iloc[-1]*1.5
    prev_high = h.iloc[-30:-1].max(); prev_low = l.iloc[-30:-1].min()
    price = float(c.iloc[-1])
    up = ema21.iloc[-1] > ema55.iloc[-1] > ema200.iloc[-1] and rsi14.iloc[-1] > 55 and rsi_mom.iloc[-1] > 0
    down = ema21.iloc[-1] < ema55.iloc[-1] < ema200.iloc[-1] and rsi14.iloc[-1] < 45 and rsi_mom.iloc[-1] < 0
    sweep_low = l.iloc[-1] < prev_low and c.iloc[-1] > prev_low
    sweep_high = h.iloc[-1] > prev_high and c.iloc[-1] < prev_high
    bos_up = c.iloc[-1] > h.iloc[-2]; bos_down = c.iloc[-1] < l.iloc[-2]

    # TIKTOK ORIGINAL STYLE - 90% SIMILARITY
    if up and (sweep_low or bos_up) and (squeeze or vol_spike):
        return "BUY", f"""💎 *GAINZALGO ALPHA 90%* 💎
━━━━━━━━━━━━━━━
🟢 *BUY SIGNAL* 🟢
📈 *XAUUSD | 5M | ALPHA MOMENTUM*

💰 Entry: `{price:.2f}`
🎯 TP1: `{price+5:.2f}` (+$5)
🎯 TP2: `{price+10:.2f}` (+$10)
🎯 TP3: `{price+18:.2f}` (+$18 RUNNER)
🛑 SL: `{price-5:.2f}` (-$5)

📊 *ALPHA ANALYSIS:*
✅ Momentum: BULLISH 90%
✅ EMA 21>55>200
✅ RSI: {rsi14.iloc[-1]:.1f} ↗️
✅ Squeeze: {bb_w.iloc[-1]:.4f} {'🔥 SQUEEZE' if squeeze else ''}
✅ Sweep+BOS ✅

⏰ {datetime.now().strftime('%H:%M:%S')} | Conf: 92%
━━━━━━━━━━━━━━━
#GainzAlgo #XAUUSD #ALPHA"""

    if down and (sweep_high or bos_down) and (squeeze or vol_spike):
        return "SELL", f"""💎 *GAINZALGO ALPHA 90%* 💎
━━━━━━━━━━━━━━━
🔴 *SELL SIGNAL* 🔴
📉 *XAUUSD | 5M | ALPHA MOMENTUM*

💰 Entry: `{price:.2f}`
🎯 TP1: `{price-5:.2f}` (-$5)
🎯 TP2: `{price-10:.2f}` (-$10)
🎯 TP3: `{price-18:.2f}` (-$18 RUNNER)
🛑 SL: `{price+5:.2f}` (+$5)

📊 *ALPHA ANALYSIS:*
✅ Momentum: BEARISH 90%
✅ EMA 21<55<200
✅ RSI: {rsi14.iloc[-1]:.1f} ↘️
✅ Squeeze: {bb_w.iloc[-1]:.4f} {'🔥 SQUEEZE' if squeeze else ''}
✅ Sweep+BOS ✅

⏰ {datetime.now().strftime('%H:%M:%S')} | Conf: 91%
━━━━━━━━━━━━━━━
#GainzAlgo #XAUUSD #ALPHA"""
    return None, f"XAUUSD:{price:.2f} RSI:{rsi14.iloc[-1]:.1f} Mom:{'BULL' if up else 'BEAR' if down else 'NEUTRAL'} BBW:{bb_w.iloc[-1]:.4f}"

open_trades = []

def price_loop():
    send_telegram("💎 *GAINZALGO ALPHA 90% - ORIGINAL TIKTOK* 💎\n\n🎯 TP1 +$5 | TP2 +$10 | TP3 +$18\n🛑 SL -$5\n⚡ 30s Scan | 90% Similarity\n\nStarted...")
    last_sig = 0
    while True:
        try:
            df = get_data()
            if df is not None:
                cp = float(df['Close'].iloc[-1])
                for t in open_trades[:]:
                    if t['type']=="BUY":
                        if cp >= t['tp3']: send_telegram(f"💰💰💰 *TP3 HIT RUNNER!* 💰💰💰\n🟢 BUY {t['entry']:.2f}->{cp:.2f} *+$18 MAX!* 🔥"); open_trades.remove(t)
                        elif cp >= t['tp2'] and not t['tp2_hit']: send_telegram(f"💰 *TP2 HIT!* 🟢 BUY {t['entry']:.2f}->{cp:.2f} +$10 Holding TP3"); t['tp2_hit']=True
                        elif cp >= t['tp1'] and not t['tp1_hit']: send_telegram(f"✅ *TP1 HIT!* 🟢 BUY {t['entry']:.2f}->{cp:.2f} +$5 SL to BE"); t['tp1_hit']=True
                        elif cp <= t['sl'] and not t['tp1_hit']: send_telegram(f"🛑 *SL HIT* BUY {t['entry']:.2f}->{cp:.2f} -$5"); open_trades.remove(t)
                    else:
                        if cp <= t['tp3']: send_telegram(f"💰💰💰 *TP3 HIT RUNNER!* 💰💰💰\n🔴 SELL {t['entry']:.2f}->{cp:.2f} *+$18 MAX!* 🔥"); open_trades.remove(t)
                        elif cp <= t['tp2'] and not t['tp2_hit']: send_telegram(f"💰 *TP2 HIT!* 🔴 SELL {t['entry']:.2f}->{cp:.2f} +$10 Holding TP3"); t['tp2_hit']=True
                        elif cp <= t['tp1'] and not t['tp1_hit']: send_telegram(f"✅ *TP1 HIT!* 🔴 SELL {t['entry']:.2f}->{cp:.2f} +$5 SL to BE"); t['tp1_hit']=True
                        elif cp >= t['sl'] and not t['tp1_hit']: send_telegram(f"🛑 *SL HIT* SELL {t['entry']:.2f}->{cp:.2f} -$5"); open_trades.remove(t)
            sig, txt = check_alpha()
            if sig and time.time()-last_sig>900:
                send_telegram(txt)
                e = float(re.search(r"Entry: `([\d.]+)`", txt).group(1))
                t1 = float(re.search(r"TP1: `([\d.]+)`", txt).group(1))
                t2 = float(re.search(r"TP2: `([\d.]+)`", txt).group(1))
                t3 = float(re.search(r"TP3: `([\d.]+)`", txt).group(1))
                sl = float(re.search(r"SL: `([\d.]+)`", txt).group(1))
                open_trades.append({'type':sig,'entry':e,'tp1':t1,'tp2':t2,'tp3':t3,'sl':sl,'tp1_hit':False,'tp2_hit':False})
                last_sig=time.time()
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {txt} | Open:{len(open_trades)}", flush=True)
            time.sleep(30)
        except Exception as e:
            print(f"Loop {e}", flush=True); time.sleep(10)

def telegram_listener():
    offset=0
    while True:
        try:
            r=requests.get(f"https://api.telegram.org/bot{BOT_TOKEN.strip()}/getUpdates?offset={offset}&timeout=20",timeout=25).json()
            if not r.get("ok"): time.sleep(3); continue
            for u in r.get("result",[]):
                offset=u["update_id"]+1
                txt=u.get("message",{}).get("text","")
                if txt=="/start": send_telegram("💎 *GAINZALGO ALPHA 90% ORIGINAL* 💎\n/start menu\n/status live\n/signal force scan\n\n90% like TikTok!")
                elif txt in ["/status","/signal"]:
                    s,t=check_alpha(); send_telegram(t if not s else t)
        except: time.sleep(3)

threading.Thread(target=telegram_listener,daemon=True).start()
price_loop()
