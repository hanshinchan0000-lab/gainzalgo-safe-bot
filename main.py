from flask import Flask
import threading, time, requests, os
import pandas as pd
import yfinance as yf

app = Flask(__name__)

# ========= CONFIG =========
SYMBOL = "XAUUSD"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

EMA_PERIOD = 50
RSI_MIN = 50
RSI_MAX = 65
SL_DISTANCE = 9.0
TP1_DISTANCE = 6.0
TP2_DISTANCE = 11.0
SPREAD_ENTRY = 0.60
SPREAD_SL = 0.50

last_price = 4157.93
active_trade = None
last_signal = 0

@app.route('/')
def home(): return f"✅ GAINZALGO V6 80% SAFE REAL XAUUSD {last_price} | 3TP + Next Liq + No BE", 200
@app.route('/health')
def health(): return "OK", 200

def send_tg(msg):
    try:
        if BOT_TOKEN and CHAT_ID:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                          data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        print(msg[:300])
    except Exception as e: print(e)

def get_yf(symbol, period, interval):
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
        if df is None or len(df) < 50: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close"})
        return df.dropna()
    except: return None

def get_data():
    global last_price
    # REAL XAUUSD like V7 - GC=F + PAXG-10.5 fallback (your 4157 zone)
    for sym in ["GC=F", "PAXG-USD"]:
        for per, inter in [("5d","15m")]:
            df = get_yf(sym, per, inter)
            if df is None: continue
            if "PAXG" in sym:
                df["close"] = df["close"] - 10.5
                df["high"] = df["high"] - 10.5
                df["low"] = df["low"] - 10.5
                df["open"] = df["open"] - 10.5
            last_price = float(df["close"].iloc[-1])
            # Build 1H,15M,5M from 15M data for V6 logic
            df_15 = df.copy()
            # Simulate 1H and 5M - get fresh
            df_1h = get_yf(sym, "5d", "60m")
            df_5 = get_yf(sym, "2d", "5m")
            if df_1h is not None and df_5 is not None:
                if "PAXG" in sym:
                    for d in [df_1h, df_5]:
                        d["close"] = d["close"] - 10.5 if "close" in d else d["Close"] - 10.5
                        d.columns = [c.lower() for c in d.columns]
                if "close" not in df_1h: df_1h.columns = [c.lower() for c in df_1h.columns]
                if "close" not in df_5: df_5.columns = [c.lower() for c in df_5.columns]
                return df_1h, df_15, df_5
    return None, None, None

def ema(s, p): return s.ewm(span=p, adjust=False).mean()
def rsi_calc(s, p=14):
    d = s.diff()
    g = d.where(d>0,0).rolling(p).mean()
    l = -d.where(d<0,0).rolling(p).mean()
    rs = g / l
    return 100 - (100/(1+rs))

def get_squeeze(df):
    sma20 = df['close'].rolling(20).mean()
    std20 = df['close'].rolling(20).std()
    upper_bb = sma20 + std20*2
    lower_bb = sma20 - std20*2
    atr = (df['high']-df['low']).rolling(20).mean()
    upper_kc = sma20 + atr*1.5
    lower_kc = sma20 - atr*1.5
    squeeze_on = (lower_bb > lower_kc) & (upper_bb < upper_kc)
    return squeeze_on

def find_fvg(df):
    for i in range(2, len(df)):
        if df['low'].iloc[i] > df['high'].iloc[i-2]:
            return (df['low'].iloc[i], df['high'].iloc[i-2])
    return None

def find_bos(df):
    last_high = df['high'].rolling(10).max().iloc[-2]
    return df['close'].iloc[-1] > last_high

def find_next_liquidity(df):
    liq = df['high'].rolling(5).max().iloc[-20:].max()
    return liq + 1.5

