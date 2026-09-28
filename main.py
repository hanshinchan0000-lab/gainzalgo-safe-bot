from flask import Flask
import threading, time, requests, os
import pandas as pd
import yfinance as yf

app = Flask(__name__)

# ========== CONFIG - REAL GOLD ONANA ==========
SYMBOL = "XAUUSD"
YF_SYMBOL = "GC=F" # for data, proxy for XAUUSD spot
TF = "15m" # use 15m for REAL setup, not noisy 1m
LIVE = True
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

EMA_FAST = 50
EMA_SLOW = 200
ADX_MIN = 22
COOLDOWN = 45*60 # 45 min no spam - ONLY REAL SETUP
last_signal_time = 0
active_trade = None
last_price = 0

# ========== HEALTH FOR UPTIMEROBOT ==========
@app.route('/')
def home():
    return f"✅ GAINZALGO {SYMBOL} LIVE - FVG+OB+RETEST - Price:{last_price}", 200

@app.route('/health')
def health(): return "OK", 200

# ========== DATA ==========
def get_candles():
    global last_price
    try:
        df = yf.download(YF_SYMBOL, period="5d", interval="15m", progress=False)
        df = df.dropna()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        # EMA
        df['EMA50'] = df['Close'].ewm(span=EMA_FAST).mean()
        df['EMA200'] = df['Close'].ewm(span=EMA_SLOW).mean()
        # ADX simple filter using EMA distance
        df['trend_strength'] = abs(df['EMA50'] - df['EMA200'])
        last_price = float(df['Close'].iloc[-1])
        return df
    except Exception as e:
        print(f"Data error: {e}")
        return None

# ========== SMC LOGIC ==========
def find_bullish_fvg(df):
    # FVG: candle1 high < candle3 low and middle is gap
    fvg_zones = []
    for i in range(2, len(df)-1):
        c1_high = df['High'].iloc[i-2]
        c3_low = df['Low'].iloc[i]
        c2 = df.iloc[i-1]
        if c1_high < c3_low and (c3_low - c1_high) > 1.5: # $1.5 gap min
            fvg_zones.append((float(c1_high), float(c3_low), i))
    return fvg_zones[-3:] if fvg_zones else []

def find_bullish_ob(df):
    # OB: last bearish candle before big bullish impulse
    obs = []
    for i in range(1, len(df)-2):
        # bearish then bullish impulse > $3
        if df['Close'].iloc[i] < df['Open'].iloc[i] and df['Close'].iloc[i+1] - df['Open'].iloc[i+1] > 3:
            ob_high = float(df['High'].iloc[i])
            ob_low = float(df['Low'].iloc[i])
            obs.append((ob_low, ob_high, i))
    return obs[-3:] if obs else []

def find_demand_zone(df):
    # Support/Demand: swing low with rejection
    demand = []
    for i in range(2, len(df)-2):
        low = df['Low'].iloc[i]
        if low < df['Low'].iloc[i-1] and low < df['Low'].iloc[i-2] and low < df['Low'].iloc[i+1] and low < df['Low'].iloc[i+2]:
            demand.append((float(low-1), float(low+2), i))
    return demand[-2:] if demand else []

def check_rejection_confirmation(df):
    # Rejection: hammer / bullish engulfing / wick rejection at zone
    last = df.iloc[-1]
    prev = df.iloc[-2]
    body = abs(last['Close'] - last['Open'])
    lower_wick = min(last['Open'], last['Close']) - last['Low']
    # 1. Hammer rejection
    hammer = lower_wick > body*1.8 and last['Close'] > last['Open']
    # 2. Bullish engulfing
    engulf = last['Close'] > prev['Open'] and last['Open'] < prev['Close'] and last['Close'] > prev['High']
    # 3. Wick rejection
    wick_rej = last['Low'] < prev['Low'] and last['Close'] > (last['High']+last['Low'])/2
    return hammer or engulf or wick_rej

# ========== TELEGRAM ==========
def send_tg(msg):
    try:
        if not BOT_TOKEN: return
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        print(f"Sent: {msg[:100]}")
    except Exception as e: print(e)

# ========== MAIN BOT LOGIC - LONG ONLY REAL SETUP ==========
def check_long_setup():
    global last_signal_time, active_trade
    df = get_candles()
    if df is None or len(df) < 210: return

    price = float(df['Close'].iloc[-1])
    ema50 = float(df['EMA50'].iloc[-1])
    ema200 = float(df['EMA200'].iloc[-1])
    trend_strength = float(df['trend_strength'].iloc[-1])

    # --- FILTERS - NO NOISE ---
    if time.time() - last_signal_time < COOLDOWN: return
    if price < ema200: return # ONLY LONG ABOVE EMA200
    if price < ema50: return
    if trend_strength < 2.0: return # weak trend filter (proxy ADX)
    if active_trade:
        check_tp_sl_hit(price)
        return

    fvg_zones = find_bullish_fvg(df)
    ob_zones = find_bullish_ob(df)
    demand_zones = find_demand_zone(df)

    # Check if price is retesting a zone NOW
    in_zone = False
    zone_type = ""
    zone_low = zone_high = 0

    for low, high, idx in fvg_zones + ob_zones + demand_zones:
        # Price retesting zone (within 0.5$)
        if low-0.5 <= price <= high+0.5:
            in_zone = True
            zone_low, zone_high = low, high
            if (low, high, idx) in fvg_zones: zone_type = "BULLISH FVG"
            elif (low, high, idx) in ob_zones: zone_type = "BULLISH OB"
            else: zone_type = "DEMAND ZONE"
            break

    if not in_zone: return

    # --- CONFIRMATION: REJECTION + RETEST ---
    if not check_rejection_confirmation(df): return # NEED rejection!

    # --- REAL SETUP FOUND - LONG ---
    entry = price
    sl = zone_low - 2.5 # SL below zone + $2.5 buffer
    risk = entry - sl
    if risk < 1.5 or risk > 8: return # risk filter no noise

    tp1 = entry + risk*1.0
    tp2 = entry + risk*2.0
    tp3 = entry + risk*3.5

    msg = f"""🚀 *GAINZALGO REAL LONG SETUP FOUND* - {SYMBOL} LIVE

✅ *{zone_type} + RETEST + REJECTION CONFIRMED*

📍 ENTRY: {entry:.2f} GOLD ONANA SPOT LIVE
🛑 SL: {sl:.2f} (-${risk:.2f})
🎯 TP1: {tp1:.2f} (1:1)
🎯 TP2: {tp2:.2f} (1:2)
🎯 TP3: {tp3:.2f} (1:3.5)

📊 Zone: {zone_low:.2f} - {zone_high:.2f}
EMA50: {ema50:.2f} | EMA200: {ema200:.2f}
TF: {TF} | No noisy - Real setup only!

BOT: gainzalgo LIVE + UptimeRobot
"""
    send_tg(msg)
    last_signal_time = time.time()
    active_trade = {"entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3, "type": zone_type}

def check_tp_sl_hit(price):
    global active_trade
    if not active_trade: return
    sl, tp1, tp2, tp3 = active_trade['sl'], active_trade['tp1'], active_trade['tp2'], active_trade['tp3']

    if price <= sl:
        send_tg(f"❌ *SL HIT* {SYMBOL}\nEntry: {active_trade['entry']:.2f} -> SL: {sl:.2f}\nSetup: {active_trade['type']}")
        active_trade = None
    elif price >= tp1 and
