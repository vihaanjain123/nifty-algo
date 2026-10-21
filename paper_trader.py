# ============================================
# NIFTY 50 Paper Trading Engine
# Author: Vihaan Jain
# Purpose: Simulates real trades based on
#          algo signals without real money
# ============================================

import json
import os
from datetime import datetime

TRADE_LOG_FILE = "paper_trades.json"
STARTING_CAPITAL = 100000

def load_trades():
    if os.path.exists(TRADE_LOG_FILE):
        with open(TRADE_LOG_FILE, "r") as f:
            return json.load(f)
    return {
        "capital": STARTING_CAPITAL,
        "position": None,
        "trades": []
    }

def save_trades(data):
    with open(TRADE_LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def execute_trade(signal, price):
    data = load_trades()
    capital = data["capital"]
    position = data["position"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # If we have an open position, check if we should close it
    if position:
        current_signal_direction = "LONG" if "BUY" in signal else "SHORT" if "SHORT" in signal else "HOLD"
        position_direction = position["direction"]

        # Close position if signal reversed or is HOLD
        should_close = (
            signal == "⚪ HOLD" or
            (position_direction == "LONG" and "SHORT" in signal) or
            (position_direction == "SHORT" and "BUY" in signal)
        )

        if should_close:
            # Calculate P&L
            entry_price = position["entry_price"]
            units = position["units"]

            if position_direction == "LONG":
                pnl = round((price - entry_price) * units, 2)
            else:
                pnl = round((entry_price - price) * units, 2)

            capital = round(capital + pnl, 2)
            data["capital"] = capital

            # Log the closed trade
            closed_trade = {
                "type": "CLOSE",
                "direction": position_direction,
                "entry_price": entry_price,
                "exit_price": price,
                "units": units,
                "pnl": pnl,
                "capital_after": capital,
                "timestamp": timestamp
            }
            data["trades"].append(closed_trade)
            data["position"] = None
            position = None

            print(f"[PAPER TRADE] CLOSED {position_direction} | Entry: {entry_price} | Exit: {price} | P&L: ₹{pnl} | Capital: ₹{capital}")

    # Open new position if signal is actionable and no open position
    if not position and signal != "⚪ HOLD":
        direction = "LONG" if "BUY" in signal else "SHORT"
        units = round(capital / price, 4)

        new_position = {
            "direction": direction,
            "entry_price": price,
            "units": units,
            "entry_time": timestamp,
            "entry_capital": capital
        }

        data["position"] = new_position
        data["capital"] = 0  # capital is now in position

        # Log the opened trade
        opened_trade = {
            "type": "OPEN",
            "direction": direction,
            "entry_price": price,
            "units": units,
            "timestamp": timestamp
        }
        data["trades"].append(opened_trade)

        print(f"[PAPER TRADE] OPENED {direction} | Price: {price} | Units: {units} | Capital: ₹{capital}")

    save_trades(data)
    return data

def get_portfolio_status(current_price):
    data = load_trades()
    position = data["position"]
    capital = data["capital"]

    if position:
        entry_price = position["entry_price"]
        units = position["units"]
        direction = position["direction"]

        if direction == "LONG":
            unrealised_pnl = round((current_price - entry_price) * units, 2)
        else:
            unrealised_pnl = round((entry_price - current_price) * units, 2)

        portfolio_value = round(capital + (units * current_price), 2) if direction == "LONG" else round(capital + position["entry_capital"] + unrealised_pnl, 2)
    else:
        unrealised_pnl = 0
        portfolio_value = capital

    total_pnl = round(portfolio_value - STARTING_CAPITAL, 2)
    total_return = round((portfolio_value - STARTING_CAPITAL) / STARTING_CAPITAL * 100, 2)

    # Calculate win rate from closed trades
    closed_trades = [t for t in data["trades"] if t["type"] == "CLOSE"]
    winning_trades = [t for t in closed_trades if t["pnl"] > 0]
    win_rate = round(len(winning_trades) / len(closed_trades) * 100, 2) if closed_trades else 0

    return {
        "capital": capital,
        "portfolio_value": portfolio_value,
        "position": position,
        "unrealised_pnl": unrealised_pnl,
        "total_pnl": total_pnl,
        "total_return": total_return,
        "total_trades": len(closed_trades),
        "win_rate": win_rate,
        "trade_history": list(reversed(data["trades"]))
    }

if __name__ == "__main__":
    # Test it
    print("Testing paper trader...")
    result = execute_trade("🟢 LONG BUY", 24000)
    print(f"Position opened: {result['position']}")
    status = get_portfolio_status(24200)
    print(f"Unrealised P&L: ₹{status['unrealised_pnl']}")
    print(f"Portfolio value: ₹{status['portfolio_value']}")