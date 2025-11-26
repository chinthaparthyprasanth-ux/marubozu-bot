import requests
import time
import statistics
from datetime import datetime

# ================================
# CONFIG
# ================================
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

EMA_SHORT = 50
EMA_LONG = 200
TP_RR = 2
USE_TREND_FILTER = True
CHECK_INTERVAL_SECONDS = 60


# ================================
# HELPERS
# ================================
def log(msg):
    print(f"[{datetime.utcnow()}] {msg}", flush=True)


def telegram_send(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=5)
    except:
        pass


# ================================
# BINANCE SAFE REQUEST
# ================================
def safe_get(url):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None


# ================================
# GET ALL BINANCE FUTURES SYMBOLS
# ================================
def get_all_futures():
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    data = safe_get(url)

    if not data or "symbols" not in data:
        log("❌ Binance blocked or rate-limited")
        return []

    futures = [
        s["symbol"]
        for s in data["symbols"]
        if s["contractType"] == "PERPETUAL" and s["status"] == "TRADING"
    ]

    return futures


# ================================
# GET 4H KLINES
# ================================
def fetch_futures_klines(symbol):
    url = (
        f"https://fapi.binance.com/fapi/v1/klines"
        f"?symbol={symbol}&interval=4h&limit=300"
    )
    return safe_get(url) or []


# ================================
# SIMPLE EMA
# ================================
def calc_ema(values, window):
    ema = []
    k = 2 / (window + 1)
    for i, val in enumerate(values):
        if i == 0:
            ema.append(val)
        else:
            ema.append(val * k + ema[-1] * (1 - k))
    return ema


# ================================
# MARUBOZU CHECK
# ================================
def analyze(o, h, l, c, vol, bodies, avg_vol):
    body = abs(c - o)
    candle_size = h - l

    if body < candle_size * 0.6:
        return False, None

    if vol < avg_vol * 1.5:
        return False, None

    direction = "bull" if c > o else "bear"
    return True, direction


# ================================
# MAIN LOOP
# ================================
def run():
    log("🚀 Bot Started (Render.com)")

    last_alert = {}

    while True:
        try:
            log("🔍 Fetching futures list...")
            symbols = get_all_futures()

            if not symbols:
                log("⚠ No symbols available. Retrying...")
                time.sleep(5)
                continue

            log(f"📌 Total Futures: {len(symbols)}")

            for s in symbols:
                try:
                    klines = fetch_futures_klines(s)
                    if not klines or len(klines) < 30:
                        continue

                    # last closed candle
                    last = klines[-2]
                    ot = int(last[0])
                    o, h, l, c, vol = (
                        float(last[1]),
                        float(last[2]),
                        float(last[3]),
                        float(last[4]),
                        float(last[5]),
                    )

                    # avoid duplicate signal
                    if last_alert.get(s) == ot:
                        continue

                    # marubozu check
                    bodies = [
                        abs(float(k[4]) - float(k[1]))
                        for k in klines[-12:-2]
                    ]
                    vols = [float(k[5]) for k in klines[-22:-2]]
                    avg_vol = statistics.mean(vols)

                    ok, direction = analyze(o, h, l, c, vol, bodies, avg_vol)
                    if not ok:
                        continue

                    # trend filter
                    closes = [float(k[4]) for k in klines[-300:]]
                    ema_s = calc_ema(closes, EMA_SHORT)[-1]
                    ema_l = calc_ema(closes, EMA_LONG)[-1]
                    trend = "up" if ema_s > ema_l else "down"

                    if USE_TREND_FILTER:
                        if direction == "bull" and trend != "up":
                            continue
                        if direction == "bear" and trend != "down":
                            continue

                    # SL / TP
                    if direction == "bull":
                        sl = l - (0.002 * c)
                        tp = c + TP_RR * (c - sl)
                    else:
                        sl = h + (0.002 * c)
                        tp = c - TP_RR * (sl - c)

                    msg = f"""
🚨 <b>{direction.upper()} MARUBOZU FOUND</b>
Symbol: <b>{s}</b>
TF: <b>4H</b>

Entry: <b>{c}</b>
SL: <b>{sl}</b>
TP: <b>{tp}</b>

Trend: <b>{trend}</b>
"""
                    telegram_send(msg)
                    log(f"📤 SENT → {s}")

                    last_alert[s] = ot

                except Exception as e:
                    log(f"❌ Error {s}: {e}")

            time.sleep(CHECK_INTERVAL_SECONDS)

        except Exception as e:
            log(f"🔥 MAIN LOOP ERROR: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run()
