# ============================================
# NIFTY 50 Signal Dashboard
# Author: Vihaan Jain
# Purpose: Web app that shows live signals
#          and sends email alerts
# ============================================
from flask import Flask, render_template_string, redirect
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd
from paper_trader import execute_trade, get_portfolio_status
from stock_scanner import scan_all_stocks, STOCKS, calculate_indicators

app = Flask(__name__)

# Store signal history and last signal
signal_history = []
last_signal = "⚪ HOLD"

# Email settings
import os
EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER", "")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>NIFTY Signal Dashboard</title>
    <meta http-equiv="refresh" content="3600">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; background: #0d1117; color: #e6edf3; margin: 0; padding: 20px; }
        .header { text-align: center; padding: 20px; border-bottom: 1px solid #30363d; }
        .header h1 { color: #58a6ff; font-size: 2em; margin: 0; }
        .header p { color: #8b949e; margin: 5px 0 0 0; }
        .nav { text-align: center; margin: 15px 0; }
        .nav a { color: #58a6ff; text-decoration: none; margin: 0 15px; font-size: 1.1em; }
        .nav a:hover { text-decoration: underline; }
        .signal-box { text-align: center; padding: 40px; margin: 30px auto; max-width: 400px; border-radius: 12px; font-size: 2em; font-weight: bold; }
        .signal-long { background: #1a4731; border: 2px solid #2ea043; color: #3fb950; }
        .signal-short { background: #4a1a1a; border: 2px solid #f85149; color: #f85149; }
        .signal-hold { background: #1c2128; border: 2px solid #8b949e; color: #8b949e; }
        .price-box { text-align: center; font-size: 2.5em; font-weight: bold; color: #58a6ff; margin: 20px 0; }
        .indicators { display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; margin: 20px auto; max-width: 800px; }
        .indicator-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px 25px; text-align: center; min-width: 120px; }
        .indicator-card .label { color: #8b949e; font-size: 0.85em; margin-bottom: 5px; }
        .indicator-card .value { color: #e6edf3; font-size: 1.3em; font-weight: bold; }
        .conditions { max-width: 500px; margin: 20px auto; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }
        .condition-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #21262d; }
        .condition-row:last-child { border-bottom: none; }
        .pass { color: #3fb950; }
        .fail { color: #f85149; }
        .chart-container { max-width: 900px; margin: 30px auto; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }
        .history { max-width: 700px; margin: 30px auto; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }
        .history h2 { color: #58a6ff; margin-top: 0; }
        table { width: 100%; border-collapse: collapse; }
        th { color: #8b949e; text-align: left; padding: 8px; border-bottom: 1px solid #30363d; }
        td { padding: 8px; border-bottom: 1px solid #21262d; }
        .refresh-btn { display: block; margin: 20px auto; padding: 12px 30px; background: #238636; color: white; border: none; border-radius: 6px; font-size: 1em; cursor: pointer; text-decoration: none; width: fit-content; }
        .refresh-btn:hover { background: #2ea043; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🇮🇳 NIFTY 50 Signal Dashboard</h1>
        <p>Last updated: {{ last_updated }}</p>
    </div>

    <div class="nav">
        <a href="/"> NIFTY Dashboard</a>
    </div>

    <div class="price-box">₹{{ price }}</div>
    <div class="signal-box {{ signal_class }}">{{ signal }}</div>

    <div class="indicators">
        <div class="indicator-card"><div class="label">MA20</div><div class="value">{{ ma20 }}</div></div>
        <div class="indicator-card"><div class="label">MA100</div><div class="value">{{ ma100 }}</div></div>
        <div class="indicator-card"><div class="label">MA400</div><div class="value">{{ ma400 }}</div></div>
        <div class="indicator-card"><div class="label">RSI</div><div class="value">{{ rsi }}</div></div>
        <div class="indicator-card"><div class="label">ADX</div><div class="value">{{ adx }}</div></div>
    </div>

    <div class="conditions">
        <div class="condition-row"><span>Trend</span><span class="{{ 'pass' if trend_ok else 'fail' }}">{{ trend_label }}</span></div>
        <div class="condition-row"><span>Choppy Market</span><span class="{{ 'pass' if not_choppy else 'fail' }}">{{ 'Clear ✅' if not_choppy else 'Choppy ❌' }}</span></div>
        <div class="condition-row"><span>Recovering from crash</span><span class="{{ 'pass' if not_recovering else 'fail' }}">{{ 'No ✅' if not_recovering else 'Yes ❌' }}</span></div>
        <div class="condition-row"><span>RSI Zone</span><span class="{{ 'pass' if rsi_ok else 'fail' }}">{{ 'Good ✅' if rsi_ok else 'Outside zone ❌' }}</span></div>
        <div class="condition-row"><span>Candle Pattern</span><span class="{{ 'pass' if candle_ok else 'fail' }}">{{ candle_label }}</span></div>
    </div>

    <div class="chart-container"><div id="chart"></div></div>

    <a href="/refresh" class="refresh-btn">🔄 Refresh Signal</a>

    <div class="history">
        <h2>💼 Paper Trading Portfolio</h2>
        <div style="display:flex; gap:20px; flex-wrap:wrap; margin-bottom:20px;">
            <div class="indicator-card">
                <div class="label">Portfolio Value</div>
                <div class="value" style="color: {{ '#3fb950' if portfolio.total_pnl >= 0 else '#f85149' }}">₹{{ portfolio.portfolio_value }}</div>
            </div>
            <div class="indicator-card">
                <div class="label">Total P&L</div>
                <div class="value" style="color: {{ '#3fb950' if portfolio.total_pnl >= 0 else '#f85149' }}">₹{{ portfolio.total_pnl }}</div>
            </div>
            <div class="indicator-card">
                <div class="label">Return</div>
                <div class="value" style="color: {{ '#3fb950' if portfolio.total_return >= 0 else '#f85149' }}">{{ portfolio.total_return }}%</div>
            </div>
            <div class="indicator-card">
                <div class="label">Win Rate</div>
                <div class="value">{{ portfolio.win_rate }}%</div>
            </div>
        </div>
        {% if portfolio.position %}
        <div style="background:#1a4731; border:1px solid #2ea043; border-radius:8px; padding:15px; margin-bottom:20px;">
            <strong style="color:#3fb950">Open Position: {{ portfolio.position.direction }}</strong><br>
            Entry: ₹{{ portfolio.position.entry_price }} | Units: {{ portfolio.position.units }} |
            Unrealised P&L: <span style="color: {{ '#3fb950' if portfolio.unrealised_pnl >= 0 else '#f85149' }}">₹{{ portfolio.unrealised_pnl }}</span>
        </div>
        {% else %}
        <div style="background:#1c2128; border:1px solid #30363d; border-radius:8px; padding:15px; margin-bottom:20px;">
            <span style="color:#8b949e">No open position</span>
        </div>
        {% endif %}
        <table>
            <tr><th>Time</th><th>Type</th><th>Direction</th><th>Price</th><th>P&L</th></tr>
            {% for trade in portfolio.trade_history %}
            <tr>
                <td>{{ trade.timestamp }}</td>
                <td>{{ trade.type }}</td>
                <td>{{ trade.direction }}</td>
                <td>₹{{ trade.entry_price if trade.type == 'OPEN' else trade.exit_price }}</td>
                <td>{{ '₹' + trade.pnl|string if trade.type == 'CLOSE' else '-' }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>

    <div class="history">
        <h2>📋 Signal History</h2>
        <table>
            <tr><th>Time</th><th>Price</th><th>Signal</th></tr>
            {% for entry in history %}
            <tr>
                <td>{{ entry.time }}</td>
                <td>₹{{ entry.price }}</td>
                <td>{{ entry.signal }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>

    <script>
        var chartData = {{ chart_json | safe }};
        Plotly.newPlot('chart', chartData.data, chartData.layout);
    </script>
</body>
</html>
"""

STOCKS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Stock Scanner</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; background: #0d1117; color: #e6edf3; margin: 0; padding: 20px; }
        .header { text-align: center; padding: 20px; border-bottom: 1px solid #30363d; }
        .header h1 { color: #58a6ff; font-size: 2em; margin: 0; }
        .header p { color: #8b949e; margin: 5px 0 0 0; }
        .nav { text-align: center; margin: 15px 0; }
        .nav a { color: #58a6ff; text-decoration: none; margin: 0 15px; font-size: 1.1em; }
        .stocks-grid { display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; margin: 30px auto; max-width: 1100px; }
        .stock-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 25px; min-width: 300px; flex: 1; }
        .stock-card.buy { border-color: #2ea043; }
        .stock-card.short { border-color: #f85149; }
        .stock-card.hold { border-color: #30363d; }
        .stock-name { font-size: 1.2em; font-weight: bold; margin-bottom: 5px; }
        .stock-price { font-size: 1.8em; font-weight: bold; color: #58a6ff; margin-bottom: 10px; }
        .signal-badge { display: inline-block; padding: 6px 16px; border-radius: 20px; font-weight: bold; margin-bottom: 15px; }
        .signal-badge.buy { background: #1a4731; color: #3fb950; }
        .signal-badge.short { background: #4a1a1a; color: #f85149; }
        .signal-badge.hold { background: #1c2128; color: #8b949e; }
        .section-title { color: #58a6ff; font-weight: bold; margin: 15px 0 8px 0; font-size: 0.95em; }
        .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        .grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
        .ind { background: #0d1117; border-radius: 8px; padding: 10px; text-align: center; }
        .ind .label { color: #8b949e; font-size: 0.75em; margin-bottom: 3px; }
        .ind .value { color: #e6edf3; font-size: 1em; font-weight: bold; }
        .green { color: #3fb950; }
        .red { color: #f85149; }
        .orange { color: #f0883e; }
        .divider { border: none; border-top: 1px solid #21262d; margin: 12px 0; }
        .analyst-box { background: #0d1117; border-radius: 8px; padding: 12px; text-align: center; margin-top: 10px; }
        .refresh-btn { display: block; margin: 20px auto; padding: 12px 30px; background: #238636; color: white; border: none; border-radius: 6px; font-size: 1em; cursor: pointer; text-decoration: none; width: fit-content; }
        .warning { font-size: 0.75em; color: #8b949e; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Stock Scanner</h1>
        <p>Last updated: {{ last_updated }}</p>
    </div>

    <div class="nav">
        <a href="/">🇮🇳 NIFTY Dashboard</a>
        <a href="/stocks">📊 Stock Scanner</a>
    </div>

    <div class="stocks-grid">
        {% for name, d in results.items() %}
        {% set sc = 'buy' if 'BUY' in d.signal else 'short' if 'SHORT' in d.signal else 'hold' %}
        {% set idx = loop.index %}
        <div class="stock-card {{ sc }}">

            <div class="stock-name">{{ name }}</div>
            <div class="stock-price">₹{{ d.price }}</div>
            <span class="signal-badge {{ sc }}">{{ d.signal }}</span>

            <hr class="divider">
            <div class="section-title">📊 Technical Indicators</div>
            <div class="grid3">
                <div class="ind">
                    <div class="label">RSI</div>
                    <div class="value" style="color: {{ '#f85149' if d.rsi and d.rsi > 70 else '#3fb950' if d.rsi and d.rsi < 30 else '#e6edf3' }}">{{ d.rsi or 'N/A' }}</div>
                </div>
                <div class="ind">
                    <div class="label">ADX</div>
                    <div class="value" style="color: {{ '#3fb950' if d.adx and d.adx > 25 else '#f85149' }}">{{ d.adx or 'N/A' }}</div>
                </div>
                <div class="ind">
                    <div class="label">Trend</div>
                    <div class="value">{{ '📈' if d.uptrend else '📉' if d.downtrend else '➡️' }}</div>
                </div>
                <div class="ind"><div class="label">MA10</div><div class="value">{{ d.ma10 or 'N/A' }}</div></div>
                <div class="ind"><div class="label">MA50</div><div class="value">{{ d.ma50 or 'N/A' }}</div></div>
                <div class="ind"><div class="label">MA200</div><div class="value">{{ d.ma200 or 'N/A' }}</div></div>
            </div>

            <hr class="divider">
            <div class="section-title">📅 52 Week Range</div>
            <div class="grid2">
                <div class="ind">
                    <div class="label">52W High</div>
                    <div class="value red">₹{{ d.week52_high or 'N/A' }}</div>
                    <div class="warning">{{ d.pct_from_52h or 'N/A' }}% from high</div>
                </div>
                <div class="ind">
                    <div class="label">52W Low</div>
                    <div class="value green">₹{{ d.week52_low or 'N/A' }}</div>
                    <div class="warning">+{{ d.pct_from_52l or 'N/A' }}% from low</div>
                </div>
                <div class="ind"><div class="label">Support</div><div class="value green">₹{{ d.support or 'N/A' }}</div></div>
                <div class="ind"><div class="label">Resistance</div><div class="value red">₹{{ d.resistance or 'N/A' }}</div></div>
            </div>

            <hr class="divider">
            <div class="section-title">💰 Fundamental Analysis</div>
            <div class="grid3">
                <div class="ind"><div class="label">P/E Ratio</div><div class="value">{{ d.pe_ratio or 'N/A' }}</div></div>
                <div class="ind"><div class="label">Forward P/E</div><div class="value">{{ d.forward_pe or 'N/A' }}</div></div>
                <div class="ind"><div class="label">EPS</div><div class="value">{{ d.eps or 'N/A' }}</div></div>
                <div class="ind"><div class="label">P/B Ratio</div><div class="value">{{ d.pb_ratio or 'N/A' }}</div></div>
                <div class="ind">
                    <div class="label">ROE %</div>
                    <div class="value" style="color: {{ '#3fb950' if d.roe and d.roe > 15 else '#f85149' if d.roe and d.roe < 10 else '#e6edf3' }}">{{ d.roe or 'N/A' }}%</div>
                </div>
                <div class="ind">
                    <div class="label">D/E Ratio</div>
                    <div class="value" style="color: {{ '#3fb950' if d.debt_to_equity and d.debt_to_equity < 1 else '#f85149' }}">{{ d.debt_to_equity or 'N/A' }}</div>
                </div>
                <div class="ind">
                    <div class="label">Rev Growth</div>
                    <div class="value" style="color: {{ '#3fb950' if d.revenue_growth and d.revenue_growth > 0 else '#f85149' }}">{{ d.revenue_growth or 'N/A' }}%</div>
                </div>
                <div class="ind">
                    <div class="label">EPS Growth</div>
                    <div class="value" style="color: {{ '#3fb950' if d.earnings_growth and d.earnings_growth > 0 else '#f85149' }}">{{ d.earnings_growth or 'N/A' }}%</div>
                </div>
                <div class="ind"><div class="label">Dividend</div><div class="value orange">{{ d.dividend_yield or '0' }}%</div></div>
            </div>
            <div class="ind" style="margin-top:8px;">
                <div class="label">Market Cap</div>
                <div class="value">₹{{ d.market_cap_cr or 'N/A' }} Cr</div>
            </div>

            <hr class="divider">
            <div class="section-title">🎯 Price Projections</div>
            <div class="warning" style="margin-bottom:8px;">⚠️ Based on momentum trend — not a guarantee</div>
            <div class="grid2">
                <div class="ind">
                    <div class="label">3 Month Target</div>
                    <div class="value" style="color: {{ '#3fb950' if d.projection_3m_pct and d.projection_3m_pct > 0 else '#f85149' }}">₹{{ d.projection_3m or 'N/A' }}</div>
                    <div class="warning">{{ d.projection_3m_pct or 'N/A' }}%</div>
                </div>
                <div class="ind">
                    <div class="label">6 Month Target</div>
                    <div class="value" style="color: {{ '#3fb950' if d.projection_6m_pct and d.projection_6m_pct > 0 else '#f85149' }}">₹{{ d.projection_6m or 'N/A' }}</div>
                    <div class="warning">{{ d.projection_6m_pct or 'N/A' }}%</div>
                </div>
                <div class="ind">
                    <div class="label">3M Range</div>
                    <div class="value" style="font-size:0.85em;">₹{{ d.range_3m_low or 'N/A' }} — ₹{{ d.range_3m_high or 'N/A' }}</div>
                </div>
                <div class="ind">
                    <div class="label">6M Range</div>
                    <div class="value" style="font-size:0.85em;">₹{{ d.range_6m_low or 'N/A' }} — ₹{{ d.range_6m_high or 'N/A' }}</div>
                </div>
            </div>

            {% if d.chart_json %}
            <hr class="divider">
            <div class="section-title">📈 Price History + Projections</div>
            <div id="stockchart_{{ loop.index }}"></div>
            <script>
                window.addEventListener('load', function() {
                    var chartData = {{ d.chart_json | safe }};
                    Plotly.newPlot('stockchart_{{ loop.index }}', chartData.data, chartData.layout);
                });
            </script>
            {% endif %}

            {% if d.analyst_target %}
            <div class="analyst-box">
                <div style="color:#8b949e; font-size:0.8em;">Analyst Consensus</div>
                <div style="color:#f0883e; font-weight:bold; font-size:1.2em;">₹{{ d.analyst_target }}</div>
                <div style="color: {{ '#3fb950' if d.analyst_upside and d.analyst_upside > 0 else '#f85149' }}">{{ d.analyst_upside or 'N/A' }}% upside</div>
                <div style="color:#8b949e; font-size:0.85em; margin-top:4px;">Recommendation: <strong style="color:#58a6ff">{{ d.analyst_recommendation }}</strong></div>
            </div>
            {% endif %}

        </div>
        {% endfor %}
    </div>

    <a href="/stocks" class="refresh-btn">🔄 Refresh Scan</a>

</body>
</html>
"""

def send_email_alert(signal, price):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg["Subject"] = f"NIFTY Signal Alert: {signal}"
    body = f"""
    NIFTY 50 Signal Alert
    Signal: {signal}
    Price: ₹{price}
    Time: {datetime.now().strftime('%Y-%m-%d %H:%M IST')}
    Open your dashboard: http://127.0.0.1:5000
    """
    msg.attach(MIMEText(body, "plain"))
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
        print(f"Email alert sent: {signal}")
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False

def generate_chart():
    nifty = yf.download("^NSEI", period="3mo", interval="1d", progress=False)
    nifty.columns = nifty.columns.get_level_values(0)
    nifty["MA20"] = nifty["Close"].rolling(window=10).mean()
    nifty["MA100"] = nifty["Close"].rolling(window=50).mean()
    dates = nifty.index.strftime("%Y-%m-%d").tolist()
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=dates, open=nifty["Open"].tolist(), high=nifty["High"].tolist(),
        low=nifty["Low"].tolist(), close=nifty["Close"].tolist(),
        name="NIFTY 50", increasing_line_color="#3fb950", decreasing_line_color="#f85149"
    ))
    fig.add_trace(go.Scatter(x=dates, y=nifty["MA20"].tolist(), name="MA10", line=dict(color="#58a6ff", width=1.5)))
    fig.add_trace(go.Scatter(x=dates, y=nifty["MA100"].tolist(), name="MA50", line=dict(color="#f0883e", width=1.5)))
    fig.update_layout(
        title="NIFTY 50 - Last 3 Months",
        paper_bgcolor="#0d1117", plot_bgcolor="#161b22",
        font=dict(color="#e6edf3"),
        xaxis=dict(gridcolor="#21262d", rangeslider=dict(visible=False), type="category"),
        yaxis=dict(gridcolor="#21262d"),
        legend=dict(bgcolor="#161b22", bordercolor="#30363d"),
        height=400
    )
    return fig.to_json()

def get_full_data():
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
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
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
        "price": close_val, "ma20": ma20, "ma100": ma100, "ma400": ma400,
        "rsi": rsi, "adx": adx, "signal": signal, "signal_class": signal_class,
        "trend_label": trend_label, "trend_ok": trend_ok, "not_choppy": not_choppy,
        "not_recovering": not_recovering, "rsi_ok": rsi_ok, "candle_ok": candle_ok,
        "candle_label": candle_label,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M IST")
    }

def scheduled_check():
    global last_signal
    print(f"\n[{datetime.now().strftime('%H:%M')}] Running scheduled signal check...")
    data = get_full_data()
    print(f"Signal: {data['signal']} | Price: ₹{data['price']}")
    if data["signal"] != last_signal:
        execute_trade(data["signal"], data["price"])
        if "BUY" in data["signal"] or "SHORT" in data["signal"]:
            send_email_alert(data["signal"], data["price"])
        last_signal = data["signal"]
    signal_history.append({
        "time": datetime.now().strftime("%H:%M"),
        "price": data["price"],
        "signal": data["signal"]
    })

@app.route("/")
def dashboard():
    global last_signal
    data = get_full_data()
    chart_json = generate_chart()
    portfolio = get_portfolio_status(data["price"])
    if data["signal"] != last_signal:
        execute_trade(data["signal"], data["price"])
        if "BUY" in data["signal"] or "SHORT" in data["signal"]:
            send_email_alert(data["signal"], data["price"])
        last_signal = data["signal"]
    signal_history.append({
        "time": datetime.now().strftime("%H:%M"),
        "price": data["price"],
        "signal": data["signal"]
    })
    return render_template_string(HTML_TEMPLATE,
                                 history=list(reversed(signal_history)),
                                 chart_json=chart_json,
                                 portfolio=portfolio,
                                 **data)

@app.route("/refresh")
def refresh():
    return redirect("/")

@app.route("/stocks")
def stocks_page():
    results = scan_all_stocks()
    return render_template_string(STOCKS_TEMPLATE, results=results,
                                 last_updated=datetime.now().strftime("%Y-%m-%d %H:%M IST"))

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_check, "interval", hours=1)
    scheduler.start()
    print("Scheduler started - checking signals every hour automatically")
    print("Starting NIFTY Signal Dashboard...")
    port = int(os.environ.get("NIFTYALGO_PORT", 5000))
    print(f"Open http://127.0.0.1:{port} in your browser")
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, port=port, host="0.0.0.0")
