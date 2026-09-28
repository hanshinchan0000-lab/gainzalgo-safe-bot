from flask import Flask
import threading, time, requests, os
import yfinance as yf
import pandas as pd

app = Flask(__name__)
# ========== REAL GOLD ONANA CONFIG ==========
SYMBOL = "XAUUSD"
YF = "GC=F"
LIVE = True
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
last_price = 0
last_signal = 0
active_trade = None
COOLDOWN = 40*60

@app.route('/')
def home(): return f"✅ GAINZALGO V2 {SYMBOL} LIVE 1H/15M/5M Price:{last_price}", 200
@app.route('/health')
def health(): return "OK", 200

# ========== DATA MULTI-TF ==========
def get_tf(interval, period):
    try:
        df = yf.download(YF, period=period, interval=interval, progress=False)
        df = df.dropna()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df['EMA50'] = df['Close'].ewm(50).mean()
        df['EMA200'] = df['Close'].ewm(200).mean()
        return df
    except: return None

# ========== MARKET STRUCTURE HH HL LL LH ==========
def get_structure(df):
    # last 20 candles
    highs = df['High'].tail(20)
    lows = df['Low'].tail(20)
    # HH HL = bullish, LL LH = bearish
    is_hh_hl = highs.iloc[-1] > highs.iloc[-3] and lows.iloc[-1] > lows.iloc[-3]
    is_ll_lh = highs.iloc[-1] < highs.iloc[-3] and lows.iloc[-1] < lows.iloc[-3]
    if is_hh_hl: return "BULLISH HH-HL"
    if is_ll_lh: return "BEARISH LL-LH"
    return "RANGE"

# ========== REAL FVG 3 CANDLE IMBALANCE ==========
def find_real_fvg(df):
    bull_fvg, bear_fvg = [], []
    for i in range(1, len(df)-1):
        c1 = df.iloc[i-1]
        c2 = df.iloc[i]
        c3 = df.iloc[i+1]
        # BULLISH FVG: c1 High < c3 Low = imbalance, c2 is big
        if c1['High'] < c3['Low'] and (c3['Low'] - c1['High']) > 1.2:
            bull_fvg.append((float(c1['High']), float(c3['Low']), i, float(c2['Close'])))
        # BEARISH FVG: c1 Low > c3 High
        if c1['Low'] > c3['High'] and (c1['Low'] - c3['High']) > 1.2:
            bear_fvg.append((float(c3['High']), float(c1['Low']), i, float(c2['Close'])))
    return bull_fvg[-3:], bear_fvg[-3:]

# ========== OB ==========
def find_ob(df):
    bull_ob, bear_ob = [], []
    for i in range(len(df)-3):
        if df['Close'].iloc[i] < df['Open'].iloc[i] and df['Close'].iloc[i+1] - df['Open'].iloc[i+1] > 2.5:
            bull_ob.append((float(df['Low'].iloc[i]), float(df['High'].iloc[i]), i))
        if df['Close'].iloc[i] > df['Open'].iloc[i] and df['Open'].iloc[i+1] - df['Close'].iloc[i+1] > 2.5:
            bear_ob.append((float(df['Low'].iloc[i]), float(df['High'].iloc[i]), i))
    return bull_ob[-2:], bear_ob[-2:]

# ========== BOS / CHoCH ON 5M ==========
def check_bos_choch_5m():
    df5 = get_tf("5m", "2d")
    if df5 is None: return None, None
    # BOS bullish: close above last high
    last_high = df5['High'].tail(10).max()
    last_low = df5['Low'].tail(10).min()
    curr = df5.iloc[-1]
    prev = df5.iloc[-2]
    bos_bull = curr['Close'] > last_high and prev['Close'] < last_high
    bos_bear = curr['Close'] < last_low and prev['Close'] > last_low
    # CHoCH
    choch_bull = curr['Close'] > df5['High'].iloc[-5] and get_structure(df5) == "BULLISH HH-HL"
    choch_bear = curr['Close'] < df5['Low'].iloc[-5] and get_structure(df5) == "BEARISH LL-LH"

    if bos_bull or choch_bull: return "BULLISH BOS/CHoCH 5M", df5
    if bos_bear or choch_bear: return "BEARISH BOS/CHoCH 5M", df5
    return None, df5

def send_tg(msg):
    try:
        if not BOT_TOKEN: return
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e: print(e)

