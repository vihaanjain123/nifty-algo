import yfinance as yf

# Download real NIFTY 50 data
nifty = yf.download("^NSEI", start="2025-12-01", end="2026-06-16", interval="1d")

# Flatten the column structure
nifty.columns = nifty.columns.get_level_values(0)

# Calculate moving averages
nifty["MA5"] = nifty["Close"].rolling(window=5).mean()
nifty["MA20"] = nifty["Close"].rolling(window=20).mean()

# Print close price vs moving average
print("\n--- CLOSE PRICE vs 5 DAY MOVING AVERAGE ---")
for date, row in nifty.iterrows():
    close = round(float(row["Close"]), 2)
    ma5 = round(float(row["MA5"]), 2) if str(row["MA5"]) != "nan" else "N/A"
    print(date, "| Close:", close, "| MA5:", ma5)

# Crossover strategy - MA5 vs MA20
print("\n--- MA5 vs MA20 CROSSOVER SIGNALS ---")
for date, row in nifty.iterrows():
    if str(row["MA5"]) == "nan" or str(row["MA20"]) == "nan":
        continue
    close = round(float(row["Close"]), 2)
    ma5 = round(float(row["MA5"]), 2)
    ma20 = round(float(row["MA20"]), 2)
    signal = "BUY" if ma5 > ma20 else "SELL"
    print(date, "| Close:", close, "| MA5:", ma5, "| MA20:", ma20, "| Signal:", signal)