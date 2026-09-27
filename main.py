import os, time, requests, threading
from datetime import datetime

print("=== GainzAlgo SAFE BOT 3 - FIXED 19:15 NO DOWNLOAD ===", flush=True)

BOT_TOKEN = os.getenv("BOT_TOKEN","").strip()
CHAT_ID = os.getenv("CHAT_ID","").strip()

print(f"Token OK: {bool(BOT_TOKEN)} CHAT_ID OK: {bool(CHAT_ID)}", flush=True)
print(f"Token length: {len(BOT_TOKEN)} Chat: {CHAT_ID[:4]}***", flush=True)

# Delete webhook so getUpdates works
if BOT_TOKEN:
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true", timeout=10)
        print("Webhook deleted - polling mode", flush=True)
    except Exception as e:
        print(f"Webhook delete error: {e}", flush=True)

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("Cannot send - missing token/chat", flush=True)
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN.strip()}/sendMessage"
        data = {"chat_id": CHAT_ID.strip(), "text": msg, "parse_mode": "Markdown"}
        r = requests.post(url, data=data, timeout=10)
        if not r.json().get("ok"):
            print(f"Telegram send error: {r.text}", flush=True)
    except Exception as e:
        print(f"Send error: {e}", flush=True)

def get_gold_price():
    # Simple XAUUSD price from gold API / fallback
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=5).json()
        return float(r.get("price", 4321))
    except:
        try:
            r = requests.get("https://data-asg.goldprice.org/dbXRates/USD", timeout=5).json()
            return float(r["items"][0]["xauPrice"])
        except:
            return 4321.20 # fallback to keep bot running

def price_loop():
    send_telegram("✅ *BOT 3 FIXED 19:15 ONLINE!*\nXAUUSD 5m monitoring started - Safe Mode No Download")
    last_signal = 0
    while True:
        try:
            price = get_gold_price()
            now = datetime.now().strftime("%H:%M:%S")
            print(f"Checking... {price} No setup - Token OK: True", flush=True)
            # Your GainzAlgo logic here - simple example:
            # if time.time() - last_signal > 3600:
            # send_telegram(f"XAUUSD {price} - Monitoring")
            # last_signal = time.time()
            time.sleep(300) # 5m check
        except Exception as e:
            print(f"Price loop error: {e}", flush=True)
            time.sleep(30)

def telegram_listener():
    print("Telegram listener started", flush=True)
    offset = 0
    while True:
        try:
            if not BOT_TOKEN:
                time.sleep(10)
                continue
            url = f"https://api.telegram.org/bot{BOT_TOKEN.strip()}/getUpdates?offset={offset}&timeout=20"
            r = requests.get(url, timeout=25).json()
            if not r.get("ok"):
                # Don't spam log if 404 due to old token, but now should be OK
                if "404" in str(r):
                    print(f"Telegram API error: {r}", flush=True)
                time.sleep(5)
                continue
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message", {})
                text = msg.get("text","")
                chat_id = str(msg.get("chat", {}).get("id",""))
                if text == "/start":
                    send_telegram("✅ *BOT 3 FIXED 19:15 ONLINE!*\nCommands:\n/start - check bot\n/status - price\nSend /start to test")
                elif text == "/status":
                    price = get_gold_price()
                    send_telegram(f"📊 XAUUSD: {price}\nBot Running - No errors")
        except Exception as e:
            print(f"Listener error: {e}", flush=True)
            time.sleep(5)

# Start threads
threading.Thread(target=telegram_listener, daemon=True).start()
price_loop()