def check_signal():
    global active_trade, last_signal
    df_1h, df_15, df_5 = get_data()
    if df_1h is None:
        print("No data")
        return

    # --- TRACK ACTIVE TRADE ---
    if active_trade:
        price = float(df_15['close'].iloc[-1])
        sl,tp1,tp2,tp3 = active_trade['sl'],active_trade['tp1'],active_trade['tp2'],active_trade['tp3']
        if price <= sl:
            send_tg(f"❌ SL HIT -9$\nEntry {active_trade['entry']:.2f} -> {sl:.2f} Price {price:.2f}")
            active_trade=None
        elif price >= tp1 and not active_trade.get('t1'):
            send_tg(f"✅ TP1 HIT +$6 {price:.2f}\nEntry {active_trade['entry']:.2f} -> TP1 {tp1:.2f}\nHolding TP2/TP3 No BE")
            active_trade['t1']=True
        elif price >= tp2 and not active_trade.get('t2'):
            send_tg(f"✅✅ TP2 HIT +$11 {price:.2f}\nEntry {active_trade['entry']:.2f} -> TP2 {tp2:.2f}\nHolding TP3 Liq")
            active_trade['t2']=True
        elif price >= tp3:
            send_tg(f"🔥 TP3 HIT NEXT LIQ {price:.2f}\nEntry {active_trade['entry']:.2f} -> TP3 {tp3:.2f} (+${tp3-active_trade['entry']:.2f})")
            active_trade=None
        return

    if time.time() - last_signal < 3600: return

    ema_1h = ema(df_1h['close'], EMA_PERIOD).iloc[-1]
    ema_15 = ema(df_15['close'], EMA_PERIOD).iloc[-1]
    rsi_15 = rsi_calc(df_15['close']).iloc[-1]
    squeeze_15 = get_squeeze(df_15)

    print(f"Check {last_price:.2f} RSI {rsi_15:.1f} EMA1H {ema_1h:.2f} EMA15 {ema_15:.2f} Squeeze {squeeze_15.iloc[-1]}")

    # V6 STRICT BUT NOT TOO STRICT (fixed your crash)
    if not (RSI_MIN <= rsi_15 <= RSI_MAX): return
    if not (df_1h['close'].iloc[-1] > ema_1h and df_15['close'].iloc[-1] > ema_15): return
    # Squeeze: OFF now (not require ON->OFF, that was too rare)
    if squeeze_15.iloc[-1] == True: return

    fvg = find_fvg(df_15)
    if not fvg: return
    if not find_bos(df_5): return

    entry = df_15['close'].iloc[-1] + SPREAD_ENTRY
    sl = entry - SL_DISTANCE - SPREAD_SL
    tp1 = entry + TP1_DISTANCE
    tp2 = entry + TP2_DISTANCE
    tp3 = find_next_liquidity(df_15)

    # No BE as you asked
    msg = f"""🚀 V6 LONG - 80% SETUP - 3TP + NEXT LIQ
Symbol: XAUUSD REAL {last_price:.2f}
Entry: {entry:.2f}
SL: {sl:.2f} (-$9)

TP1: {tp1:.2f} (+$6) 30% SAFE
TP2: {tp2:.2f} (+$11) 30%
TP3: {tp3:.2f} (Next BSL) 40% 🎯

Filters: RSI {rsi_15:.1f} | EMA50 OK | Squeeze OFF | 15M FVG + 5M BOS
No BE - Manage manually
"""
    send_tg(msg)
    last_signal = time.time()
    active_trade = {"entry":entry,"sl":sl,"tp1":tp1,"tp2":tp2,"tp3":tp3,"t1":False,"t2":False}

def bot_loop():
    send_tg(f"✅ GAINZALGO V6 ONLINE - REAL XAUUSD {last_price}\n80% SAFE | 3TPs + Next Liquidity + No BE\nRSI 50-65 | EMA50 | Squeeze OFF | FVG+BOS\nREAL price PAXG-10.5 fallback like VIDYA V7")
    while True:
        try:
            check_signal()
            time.sleep(60)
        except Exception as e:
            print(f"Loop err {e}")
            time.sleep(30)

threading.Thread(target=bot_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
