import yfinance as yf
import matplotlib.pyplot as plt

# Download NIFTY data - 2 years for MA200 to work
nifty = yf.download("^NSEI", start="2024-06-01", end="2026-06-16", interval="1d")
nifty.columns = nifty.columns.get_level_values(0)

# Calculate moving averages
nifty["MA10"] = nifty["Close"].rolling(window=10).mean()
nifty["MA50"] = nifty["Close"].rolling(window=50).mean()
nifty["MA200"] = nifty["Close"].rolling(window=200).mean()

# Backtest settings
starting_capital = 100000
capital = starting_capital
position = 0
buy_price = 0
hold_days = 0
cooldown = 0
min_hold = 5
trades = []
buy_dates = []
buy_prices_list = []
sell_dates = []
sell_prices_list = []

print("--- BACKTEST RESULTS ---\n")

for date, row in nifty.iterrows():
    if str(row["MA10"]) == "nan" or str(row["MA50"]) == "nan" or str(row["MA200"]) == "nan":
        continue

    close = round(float(row["Close"]), 2)
    ma10 = round(float(row["MA10"]), 2)
    ma50 = round(float(row["MA50"]), 2)
    ma200 = round(float(row["MA200"]), 2)
    signal = "BUY" if ma10 > ma50 else "SELL"

    # Count down cooldown
    if cooldown > 0:
        cooldown -= 1

    # BUY condition
    if signal == "BUY" and position == 0 and cooldown == 0 and close > ma200:
        position = capital / close
        buy_price = close
        capital = 0
        hold_days = 0
        buy_dates.append(date)
        buy_prices_list.append(close)
        print(f"{date} | BUY at {close} | Units: {round(position, 4)}")

    # SELL condition
    elif position > 0:
        hold_days += 1
        stop_loss_price = round(buy_price * 0.985, 2)

        if hold_days >= min_hold:
            if signal == "SELL" or close < stop_loss_price:
                exit_reason = "STOP LOSS" if close < stop_loss_price else "SIGNAL"
                capital = position * close
                profit = round(capital - starting_capital, 2)
                trades.append({"exit": exit_reason, "pnl": round((close - buy_price) * position, 2)})
                sell_dates.append(date)
                sell_prices_list.append(close)
                print(f"{date} | {exit_reason} SELL at {close} | Capital: ₹{round(capital, 2)} | Profit so far: ₹{profit}")
                position = 0
                hold_days = 0
                if exit_reason == "STOP LOSS":
                    cooldown = 5

# Final result
if position > 0:
    final_value = round(position * float(nifty["Close"].iloc[-1]), 2)
else:
    final_value = round(capital, 2)

print(f"\n--- FINAL PORTFOLIO VALUE: ₹{final_value} ---")
print(f"--- TOTAL PROFIT/LOSS: ₹{round(final_value - starting_capital, 2)} ---")

# Performance metrics
winning_trades = [t for t in trades if t["pnl"] > 0]
losing_trades = [t for t in trades if t["pnl"] <= 0]

win_rate = round(len(winning_trades) / len(trades) * 100, 2) if trades else 0
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

# Plot with buy/sell markers
fig, ax = plt.subplots(figsize=(12,6))
ax.plot(nifty.index, nifty["Close"], color="blue", label="NIFTY 50", linewidth=1)
ax.scatter(buy_dates, buy_prices_list, color="green", marker="^", s=150, label="BUY", zorder=5)
ax.scatter(sell_dates, sell_prices_list, color="red", marker="v", s=150, label="SELL", zorder=5)
ax.set_title("NIFTY 50 - Algo Buy/Sell Signals")
ax.set_xlabel("Date")
ax.set_ylabel("Price")
ax.grid(True)
ax.legend()
plt.tight_layout()
plt.show()