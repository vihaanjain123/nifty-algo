import yfinance as yf
import matplotlib.pyplot as plt

# Download hourly NIFTY data
nifty = yf.download("^NSEI", start="2025-06-01", end="2026-06-17", interval="1h")
nifty.columns = nifty.columns.get_level_values(0)

# Calculate indicators on full dataset first
nifty["MA20"] = nifty["Close"].rolling(window=20).mean()
nifty["MA100"] = nifty["Close"].rolling(window=100).mean()
nifty["MA400"] = nifty["Close"].rolling(window=400).mean()

delta = nifty["Close"].diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)
avg_gain = gain.rolling(window=14).mean()
avg_loss = loss.rolling(window=14).mean()
rs = avg_gain / avg_loss
nifty["RSI"] = 100 - (100 / (1 + rs))

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
        if any(str(row[col]) == "nan" for col in ["MA20", "MA100", "MA400", "RSI"]):
            continue

        close = round(float(row["Close"]), 2)
        ma20 = round(float(row["MA20"]), 2)
        ma100 = round(float(row["MA100"]), 2)
        ma400 = round(float(row["MA400"]), 2)
        rsi = round(float(row["RSI"]), 2)

        open_curr = float(row["Open"])
        high_curr = float(row["High"])
        low_curr = float(row["Low"])
        close_curr = float(row["Close"])

        idx = nifty.index.get_loc(date)
        if idx == 0:
            continue
        prev_row = nifty.iloc[idx - 1]
        open_prev = float(prev_row["Open"])
        close_prev = float(prev_row["Close"])

        # Candlestick patterns
        bullish_engulfing = (
            close_prev < open_prev and
            close_curr > open_curr and
            close_curr > open_prev and
            open_curr < close_prev
        )

        body = abs(close_curr - open_curr)
        lower_wick = min(close_curr, open_curr) - low_curr
        upper_wick = high_curr - max(close_curr, open_curr)

        hammer = (
            body > 0 and
            lower_wick >= 2 * body and
            upper_wick <= 0.3 * body
        )

        good_candle = bullish_engulfing or hammer or (close_curr > open_curr)
        no_upper_wick_rejection = upper_wick <= 1.5 * body

        # Signal conditions
        ma_signal = ma20 > ma100
        uptrend = close > ma400 and ma100 > ma400
        good_rsi = 20 < rsi < 65
        price_above_ma20 = close > ma20

        if cooldown > 0:
            cooldown -= 1

        # BUY
        if ma_signal and uptrend and good_rsi and price_above_ma20 and good_candle and no_upper_wick_rejection and position == 0 and cooldown == 0:
            position = capital / close
            buy_price = close
            capital = 0
            hold_bars = 0
            highest_price = close
            buy_dates.append(date)
            buy_prices_list.append(close)
            print(f"{date} | BUY at {close} | Units: {round(position, 4)}")

        # SELL
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
                    print(f"{date} | {exit_reason} SELL at {close} | Capital: ₹{round(capital, 2)} | Profit: ₹{profit}")
                    position = 0
                    hold_bars = 0
                    highest_price = 0
                    if exit_reason == "TRAILING STOP":
                        cooldown = 6

    # Final result
    if position > 0:
        final_value = round(position * float(data["Close"].iloc[-1]), 2)
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
    ax.scatter(buy_dates, buy_prices_list, color="green", marker="^", s=100, label="BUY", zorder=5)
    ax.scatter(sell_dates, sell_prices_list, color="red", marker="v", s=100, label="SELL", zorder=5)
    ax.set_title(f"NIFTY 50 - {label}")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price")
    ax.grid(True)
    ax.legend()
    plt.tight_layout()
    plt.show()

    return final_value

# Run on training data first
print("=" * 50)
print("TRAINING PHASE - Tuning parameters")
print("=" * 50)
train_result = run_backtest(train, "TRAINING")

# Run on test data - this is the real test
print("\n" + "=" * 50)
print("TESTING PHASE - Real performance check")
print("=" * 50)
test_result = run_backtest(test, "TESTING")

print("\n" + "=" * 50)
print(f"TRAINING Return: {round((train_result - 100000) / 100000 * 100, 2)}%")
print(f"TESTING Return: {round((test_result - 100000) / 100000 * 100, 2)}%")
print("=" * 50)