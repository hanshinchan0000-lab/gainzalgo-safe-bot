import time
import requests
import pandas as pd
import numpy as np

# ========= CONFIG =========
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"
SYMBOL = "XAUUSD"
TIMEFRAME_15 = "M15"
TIMEFRAME_5 = "M5"

# V6 Filters
EMA_PERIOD = 50
RSI_MIN = 50
RSI_MAX = 65
SL_DISTANCE = 9.0      # $9
TP1_DISTANCE = 6.0     # $6 - sure hit
TP2_DISTANCE = 11.0    # $11 - momentum
SPREAD_BUFFER_ENTRY = 0.60
SPREAD_BUFFER_SL = 0.50

# ========= INDICATORS =========
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_squeeze(df):
    # Bollinger + Keltner squeeze
    sma20 = df['close'].rolling(20).mean()
    std20 = df['close'].rolling(20).std()
    upper_bb = sma20 + std20*2
    lower_bb = sma20 - std20*2
    # Keltner simplified
    atr = (df['high']-df['low']).rolling(20).mean()
    upper_kc = sma20 + atr*1.5
    lower_kc = sma20 - atr*1.5
    squeeze_on = (lower_bb > lower_kc) & (upper_bb < upper_kc)
    return squeeze_on

def find_fvg(df):
    # 15M Bullish FVG: low[0] > high[2]
    fvg_list = []
    for i in range(2, len(df)):
        if df['low'].iloc[i] > df['high'].iloc[i-2]:
            fvg_list.append((df['low'].iloc[i], df['high'].iloc[i-2], i))
    return fvg_list[-1] if fvg_list else None

def find_bos(df, direction="bull"):
    # 5M BOS: close breaks last swing high
    last_high = df['high'].rolling(10).max().iloc[-2]
    if direction == "bull" and df['close'].iloc[-1] > last_high:
        return True
    last_low = df['low'].rolling(10).min().iloc[-2]
    if direction == "bear" and df['close'].iloc[-1] < last_low:
        return True
    return False

def find_next_liquidity(df, direction="bull"):
    # Next Buy Side Liquidity = recent swing high / equal highs
    if direction == "bull":
        # last 20 candles high
        liquidity = df['high'].rolling(5).max().iloc[-20:].max()
        # add wick buffer $1.5 for liquidity grab
        return liquidity + 1.5
    else:
        liquidity = df['low'].rolling(5).min().iloc[-20:].min()
        return liquidity - 1.5

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

# ========= MAIN LOOP =========
def check_signal(df_1h, df_15, df_5):
    # Filters
    ema_1h = ema(df_1h['close'], EMA_PERIOD).iloc[-1]
    ema_15 = ema(df_15['close'], EMA_PERIOD).iloc[-1]
    rsi_15 = rsi(df_15['close']).iloc[-1]
    squeeze_15 = get_squeeze(df_15)

    # V6 STRICT CONDITIONS
    if not (RSI_MIN <= rsi_15 <= RSI_MAX):
        return None, f"Skip RSI {rsi_15:.1f} not in 50-65"
    
    # Squeeze must JUST turn OFF: previous ON, current OFF
    if len(squeeze_15) < 2 or not (squeeze_15.iloc[-2] == True and squeeze_15.iloc[-1] == False):
        return None, "Skip Squeeze not just OFF"

    if not (df_1h['close'].iloc[-1] > ema_1h and df_15['close'].iloc[-1] > ema_15):
        return None, "Skip not above EMA50 1H+15M"

    fvg = find_fvg(df_15)
    if not fvg:
        return None, "No FVG"

    if not find_bos(df_5, "bull"):
        return None, "No 5M BOS"

    # ENTRY + BUFFERS
    entry_raw = df_15['close'].iloc[-1]
    entry = entry_raw + SPREAD_BUFFER_ENTRY
    sl = entry - SL_DISTANCE - SPREAD_BUFFER_SL
    
    tp1 = entry + TP1_DISTANCE
    tp2 = entry + TP2_DISTANCE
    tp3 = find_next_liquidity(df_15, "bull")

    msg = f"""🚀 V6 LONG SIGNAL - 80% SETUP
Symbol: XAUUSD
Entry: {entry:.2f}
SL: {sl:.2f} (-${SL_DISTANCE})

TP1: {tp1:.2f} (+${TP1_DISTANCE}) 30%
TP2: {tp2:.2f} (+${TP2_DISTANCE}) 30%
TP3: {tp3:.2f} (Next Liquidity BSL) 40% 🎯

Filters: RSI {rsi_15:.1f} | EMA50 OK | Squeeze OFF→ON | FVG+5M BOS
No BE - Manage manually | 0.05 lot = TP1 $9 / TP2 $16.5 / TP3 ~${(tp3-entry)*5:.1f}
"""
    return msg, "OK"

# --- Replace this with your MT5 / data feed ---
def get_data():
    # TODO: Connect to MT5 or your data API
    # df_1h, df_15, df_5 = mt5_get_data()
    # For now dummy
    pass

if __name__ == "__main__":
    while True:
        try:
            # df_1h, df_15, df_5 = get_data()
            # signal, reason = check_signal(df_1h, df_15, df_5)
            # if signal:
            #     send_telegram(signal)
            # else:
            #     print(reason)
            pass
        except Exception as e:
            print(e)
        time.sleep(60)
