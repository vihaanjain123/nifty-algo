# ============================================
# NIFTY 50 Trading Algorithm - Version 1
# Author: Vihaan Jain
# Started: June 15, 2026
# Strategy: MA Crossover + RSI + Candlestick Patterns + Long/Short + ADX + Choppy Market Filter
# Timeframe: Hourly
# Status: Backtesting phase
# ============================================

import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd

# Download hourly NIFTY data
nifty = yf.download("^NSEI", start="2025-06-01", end="2026-06-17", interval="1h")
nifty.columns = nifty.columns.get_level_values(0)

# Calculate indicators on full dataset
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

# ADX manually
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

# ATR for choppy detection
nifty["ATR10"] = tr.rolling(10).mean()

# Split into train and test
train = nifty["2025-06-01":"2025-12-31"]
test = nifty["2026-01-01":"2026-06-17"]

def run_backtest(data, label):
    starting_capital = 100000
    capital = starting_capital
    position = 0
    buy_price = 0
    hold_bars = 0
    cooldown = 0
    highest_price = 0
    min_hold = 6
    trailing_stop_pct = 0.015
    trades = []
    buy_dates = []
    buy_prices_list = []
    sell_dates = []
    sell_prices_list = []

    print(f"\n--- {label} RESULTS ---\n")

    for date, row in data.iterrows():
        if any(str(row[col]) == "nan" for col in ["MA20", "MA100", "MA400", "RSI", "ADX", "ATR10"]):
            continue

        close = round(float(row["Close"]), 2)
        ma20 = round(float(row["MA20"]), 2)
        ma100 = round(float(row["MA100"]), 2)
        ma400 = round(float(row["MA400"]), 2)
        rsi = round(float(row["RSI"]), 2)
        adx = round(float(row["ADX"]), 2)
        atr10 = round(float(row["ATR10"]), 2)

        open_curr = float(row["Open"])
        high_curr = float(row["High"])
        low_curr = float(row["Low"])
        close_curr = float(row["Close"])

        idx = nifty.index.get_loc(date)
        if idx < 10:
            continue
        prev_row = nifty.iloc[idx - 1]
        prev2_row = nifty.iloc[idx - 2]

        open_prev = float(prev_row["Open"])
        close_prev = float(prev_row["Close"])
        high_prev = float(prev_row["High"])
        low_prev = float(prev_row["Low"])

        open_prev2 = float(prev2_row["Open"])
        close_prev2 = float(prev2_row["Close"])

        # Last 10 candles for choppy detection
        last10 = nifty.iloc[idx-10:idx]
        last10_high = float(last10["High"].max())
        last10_low = float(last10["Low"].min())
        last10_close_start = float(last10["Close"].iloc[0])
        last10_close_end = float(last10["Close"].iloc[-1])

        # Count MA20 crosses in last 10 candles
        ma20_crosses = 0
        for i in range(1, len(last10)):
            prev_close = float(last10["Close"].iloc[i-1])
            curr_close = float(last10["Close"].iloc[i])
            prev_ma20 = float(last10["MA20"].iloc[i-1])
            curr_ma20 = float(last10["MA20"].iloc[i])
            if (prev_close < prev_ma20 and curr_close > curr_ma20) or \
               (prev_close > prev_ma20 and curr_close < curr_ma20):
                ma20_crosses += 1

        # ============================================
        # CHOPPY MARKET DETECTOR - All 5 filters
        # ============================================

        # Filter 1: ADX must be strong enough
        adx_strong = adx > 28

        # Filter 2: MA separation must be significant
        ma_separation = abs(ma20 - ma100) / ma100 * 100
        ma_separated = ma_separation > 0.5

        # Filter 3: Price not crossing MA20 too often
        not_oscillating = ma20_crosses <= 3

        # Filter 4: Net price movement must justify ATR
        net_move = abs(last10_close_end - last10_close_start)
        atr_justified = net_move > atr10 * 0.5

        # Filter 5: Swing range must show directional movement
        swing_range = last10_high - last10_low
        swing_meaningful = swing_range > close * 0.01

        # Filter 6: Trend reversal detection - don't short into a recovery
        last20 = nifty.iloc[idx-20:idx]
        last20_lows = last20["Low"].values
        # Check if lows are trending upward (recovery signal)
        early_low = float(last20_lows[:10].mean())
        recent_low = float(last20_lows[10:].mean())
        not_recovering = recent_low <= early_low * 1.005  # recent lows not more than 0.5% above early lows

        # All 5 must pass
        not_choppy = adx_strong and ma_separated and not_oscillating and atr_justified and swing_meaningful

        # ============================================
        # Candlestick patterns
        # ============================================
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

        if cooldown > 0:
            cooldown -= 1

        # LONG BUY
        if ma_signal and uptrend and good_rsi and price_above_ma20 and good_candle and no_upper_wick_rejection and not_choppy and position == 0 and cooldown == 0:
            position = capital / close
            buy_price = close
            capital = 0
            hold_bars = 0
            highest_price = close
            buy_dates.append(date)
            buy_prices_list.append(close)
            print(f"{date} | LONG BUY at {close} | Units: {round(position, 4)}")

        # SHORT ENTRY
        # SHORT ENTRY
        elif ma_signal_short and downtrend and bad_rsi and price_below_ma20 and bad_candle and no_lower_wick_rejection and not_choppy and not_recovering and position == 0 and cooldown == 0:
            position = -(capital / close)
            buy_price = close
            capital = 0
            hold_bars = 0
            highest_price = close
            buy_dates.append(date)
            buy_prices_list.append(close)
            print(f"{date} | SHORT at {close} | Units: {round(abs(position), 4)}")

        # LONG EXIT
        elif position > 0:
            hold_bars += 1

            if close > highest_price:
                highest_price = close

            trailing_stop = round(highest_price * (1 - trailing_stop_pct), 2)

            if hold_bars >= min_hold:
                if (not ma_signal) or close < trailing_stop:
                    exit_reason = "TRAILING STOP" if close < trailing_stop else "SIGNAL"
                    capital = position * close
                    profit = round(capital - starting_capital, 2)
                    trades.append({"exit": exit_reason, "pnl": round((close - buy_price) * position, 2)})
                    sell_dates.append(date)
                    sell_prices_list.append(close)
                    print(f"{date} | LONG {exit_reason} SELL at {close} | Capital: ₹{round(capital, 2)} | Profit: ₹{profit}")
                    position = 0
                    hold_bars = 0
                    highest_price = 0
                    if exit_reason == "TRAILING STOP":
                        cooldown = 6

        # SHORT EXIT
        elif position < 0:
            hold_bars += 1

            if close < highest_price:
                highest_price = close

            trailing_stop_short = round(highest_price * (1 + trailing_stop_pct), 2)

            if hold_bars >= min_hold:
                if (not ma_signal_short) or close > trailing_stop_short:
                    exit_reason = "TRAILING STOP" if close > trailing_stop_short else "SIGNAL"
                    capital = abs(position) * (2 * buy_price - close)
                    profit = round(capital - starting_capital, 2)
                    trades.append({"exit": exit_reason, "pnl": round((buy_price - close) * abs(position), 2)})
                    sell_dates.append(date)
                    sell_prices_list.append(close)
                    print(f"{date} | SHORT COVER {exit_reason} at {close} | Capital: ₹{round(capital, 2)} | Profit: ₹{profit}")
                    position = 0
                    hold_bars = 0
                    highest_price = 0
                    if exit_reason == "TRAILING STOP":
                        cooldown = 6

    # Final result
    if position > 0:
        final_value = round(position * float(data["Close"].iloc[-1]), 2)
    elif position < 0:
        final_value = round(abs(position) * (2 * buy_price - float(data["Close"].iloc[-1])), 2)
    else:
        final_value = round(capital, 2)

    print(f"\n--- FINAL PORTFOLIO VALUE: ₹{final_value} ---")
    print(f"--- TOTAL PROFIT/LOSS: ₹{round(final_value - starting_capital, 2)} ---")

    if trades:
        winning_trades = [t for t in trades if t["pnl"] > 0]
        losing_trades = [t for t in trades if t["pnl"] <= 0]
        win_rate = round(len(winning_trades) / len(trades) * 100, 2)
        avg_win = round(sum(t["pnl"] for t in winning_trades) / len(winning_trades), 2) if winning_trades else 0
        avg_loss = round(sum(t["pnl"] for t in losing_trades) / len(losing_trades), 2) if losing_trades else 0

        print("\n--- PERFORMANCE METRICS ---")
        print(f"Total Trades: {len(trades)}")
        print(f"Winning Trades: {len(winning_trades)}")
        print(f"Losing Trades: {len(losing_trades)}")
        print(f"Win Rate: {win_rate}%")
        print(f"Average Win: ₹{avg_win}")
        print(f"Average Loss: ₹{avg_loss}")
        print(f"Total Return: {round((final_value - starting_capital) / starting_capital * 100, 2)}%")

        print("\n--- TRADE BREAKDOWN ---")
        for i, t in enumerate(trades):
            result = "WIN" if t["pnl"] > 0 else "LOSS"
            print(f"Trade {i+1}: {result} | P&L: ₹{t['pnl']} | Exit: {t['exit']}")

    # Plot
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(data.index, data["Close"], color="blue", label="NIFTY 50", linewidth=0.8)
    ax.scatter(buy_dates, buy_prices_list, color="green", marker="^", s=100, label="BUY/SHORT", zorder=5)
    ax.scatter(sell_dates, sell_prices_list, color="red", marker="v", s=100, label="SELL/COVER", zorder=5)
    ax.set_title(f"NIFTY 50 - {label}")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price")
    ax.grid(True)
    ax.legend()
    plt.tight_layout()
    plt.savefig(f"{label}_chart.png")

    return final_value
    plt.tight_layout()
    plt.savefig(f"{label}_chart.png")
    plt.close()
    print(f"Chart saved as {label}_chart.png")

# Run training
print("=" * 50)
print("TRAINING PHASE - Tuning parameters")
print("=" * 50)
train_result = run_backtest(train, "TRAINING")

# Run testing
print("\n" + "=" * 50)
print("TESTING PHASE - Real performance check")
print("=" * 50)
test_result = run_backtest(test, "TESTING")

print("\n" + "=" * 50)
print(f"TRAINING Return: {round((train_result - 100000) / 100000 * 100, 2)}%")
print(f"TESTING Return: {round((test_result - 100000) / 100000 * 100, 2)}%")
print("=" * 50)