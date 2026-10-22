"""
Paper trader with position sizing based on signal strength.

The algorithm gives every LONG/SHORT signal a strength score from 0 to 100.
The paper trader then risks only part of its capital:

    allocation = 20% + 60% x (strength / 100)      ->  between 20% and 80% of capital

so a weak signal uses a small position, a strong signal uses a larger one, and
the trader is never fully invested. Simulated costs of 0.03% per side are charged.

Educational paper trading only - not financial advice.
"""

import json
import os
import threading
from datetime import datetime

STARTING_CAPITAL = 100000.0
MIN_ALLOC = 0.20          # allocation at strength 0
MAX_ALLOC = 0.80          # allocation at strength 100
COST_PER_SIDE = 0.0003    # 0.03% per side

TRADES_FILE = os.environ.get(
    "PAPER_TRADES_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_trades.json"),
)
_lock = threading.Lock()


def allocation_pct(strength):
    """Percent of capital to use for a signal of this strength (0-100)."""
    s = max(0, min(100, float(strength or 0)))
    return round((MIN_ALLOC + (MAX_ALLOC - MIN_ALLOC) * s / 100) * 100, 1)


def _fresh():
    return {"starting_capital": STARTING_CAPITAL, "capital": STARTING_CAPITAL,
            "position": None, "trade_history": []}


def _load():
    if not os.path.exists(TRADES_FILE):
        return _fresh()
    try:
        with open(TRADES_FILE) as f:
            data = json.load(f)
        if all(k in data for k in ("starting_capital", "capital", "position", "trade_history")):
            return data
    except Exception:
        pass
    # Old or unreadable file: keep a backup and start fresh
    backup = TRADES_FILE.replace(".json", "_old.json")
    try:
        os.replace(TRADES_FILE, backup)
        print(f"Old paper-trading file moved to {backup}; starting a fresh portfolio.")
    except Exception:
        pass
    return _fresh()


def _save(data):
    with open(TRADES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _unrealised(position, price):
    if not position:
        return 0.0
    if position["direction"] == "LONG":
        return (price - position["entry_price"]) * position["units"]
    return (position["entry_price"] - price) * position["units"]


def _close(data, price, reason):
    pos = data["position"]
    gross = _unrealised(pos, price)
    costs = pos["invested"] * COST_PER_SIDE * 2          # entry + exit
    pnl = round(gross - costs, 2)
    data["capital"] = round(data["capital"] + pnl, 2)
    data["trade_history"].append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "type": "CLOSE", "direction": pos["direction"],
        "entry_price": pos["entry_price"], "exit_price": round(price, 2),
        "units": pos["units"], "invested": pos["invested"],
        "strength": pos.get("strength"), "pnl": pnl, "reason": reason,
    })
    data["position"] = None
    return pnl


def _open(data, direction, price, strength):
    alloc = allocation_pct(strength) / 100
    invested = round(data["capital"] * alloc, 2)
    units = round(invested / price, 4)
    data["position"] = {
        "direction": direction, "entry_price": round(price, 2), "units": units,
        "invested": invested, "strength": int(strength or 0),
        "alloc_pct": round(alloc * 100, 1),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    data["trade_history"].append({
        "timestamp": data["position"]["time"], "type": "OPEN", "direction": direction,
        "entry_price": round(price, 2), "exit_price": None, "units": units,
        "invested": invested, "strength": int(strength or 0), "pnl": None,
    })


def execute_trade(signal, price, strength=50):
    """Act on a signal string such as '🟢 LONG BUY', '🔴 SHORT' or '⚪ HOLD'."""
    with _lock:
        data = _load()
        pos = data["position"]
        if "BUY" in signal:
            want = "LONG"
        elif "SHORT" in signal:
            want = "SHORT"
        else:
            want = None

        msg = "No action"
        if want is None:
            if pos:
                pnl = _close(data, price, "SIGNAL")
                msg = f"Closed {pos['direction']} at {price} | P&L Rs{pnl}"
        elif pos and pos["direction"] == want:
            msg = f"Already {want}, no change"
        else:
            if pos:
                pnl = _close(data, price, "REVERSAL")
                print(f"Closed {pos['direction']} at {price} | P&L Rs{pnl}")
            _open(data, want, price, strength)
            p = data["position"]
            msg = (f"Opened {want} at {price} | strength {p['strength']}/100 | "
                   f"allocation {p['alloc_pct']}% = Rs{p['invested']}")
        _save(data)
        print(msg)
        return msg


def get_portfolio_status(price):
    with _lock:
        data = _load()
    pos = data["position"]
    unrealised = round(_unrealised(pos, price), 2)
    value = round(data["capital"] + unrealised, 2)
    closed = [t for t in data["trade_history"] if t["type"] == "CLOSE"]
    wins = [t for t in closed if t["pnl"] > 0]
    total_pnl = round(value - data["starting_capital"], 2)
    return {
        "portfolio_value": value,
        "total_pnl": total_pnl,
        "total_return": round(total_pnl / data["starting_capital"] * 100, 2),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "closed_trades": len(closed),
        "cash_capital": data["capital"],
        "position": pos,
        "unrealised_pnl": unrealised,
        "trade_history": list(reversed(data["trade_history"])),
    }