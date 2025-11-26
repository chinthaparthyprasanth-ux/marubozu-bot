import time
import requests
import statistics
from datetime import datetime

# ==================== TELEGRAM CONFIG ====================
TELEGRAM_TOKEN = "8303064683:AAH3HF-RT8UGpKFbBCetjejd3b0xf-v7zZs"
TELEGRAM_CHAT_ID = "7653908542"
# ==========================================================

# ==================== BOT CONFIG ==========================
BINANCE_FUTURES = "https://fapi.binance.com"
CHECK_INTERVAL_SECONDS = 60
BODY_PCT_OF_RANGE = 0.80
WICK_PCT_OF_RANGE = 0.05
MIN_BODY_VS_AVG = 1.5
VOLUME_MULTIPLIER = 1.5
EMA_SHORT = 21
EMA_LONG = 200
USE_TREND_FILTER = True
TP_RR = 2.0
# ==========================================================


def log(msg):
    print(f"[{datetime.utcnow()}] {msg}", flush=True)


def telegram_send(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        log(f"Telegram Error: {e}")


# ==================== FETCH ALL FUTURES SYMBOLS ====================
def get_all_futures_symbols():
    try:
        url = f"{BINANCE_FUTURES}/fapi/v1/exchangeInfo"
        data = requests.get(url, timeout=10).json()

        # Prevent crashing if Binance returns error
        if "symbols" not in data:
            log(f"❌ Binance API Error (exchangeInfo): {data}")
            return []

        symbols = []
        for s in data["symbols"]:
            if s["contractType"] == "PERPETUAL" and s["quoteAsset"] == "USDT":
                symbols.append(s["symbol"])

        return symbols

    except Exception as e:
        log(f"❌ ERROR fetching symbols: {e}")
        return []


# ==================== FETCH FUTURES KLINES =========================
def fetch_futures_klines(symbol):
    try:
        url = f"{BINANCE_FUTURES}/fapi/v1/klines"
        params = {"symbol": symbol, "interval": "4h", "limit": 200}
        data = requests.get(url, params=params, timeout=10).json()

        if isinstance(data, dict) and "code" in data:
            log(f"❌ Binance API Error for {symbol}: {data}")
            return []

        return data

    except Exception as e:
        log(f"❌ ERROR fetching klines for {symbol}: {e}")
        return []


# ==================== EMA CALC ==========================
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


# ==================== MARUBOZU CHECK ====================
def analyze(o, h, l, c, vol, bodies, avg_vol):
    body = abs(c - o)
    rng = h - l
    if rng == 0:
        return False, None

    upper = h - max(o, c)
    lower = min(o, c) - l

    if (
        body / rng >= BODY_PCT_OF_RANGE
        and upper / rng <= WICK_PCT_OF_RANGE
        and lower / rng <= WICK_PCT_OF_RANGE
        and body >= MIN_BODY_VS_AVG * statistics.mean(bodies)
        and vol >= VOLUME_MULTIPLIER * avg_vol
    ):
        return True, "bull" if c > o else "bear"

    return False, None


# ==================== MAIN LOOP ==========================
def run():
    log("🚀 Marubozu Futures Bot Started (ALL BINANCE FUTURES)")
    last_alert = {}

    while True:
        try:
            log("🔍 Fetching ALL Binance Futures symbols...")
            symbols = get_all_futures_symbols()

            if not symbols:
                log("⚠️ No symbols fetched — Binance may be rate-limiting. Retrying...")
                time.sleep(5)
                continue

            log(f"📌 Total futures pairs: {len(symbols)}")

            for s in symbols:
                try:
                    log(f"⏳ Fetching klines for {s}")
                    klines = fetch_futures_klines(s)

                    if not klines or len(klines) < 30:
                        log(f"⚠️ Not enough data for {s}")
                        continue

                    last_closed = klines[-2]
                    ot = int(last_closed[0])
                    o, h, l, c, vol = (
                        float(last_closed[1]),
                        float(last_closed[2]),
                        float(last_closed[3]),
                        float(last_closed[4]),
                        float(last_closed[5]),
                    )

                    if last_alert.get(s) == ot:
                        continue

                    bodies = [abs(float(k[4]) - float(k[1])) for k in klines[-12:-2]]
                    vols = [float(k[5]) for k in klines[-22:-2]]
                    avg_vol = statistics.mean(vols) if vols else vol

                    ok, direction = analyze(o, h, l, c, vol, bodies, avg_vol)
                    log(f"📉 Analyzed {s}: ok={ok}, direction={direction}")

                    if not ok:
                        continue

                    closes = [float(k[4]) for k in klines[-300:]]
                    ema_s = calc_ema(closes, EMA_SHORT)[-1]
                    ema_l = calc_ema(closes, EMA_LONG)[-1]
                    trend = "up" if ema_s > ema_l else "down"

                    log(f"📈 EMA Trend for {s}: {trend}")

                    if USE_TREND_FILTER:
                        if direction == "bull" and trend != "up":
                            continue
                        if direction == "bear" and trend != "down":
                            continue

                    if direction == "bull":
                        entry = c
                        sl = l - (0.002 * c)
                        tp = entry + TP_RR * (entry - sl)
                    else:
                        entry = c
                        sl = h + (0.002 * c)
                        tp = entry - TP_RR * (sl - entry)

                    msg = f"""
🚨 <b>{direction.upper()} MARUBOZU FOUND</b>
Symbol: <b>{s}</b>
Timeframe: <b>4H</b>

Close: <b>{c}</b>
Volume: <b>{vol}</b>
Trend: <b>{trend}</b>

Entry: <b>{entry}</b>
SL: <b>{sl}</b>
TP: <b>{tp}</b>

<i>Binance Futures Scanner</i>
"""
                    telegram_send(msg)
                    log(f"📤 ALERT SENT → {s}")

                    last_alert[s] = ot

                except Exception as e:
                    log(f"❌ ERROR processing {s}: {e}")

            log("😴 Sleeping 60 seconds...\n")
            time.sleep(CHECK_INTERVAL_SECONDS)

        except Exception as e:
            log(f"🔥 MAIN LOOP ERROR: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run()
