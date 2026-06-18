# My Trading Algo Project - Day 1

# Variables
stock_name = "Nifty"
stock_price = 24500
purchase_quantity = 10

#Basic Calculation
total_value = stock_price * purchase_quantity
print("Stock:" , stock_name)
print("Price per unit:" , stock_price)
print("Total value of holdings:" , total_value )
print("Double quantity value", stock_price * purchase_quantity * 2)

#Simple Condition
if stock_price > 20000 :
    print("This is a high value stock")
else:
    print("This is a lower value stock")

# A list of NIFTY closing prices over 5 days

prices = [24500, 24820, 24300, 24990, 25100]
print ("All prices:", prices)
print ("Day 1 price", prices[0])
print ("Last day price", prices[-1])

# Loop and flag if price is above 25000
for price in prices:
    if price > 25000:
        print (price, "is above target")
    else:
        print (price, "is below target")

# A function that checks if we should buy a stock
def should_buy(price, target):
    if price > target:
        print (price, " - BUY SIGNAL")
    else:
        print (price, " - NO SIGNAL")

for price in prices :
    should_buy(price, 25000)

# A function that RETURNS a signal instead of just printing it
def get_signal(price, target) :
    if price > target:
        return"BUY"
    else:
        return"HOLD"
#store and use the returned value
signals = []
for price in prices :
    signal = get_signal(price, 25000)
    signals.append(signal)
print("Signals Generated", signals)
