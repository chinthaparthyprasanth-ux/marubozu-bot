def run():
    log("🚀 Marubozu Futures Bot Started (Railway)")
    last_alert = {}

    while True:
        try:
            log("🔍 Fetching top 50 futures symbols...")
            symbols = get_top_futures()
            log(f"📌 Found {len(symbols)} symbols")

            for s in symbols:
                try:
                    log(f"⏳ Fetching klines for {s}")
                    klines = fetch_futures_klines(s)

                    if len(klines) < 30:
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
                        log(f"⏭️ Already alerted for {s}, skipping...")
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

                    log(f"📈 Trend for {s}: {trend}")

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
🚨 <b>{direction.upper()} MARUBOZU (Binance Futures)</b>
Symbol: <b>{s}</b>
TF: <b>4H</b>

Close: <b>{c}</b>
Volume: <b>{vol}</b>
Trend: <b>{trend}</b>

Entry: <b>{entry}</b>
SL: <b>{sl}</b>
TP: <b>{tp}</b>

<i>Railway Bot</i>
"""
                    telegram_send(msg)
                    log(f"📤 ALERT SENT → {s}")

                    last_alert[s] = ot

                except Exception as e:
                    log(f"❌ ERROR processing {s}: {e}")

            log("😴 Sleeping 60 seconds...")
            time.sleep(CHECK_INTERVAL_SECONDS)

        except Exception as e:
            log(f"🔥 MAIN LOOP ERROR: {e}")
            time.sleep(5)
