# ============================================
# NIFTY 50 Signal Dashboard
# Author: Vihaan Jain
# Purpose: Web app that shows live signals
#          and sends email alerts
# ============================================

from flask import Flask, render_template_string
from signal_checker import get_signal
from datetime import datetime

app = Flask(__name__)

# Store signal history
signal_history = []

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>NIFTY Signal Dashboard</title>
    <meta http-equiv="refresh" content="3600">
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #0d1117;
            color: #e6edf3;
            margin: 0;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 20px;
            border-bottom: 1px solid #30363d;
        }
        .header h1 {
            color: #58a6ff;
            font-size: 2em;
            margin: 0;
        }
        .header p {
            color: #8b949e;
            margin: 5px 0 0 0;
        }
        .signal-box {
            text-align: center;
            padding: 40px;
            margin: 30px auto;
            max-width: 400px;
            border-radius: 12px;
            font-size: 2em;
            font-weight: bold;
        }
        .signal-long {
            background: #1a4731;
            border: 2px solid #2ea043;
            color: #3fb950;
        }
        .signal-short {
            background: #4a1a1a;
            border: 2px solid #f85149;
            color: #f85149;
        }
        .signal-hold {
            background: #1c2128;
            border: 2px solid #8b949e;
            color: #8b949e;
        }
        .price-box {
            text-align: center;
            font-size: 2.5em;
            font-weight: bold;
            color: #58a6ff;
            margin: 20px 0;
        }
        .indicators {
            display: flex;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
            margin: 20px auto;
            max-width: 800px;
        }
        .indicator-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 15px 25px;
            text-align: center;
            min-width: 120px;
        }
        .indicator-card .label {
            color: #8b949e;
            font-size: 0.85em;
            margin-bottom: 5px;
        }
        .indicator-card .value {
            color: #e6edf3;
            font-size: 1.3em;
            font-weight: bold;
        }
        .conditions {
            max-width: 500px;
            margin: 20px auto;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
        }
        .condition-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #21262d;
        }
        .condition-row:last-child {
            border-bottom: none;
        }
        .pass { color: #3fb950; }
        .fail { color: #f85149; }
        .history {
            max-width: 700px;
            margin: 30px auto;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
        }
        .history h2 {
            color: #58a6ff;
            margin-top: 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th {
            color: #8b949e;
            text-align: left;
            padding: 8px;
            border-bottom: 1px solid #30363d;
        }
        td {
            padding: 8px;
            border-bottom: 1px solid #21262d;
        }
        .refresh-btn {
            display: block;
            margin: 20px auto;
            padding: 12px 30px;
            background: #238636;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 1em;
            cursor: pointer;
            text-decoration: none;
            width: fit-content;
        }
        .refresh-btn:hover {
            background: #2ea043;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🇮🇳 NIFTY 50 Signal Dashboard</h1>
        <p>Last updated: {{ last_updated }}</p>
    </div>

    <div class="price-box">₹{{ price }}</div>

    <div class="signal-box {{ signal_class }}">
        {{ signal }}
    </div>

    <div class="indicators">
        <div class="indicator-card">
            <div class="label">MA20</div>
            <div class="value">{{ ma20 }}</div>
        </div>
        <div class="indicator-card">
            <div class="label">MA100</div>
            <div class="value">{{ ma100 }}</div>
        </div>
        <div class="indicator-card">
            <div class="label">MA400</div>
            <div class="value">{{ ma400 }}</div>
        </div>
        <div class="indicator-card">
            <div class="label">RSI</div>
            <div class="value">{{ rsi }}</div>
        </div>
        <div class="indicator-card">
            <div class="label">ADX</div>
            <div class="value">{{ adx }}</div>
        </div>
    </div>

    <div class="conditions">
        <div class="condition-row">
            <span>Trend</span>
            <span class="{{ 'pass' if trend_ok else 'fail' }}">{{ trend_label }}</span>
        </div>
        <div class="condition-row">
            <span>Choppy Market</span>
            <span class="{{ 'pass' if not_choppy else 'fail' }}">{{ 'Clear ✅' if not_choppy else 'Choppy ❌' }}</span>
        </div>
        <div class="condition-row">
            <span>Recovering from crash</span>
            <span class="{{ 'pass' if not_recovering else 'fail' }}">{{ 'No ✅' if not_recovering else 'Yes ❌' }}</span>
        </div>
        <div class="condition-row">
            <span>RSI Zone</span>
            <span class="{{ 'pass' if rsi_ok else 'fail' }}">{{ 'Good ✅' if rsi_ok else 'Outside zone ❌' }}</span>
        </div>
        <div class="condition-row">
            <span>Candle Pattern</span>
            <span class="{{ 'pass' if candle_ok else 'fail' }}">{{ candle_label }}</span>
        </div>
    </div>

    <a href="/refresh" class="refresh-btn">🔄 Refresh Signal</a>

    <div class="history">
        <h2>📋 Signal History</h2>
        <table>
            <tr>
                <th>Time</th>
                <th>Price</th>
                <th>Signal</th>
            </tr>
            {% for entry in history %}
            <tr>
                <td>{{ entry.time }}</td>
                <td>₹{{ entry.price }}</td>
                <td>{{ entry.signal }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
"""

def get_full_data():
    import yfinance as yf
    import pandas as pd

    nifty = yf.download("^NSEI", period="6mo", interval="1h", progress=False)
    nifty.columns = nifty.columns.get_level_values(0)

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

    row = nifty.iloc[-1]
    prev_row = nifty.iloc[-2]
    prev2_row = nifty.iloc[-3]

    close_val = round(float(row["Close"]), 2)
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
    open_prev = float(prev_row["Open"])
    close_prev = float(prev_row["Close"])
    high_prev = float(prev_row["High"])
    low_prev = float(prev_row["Low"])
    open_prev2 = float(prev2_row["Open"])
    close_prev2 = float(prev2_row["Close"])

    last10 = nifty.iloc[-11:-1]
    last20 = nifty.iloc[-21:-1]

    ma20_crosses = 0
    for i in range(1, len(last10)):
        pc = float(last10["Close"].iloc[i-1])
        cc = float(last10["Close"].iloc[i])
        pm = float(last10["MA20"].iloc[i-1])
        cm = float(last10["MA20"].iloc[i])
        if (pc < pm and cc > cm) or (pc > pm and cc < cm):
            ma20_crosses += 1

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
    swing_meaningful = swing_range > close_val * 0.01
    not_choppy = adx_strong and ma_separated and not_oscillating and atr_justified and swing_meaningful

    last20_lows = last20["Low"].values
    early_low = float(last20_lows[:10].mean())
    recent_low = float(last20_lows[10:].mean())
    not_recovering = recent_low <= early_low * 1.005

    body = abs(close_curr - open_curr)
    lower_wick = min(close_curr, open_curr) - low_curr
    upper_wick = high_curr - max(close_curr, open_curr)
    body_prev = abs(close_prev - open_prev)
    body_prev2 = abs(close_prev2 - open_prev2)

    bullish_engulfing = (close_prev < open_prev and close_curr > open_curr and close_curr > open_prev and open_curr < close_prev)
    hammer = (body > 0 and lower_wick >= 2 * body and upper_wick <= 0.3 * body)
    midpoint_prev2 = (open_prev2 + close_prev2) / 2
    morning_star = (close_prev2 < open_prev2 and body_prev < body_prev2 * 0.3 and close_curr > open_curr and close_curr > midpoint_prev2 and body > body_prev2 * 0.5)
    tweezer_bottom = (close_prev < open_prev and close_curr > open_curr and abs(low_curr - low_prev) <= 0.001 * low_prev)
    bearish_engulfing = (close_prev > open_prev and close_curr < open_curr and close_curr < open_prev and open_curr > close_prev)
    shooting_star = (body > 0 and upper_wick >= 2 * body and lower_wick <= 0.3 * body)
    midpoint_prev2_bear = (open_prev2 + close_prev2) / 2
    evening_star = (close_prev2 > open_prev2 and body_prev < body_prev2 * 0.3 and close_curr < open_curr and close_curr < midpoint_prev2_bear and body > body_prev2 * 0.5)
    tweezer_top = (close_prev > open_prev and close_curr < open_curr and abs(high_curr - high_prev) <= 0.001 * high_prev)

    good_candle = bullish_engulfing or hammer or morning_star or tweezer_bottom or (close_curr > open_curr)
    bad_candle = bearish_engulfing or shooting_star or evening_star or tweezer_top or (close_curr < open_curr)
    no_upper_wick_rejection = upper_wick <= 1.5 * body
    no_lower_wick_rejection = lower_wick <= 1.5 * body if body > 0 else True

    ma_signal = ma20 > ma100
    uptrend = close_val > ma400 and ma100 > ma400
    good_rsi = 20 < rsi < 65
    price_above_ma20 = close_val > ma20
    ma_signal_short = ma20 < ma100
    downtrend = close_val < ma400 and ma100 < ma400
    bad_rsi = 35 < rsi < 75
    price_below_ma20 = close_val < ma20

    if ma_signal and uptrend and good_rsi and price_above_ma20 and good_candle and no_upper_wick_rejection and not_choppy:
        signal = "🟢 LONG BUY"
        signal_class = "signal-long"
    elif ma_signal_short and downtrend and bad_rsi and price_below_ma20 and bad_candle and no_lower_wick_rejection and not_choppy and not_recovering:
        signal = "🔴 SHORT"
        signal_class = "signal-short"
    else:
        signal = "⚪ HOLD"
        signal_class = "signal-hold"

    if uptrend:
        trend_label = "Uptrend ✅"
        trend_ok = True
    elif downtrend:
        trend_label = "Downtrend ✅"
        trend_ok = True
    else:
        trend_label = "Neutral ⚪"
        trend_ok = False

    rsi_ok = good_rsi or bad_rsi
    candle_ok = good_candle or bad_candle
    candle_label = "Bullish ✅" if good_candle else "Bearish ✅" if bad_candle else "Neutral ⚪"

    return {
        "price": close_val,
        "ma20": ma20,
        "ma100": ma100,
        "ma400": ma400,
        "rsi": rsi,
        "adx": adx,
        "signal": signal,
        "signal_class": signal_class,
        "trend_label": trend_label,
        "trend_ok": trend_ok,
        "not_choppy": not_choppy,
        "not_recovering": not_recovering,
        "rsi_ok": rsi_ok,
        "candle_ok": candle_ok,
        "candle_label": candle_label,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M IST")
    }

@app.route("/")
def dashboard():
    data = get_full_data()
    signal_history.append({
        "time": datetime.now().strftime("%H:%M"),
        "price": data["price"],
        "signal": data["signal"]
    })
    return render_template_string(HTML_TEMPLATE, history=list(reversed(signal_history)), **data)

@app.route("/refresh")
def refresh():
    from flask import redirect
    return redirect("/")

if __name__ == "__main__":
    print("Starting NIFTY Signal Dashboard...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=False, port=5000)