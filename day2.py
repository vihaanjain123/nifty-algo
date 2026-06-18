# A list of dictionaries - multiple days of market data
market_data = [
    {"date": "2026-06-10", "price": 24500, "volume": 150000},
    {"date": "2026-06-11", "price": 24820, "volume": 162000},
    {"date": "2026-06-12", "price": 24300, "volume": 143000},
    {"date": "2026-06-13", "price": 24990, "volume": 171000},
    {"date": "2026-06-14", "price": 25100, "volume": 168000},
]

# Loop through and print each day nicely
for day in market_data:
    print(day["date"], "| Price:", day["price"], "| Volume:", day["volume"])

    # Function that analyses a day's data and returns a signal
def analyse_day(day, target):
    price = day["price"]
    date = day["date"]
    signal = ""
    
    if price > target:
        signal = "BUY"
    else:
        signal = "HOLD"
    
    return {"date": date, "price": price, "signal": signal}

# Run analysis on all days and store results
target_price = 24800
results = []

for day in market_data:
    result = analyse_day(day, target_price)
    results.append(result)

# Print final results
print("\n--- TRADING SIGNALS ---")
for result in results:
    print(result["date"], "| Price:", result["price"], "| Signal:", result["signal"])