# ========== MAIN LOGIC 1H ANALYSE / 15M EXEC / 5M BOS ==========
def check_setup():
    global last_price, last_signal, active_trade

    if time.time() - last_signal < COOLDOWN: return
    if active_trade:
        df15 = get_tf("15m", "5d")
        if df15 is not None: check_hit(float(df15['Close'].iloc[-1]))
        return

    # 1. 1H ANALYSIS
    df1h = get_tf("1h", "20d")
    if df1h is None: return
    structure_1h = get_structure(df1h)
    trend_1h = "BULLISH" if df1h['Close'].iloc[-1] > df1h['EMA200'].iloc[-1] else "BEARISH"
    print(f"1H: {trend_1h} | {structure_1h}")

    # 2. 15M EXECUTION - FVG + OB
    df15 = get_tf("15m", "5d")
    if df15 is None: return
    bull_fvg, bear_fvg = find_real_fvg(df15)
    bull_ob, bear_ob = find_ob(df15)
    price = float(df15['Close'].iloc[-1])
    last_price = price

    # 3. 5M BOS/CHoCH CONFIRMATION
    bos_signal, df5 = check_bos_choch_5m()
    if not bos_signal: return # NEED 5M BOS/CHoCH

    print(f"5M: {bos_signal}")

    # --- LONG SETUP: 1H BULLISH + 15M BULL FVG/OB RETEST + 5M BULLISH BOS + CLOSE CONFIRM ---
    if "BULLISH" in bos_signal and trend_1h == "BULLISH":
        for low, high, idx, mid in bull_fvg + bull_ob:
            # Price need to ENTER exact zone and CLOSE above zone low (your requirement!)
            if low-1 <= price <= high+1:
                # Need close confirmation: close above zone + rejection
                last_candle = df15.iloc[-1]
                close_confirmed = last_candle['Close'] > low and last_candle['Close'] > last_candle['Open'] # bullish close
                wick_reject = (min(last_candle['Open'], last_candle['Close']) - last_candle['Low']) > 1.0

                if close_confirmed and wick_reject:
                    entry = price
                    sl = low - 2.0
                    risk = entry - sl
                    if risk < 1.2 or risk > 7: continue
                    tp1 = entry + risk*2 # 1:2 as you want
                    tp2 = entry + risk*3
                    tp3 = entry + risk*4

                    send_tg(f"""🚀 *GAINZALGO LONG - REAL SETUP* LIVE

1H: {trend_1h} {structure_1h}
15M: BULLISH FVG/OB RETEST {low:.1f}-{high:.1f}
5M: {bos_signal} ✅

*CLOSE CONFIRMED* above {low:.1f} + REJECTION

ENTRY: {entry:.2f} GOLD ONANA SPOT LIVE
SL: {sl:.2f} (-${risk:.2f})
TP1: {tp1:.2f} (1:2)
TP2: {tp2:.2f} (1:3)
TP3: {tp3:.2f} (1:4)

HH-HL + BOS + FVG exact close!
""")
                    last_signal = time.time()
                    active_trade = {"entry":entry,"sl":sl,"tp1":tp1,"tp2":tp2,"tp3":tp3,"dir":"LONG"}
                    return

    # --- SHORT SETUP: 1H BEARISH + 15M BEAR FVG/OB RETEST + 5M BEARISH BOS + CLOSE CONFIRM ---
    if "BEARISH" in bos_signal and trend_1h == "BEARISH":
        for low, high, idx, mid in bear_fvg + bear_ob:
            if low-1 <= price <= high+1:
                last_candle = df15.iloc[-1]
                close_confirmed = last_candle['Close'] < high and last_candle['Close'] < last_candle['Open']
                wick_reject = (last_candle['High'] - max(last_candle['Open'], last_candle['Close'])) > 1.0

                if close_confirmed and wick_reject:
                    entry = price
                    sl = high + 2.0
                    risk = sl - entry
                    if risk < 1.2 or risk > 7: continue
                    tp1 = entry - risk*2
                    tp2 = entry - risk*3
                    tp3 = entry - risk*4

                    send_tg(f"""🔻 *GAINZALGO SHORT - REAL SETUP* LIVE

1H: {trend_1h} {structure_1h}
15M: BEARISH FVG/OB RETEST {low:.1f}-{high:.1f}
5M: {bos_signal} ✅

*CLOSE CONFIRMED* below {high:.1f} + REJECTION

ENTRY: {entry:.2f} GOLD ONANA SPOT LIVE
SL: {sl:.2f} (-${risk:.2f})
TP1: {tp1:.2f} (1:2)
TP2: {tp2:.2f} (1:3)
TP3: {tp3:.2f} (1:4)

LL-LH + BOS + FVG exact close!
""")
                    last_signal = time.time()
                    active_trade = {"entry":entry,"sl":sl,"tp1":tp1,"tp2":tp2,"tp3":tp3,"dir":"SHORT"}
                    return

def check_hit(price):
    global active_trade
    if not active_trade: return
    sl, tp1, tp2, tp3, dir = active_trade['sl'], active_trade['tp1'], active_trade['tp2'], active_trade['tp3'], active_trade['dir']

    if dir == "LONG":
        if price <= sl:
            send_tg(f"❌ *SL HIT LONG* {price:.2f} Entry {active_trade['entry']:.2f}")
            active_trade = None
        elif price >= tp1 and price < tp2:
            send_tg(f"✅ *TP1 HIT LONG 1:2* {price:.2f}! SL to BE")
            active_trade['sl'] = active_trade['entry']
        elif price >= tp2:
            send_tg(f"✅✅ *TP2 HIT LONG* {price:.2f}!")
        elif price >= tp3:
            send_tg(f"🔥 *TP3 HIT LONG FULL* {price:.2f} DONE!")
            active_trade = None
    else:
        if price >= sl:
            send_tg(f"❌ *SL HIT SHORT* {price:.2f} Entry {active_trade['entry']:.2f}")
            active_trade = None
        elif price <= tp1:
            send_tg(f"✅ *TP1 HIT SHORT 1:2* {price:.2f}! SL to BE")
            active_trade['sl'] = active_trade['entry']
        elif price <= tp3:
            send_tg(f"🔥 *TP3 HIT SHORT FULL* {price:.2f} DONE!")
            active_trade = None

def bot_loop():
    send_tg(f"✅ *GAINZALGO V2 ONLINE*\n1H Analyse: HH/HL LL/LH\n15M Exec: Real FVG 3-candle + OB\n5M: BOS/CHoCH Confirm\nLONG+SHORT + Close confirm + 1:2 RR\nREAL GOLD ONANA LIVE!")
    while True:
        try:
            check_setup()
            time.sleep(60)
        except Exception as e:
            print(e)
            time.sleep(30)

threading.Thread(target=bot_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
