# ============================================
# NIFTY 50 Live Signal Checker
# Author: Vihaan Jain
# Purpose: Check current market conditions
#          and output today's trading signal
# ============================================

import yfinance as yf
import pandas as pd
from datetime import datetime

def get_signal():
    print("=" * 50)
    print(f"NIFTY SIGNAL CHECKER")
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # Download recent data - enough for all indicators
    nifty = yf.download("^NSEI", period="6mo", interval="1h", progress=False)
    nifty.columns = nifty.columns.get_level_values(0)

    # Calculate all indicators
    nifty["MA20"] = nifty["Close"].rolling(window=20).mean()
    nifty["MA100"] = nifty["Close"].rolling(window=100).mean()
    nifty["MA400"] = nifty["Close"].rolling(window=400).mean()

    # RSI
    delta = nifty["Close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    nifty["RSI"] = 100 - (100 / (1 + rs))

    # ADX
    high = nifty["High"]
    low = nifty["Low"]
    close = nifty["Close"]

    plus_dm = high.diff()
    minus_dm = low.diff().abs()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)

    atr_series = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr_series)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr_series)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    nifty["ADX"] = dx.rolling(14).mean()
    nifty["ATR10"] = tr.rolling(10).mean()

    # Get the last complete candle
    row = nifty.iloc[-1]
    prev_row = nifty.iloc[-2]
    prev2_row = nifty.iloc[-3]

    close = round(float(row["Close"]), 2)
    ma20 = round(float(row["MA20"]), 2)
    ma100 = round(float(row["MA100"]), 2)
    ma400 = round(float(row["MA400"]), 2)
    rsi = round(float(row["RSI"]), 2)
    adx = round(float(row["ADX"]), 2)
    atr10 = round(float(row["ATR10"]), 2)

    # Current candle data
    open_curr = float(row["Open"])
    high_curr = float(row["High"])
    low_curr = float(row["Low"])
    close_curr = float(row["Close"])

    open_prev = float(prev_row["Open"])
    close_prev = float(prev_row["Close"])
    high_prev = float(prev_row["High"])
    low_prev = float(prev_row["Low"])

    open_prev2 = float(prev2_row["Open"])
    close_prev2 = float(prev2_row["Close"])

    # Last 10 and 20 candles
    last10 = nifty.iloc[-11:-1]
    last20 = nifty.iloc[-21:-1]

    # Count MA20 crosses
    ma20_crosses = 0
    for i in range(1, len(last10)):
        pc = float(last10["Close"].iloc[i-1])
        cc = float(last10["Close"].iloc[i])
        pm = float(last10["MA20"].iloc[i-1])
        cm = float(last10["MA20"].iloc[i])
        if (pc < pm and cc > cm) or (pc > pm and cc < cm):
            ma20_crosses += 1

    # Choppy market detector
    last10_high = float(last10["High"].max())
    last10_low = float(last10["Low"].min())
    last10_close_start = float(last10["Close"].iloc[0])
    last10_close_end = float(last10["Close"].iloc[-1])

    adx_strong = adx > 28
    ma_separation = abs(ma20 - ma100) / ma100 * 100
    ma_separated = ma_separation > 0.5
    not_oscillating = ma20_crosses <= 3
    net_move = abs(last10_close_end - last10_close_start)
    atr_justified = net_move > atr10 * 0.5
    swing_range = last10_high - last10_low
    swing_meaningful = swing_range > close * 0.01
    not_choppy = adx_strong and ma_separated and not_oscillating and atr_justified and swing_meaningful

    # Trend reversal detector
    last20_lows = last20["Low"].values
    early_low = float(last20_lows[:10].mean())
    recent_low = float(last20_lows[10:].mean())
    not_recovering = recent_low <= early_low * 1.005

    # Candlestick patterns
    body = abs(close_curr - open_curr)
    lower_wick = min(close_curr, open_curr) - low_curr
    upper_wick = high_curr - max(close_curr, open_curr)
    body_prev = abs(close_prev - open_prev)
    body_prev2 = abs(close_prev2 - open_prev2)

    bullish_engulfing = (
        close_prev < open_prev and
        close_curr > open_curr and
        close_curr > open_prev and
        open_curr < close_prev
    )
    hammer = (
        body > 0 and
        lower_wick >= 2 * body and
        upper_wick <= 0.3 * body
    )
    midpoint_prev2 = (open_prev2 + close_prev2) / 2
    morning_star = (
        close_prev2 < open_prev2 and
        body_prev < body_prev2 * 0.3 and
        close_curr > open_curr and
        close_curr > midpoint_prev2 and
        body > body_prev2 * 0.5
    )
    tweezer_bottom = (
        close_prev < open_prev and
        close_curr > open_curr and
        abs(low_curr - low_prev) <= 0.001 * low_prev
    )
    bearish_engulfing = (
        close_prev > open_prev and
        close_curr < open_curr and
        close_curr < open_prev and
        open_curr > close_prev
    )
    shooting_star = (
        body > 0 and
        upper_wick >= 2 * body and
        lower_wick <= 0.3 * body
    )
    midpoint_prev2_bear = (open_prev2 + close_prev2) / 2
    evening_star = (
        close_prev2 > open_prev2 and
        body_prev < body_prev2 * 0.3 and
        close_curr < open_curr and
        close_curr < midpoint_prev2_bear and
        body > body_prev2 * 0.5
    )
    tweezer_top = (
        close_prev > open_prev and
        close_curr < open_curr and
        abs(high_curr - high_prev) <= 0.001 * high_prev
    )

    good_candle = bullish_engulfing or hammer or morning_star or tweezer_bottom or (close_curr > open_curr)
    bad_candle = bearish_engulfing or shooting_star or evening_star or tweezer_top or (close_curr < open_curr)
    no_upper_wick_rejection = upper_wick <= 1.5 * body
    no_lower_wick_rejection = lower_wick <= 1.5 * body if body > 0 else True

    # Signal conditions
    ma_signal = ma20 > ma100
    uptrend = close > ma400 and ma100 > ma400
    good_rsi = 20 < rsi < 65
    price_above_ma20 = close > ma20

    ma_signal_short = ma20 < ma100
    downtrend = close < ma400 and ma100 < ma400
    bad_rsi = 35 < rsi < 75
    price_below_ma20 = close < ma20

    # Determine signal
    if ma_signal and uptrend and good_rsi and price_above_ma20 and good_candle and no_upper_wick_rejection and not_choppy:
        signal = "🟢 LONG BUY"
    elif ma_signal_short and downtrend and bad_rsi and price_below_ma20 and bad_candle and no_lower_wick_rejection and not_choppy and not_recovering:
        signal = "🔴 SHORT"
    else:
        signal = "⚪ HOLD"

    # Print full report
    print(f"\nCURRENT NIFTY PRICE: ₹{close}")
    print(f"\n--- INDICATORS ---")
    print(f"MA20:  {ma20}")
    print(f"MA100: {ma100}")
    print(f"MA400: {ma400}")
    print(f"RSI:   {rsi}")
    print(f"ADX:   {adx}")
    print(f"\n--- MARKET CONDITIONS ---")
    print(f"Trend:         {'Uptrend ✅' if uptrend else 'Downtrend ❌' if downtrend else 'Neutral ⚪'}")
    print(f"Choppy Market: {'No ✅' if not_choppy else 'Yes ❌'}")
    print(f"Recovering:    {'Yes ❌' if not not_recovering else 'No ✅'}")
    print(f"RSI Zone:      {'Good ✅' if good_rsi else 'Overbought/Oversold ❌'}")
    print(f"Candle:        {'Bullish ✅' if good_candle else 'Bearish' if bad_candle else 'Neutral'}")
    print(f"\n{'=' * 50}")
    print(f"SIGNAL: {signal}")
    print(f"{'=' * 50}\n")

    return signal

if __name__ == "__main__":
    get_signal()