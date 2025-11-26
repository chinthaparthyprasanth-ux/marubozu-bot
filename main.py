import time
import requests
import statistics
from datetime import datetime, timezone

# ==================== TELEGRAM CONFIG ====================
TELEGRAM_TOKEN = "8303064683:AAH3HF-RT8UGpKFbBCetjejd3b0xf-v7zZs"
TELEGRAM_CHAT_ID = "7653908542"
# =========================================================

# ==================== BOT CONFIG (FUTURES) =========================
BINANCE_FUTURES = "https://fapi.binance.com"
CHECK_INTERVAL_SECONDS = 60
TOP_N = 50
BODY_PCT_OF_RANGE = 0.80
WICK_PCT_OF_RANGE = 0.05
MIN_BODY_VS_AVG = 1.5
VOLUME_MULTIPLIER = 1.5
EMA_SHORT = 21
EMA_LONG = 200
USE_TREND_FILTER = True
AVOID_CLOSE_TO_24H_HIGH_PCT = 0.01
AVOID_CLOSE_TO_24H_LOW_PCT = 0.01
TP_RR = 2.0
# =========================================================

def log(msg):
    print(f"[{datetime.utcnow()}] {msg}", flush=True)

def telegram_send(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload)
    except:
        pass

def get_top_futures():
    try:
        url = f"{BINANCE_FUTURES}/fapi/v1/ticker/24hr"
        r = requests.get(url, timeout=10).json()
        usdt = [x for x in r if x["symbol"].endswith("USDT")]
        sorted_usdt = sorted(usdt, key=lambda x: float(x["quoteVolume"]), reverse=True)
        return [x["symbol"] for x in sorted_usdt[:TOP_N]]
    except:
        return []

def fetch_futures_klines(symbol):
    url = f"{BINANCE_FUTURES}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": "4h", "limit": 200}
    return requests.get(url, params=params, timeout=10).json()

def calc_ema(values, period):
    k = 2 / (period + 1)
    ema = []
    prev = None
    for v in values:
        if prev is None:
            prev = v
        prev = (v - prev) * k + prev
        ema.append(prev)
    return ema

def analyze(o,h,l,c,vol,bodies,avg_vol):
    body = abs(c - o)
    rng = h - l
    if rng == 0:
        return False, None

    upper = h - max(o, c)
    lower = min(o, c) - l

    if body/rng >= BODY_PCT_OF_RANGE and \
       upper/rng <= WICK_PCT_OF_RANGE and \
       lower/rng <= WICK_PCT_OF_RANGE and \
       body >= MIN_BODY_VS_AVG * statistics.mean(bodies) and \
       vol >= VOLUME_MULTIPLIER * avg_vol:
        return True, "bull" if c > o else "bear"

    return False, None

def run():
    log("🚀 Marubozu Futures Bot Started (Railway)")
    last_alert = {}

    while True:
        try:
            symbols = get_top_futures()

            for s in symbols:
                try:
                    klines = fetch_futures_klines(s)
                    if len(klines) < 30:
                        continue

                    last_closed = klines[-2]
                    ot = int(last_closed[0])
                    o, h, l, c, vol = float(last_closed[1]), float(last_closed[2]), float(last_closed[3]), float(last_closed[4]), float(last_closed[5])

                    if last_alert.get(s) == ot:
                        continue

                    bodies = [abs(float(k[4]) - float(k[1])) for k in klines[-12:-2]]
                    vols  = [float(k[5]) for k in klines[-22:-2]]
                    avg_vol = statistics.mean(vols) if vols else vol

                    ok, direction = analyze(o,h,l,c,vol,bodies,avg_vol)
                    if not ok:
                        continue

                    closes = [float(k[4]) for k in klines[-300:]]
                    ema_s = calc_ema(closes, EMA_SHORT)[-1]
                    ema_l = calc_ema(closes, EMA_LONG)[-1]
                    trend = "up" if ema_s > ema_l else "down"

                    if USE_TREND_FILTER:
                        if direction == "bull" and trend != "up": continue
                        if direction == "bear" and trend != "down": continue

                    if direction == "bull":
                        entry = c
                        sl = l - (0.002 * c)
                        tp = entry + TP_RR * (entry - sl)
                    else:
                        entry = c
                        sl = h + (0.002 * c)
                        tp = entry - TP_RR * (sl - entry)

                    msg = f"""
🚨 <b>{direction.upper()} MARUBOZU (Binance Futures)</b>
Symbol: <b>{s}</b>
Timeframe: <b>4H</b>

Close: <b>{c}</b>
Volume: <b>{vol}</b>
Trend: <b>{trend}</b>

Entry: <b>{entry}</b>
SL: <b>{sl}</b>
TP: <b>{tp}</b>

<i>Sent from Railway Futures Bot</i>
"""
                    telegram_send(msg)
                    log(f"ALERT → {s}")

                    last_alert[s] = ot
                    time.sleep(0.2)

                except Exception as e:
                    log(f"Error {s}: {e}")

            time.sleep(CHECK_INTERVAL_SECONDS)

        except Exception as e:
            log(f"Main loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run()
