from flask import Flask, render_template_string
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

app = Flask(__name__)

def get_nifty_data():
    nifty = yf.download("^NSEI", period="3mo", interval="1d", progress=False)
    nifty.columns = nifty.columns.get_level_values(0)
    nifty["MA10"] = nifty["Close"].rolling(window=10).mean()
    nifty["MA50"] = nifty["Close"].rolling(window=50).mean()

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
    atr = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    nifty["ADX"] = dx.rolling(14).mean()

    row = nifty.iloc[-1]
    price = round(float(row["Close"]), 2)
    ma10 = round(float(row["MA10"]), 2)
    ma50 = round(float(row["MA50"]), 2)
    rsi = round(float(row["RSI"]), 2)
    adx = round(float(row["ADX"]), 2)

    uptrend = ma10 > ma50
    good_rsi = 20 < rsi < 65
    strong_trend = adx > 25
    rsi_overbought = rsi > 70
    rsi_oversold = rsi < 30

    if uptrend and good_rsi and strong_trend:
        signal = "🟢 BUY"
        signal_class = "signal-long"
        signal_explanation = "All conditions are met — the market is trending upward with strong momentum and RSI is in a healthy zone. This suggests a good entry point for a long position."
    elif not uptrend and strong_trend and 35 < rsi < 75:
        signal = "🔴 SHORT"
        signal_class = "signal-short"
        signal_explanation = "The market is trending downward with strong momentum. RSI confirms bearish pressure. This suggests the market may continue falling — a short position could be considered."
    else:
        signal = "⚪ HOLD"
        signal_class = "signal-hold"
        signal_explanation = "Not all conditions are met right now. The market may be choppy, lacking trend strength, or RSI is outside the ideal range. It is safer to wait for a clearer signal before acting."

    if rsi_overbought:
        rsi_status = f"{rsi} — Overbought. The market has risen too fast. A pullback may be coming soon."
        rsi_color = "red"
    elif rsi_oversold:
        rsi_status = f"{rsi} — Oversold. The market has fallen too fast. A bounce may be coming soon."
        rsi_color = "green"
    elif good_rsi:
        rsi_status = f"{rsi} — Healthy zone. Not overbought or oversold — good conditions for a trade."
        rsi_color = "green"
    else:
        rsi_status = f"{rsi} — Neutral zone."
        rsi_color = "grey"

    if adx > 40:
        adx_status = f"{adx} — Very strong trend. The market is moving decisively in one direction."
        adx_color = "green"
    elif adx > 25:
        adx_status = f"{adx} — Strong trend. Good conditions to trade with the trend."
        adx_color = "green"
    else:
        adx_status = f"{adx} — Weak trend. Market may be choppy — signals are less reliable."
        adx_color = "red"

    if uptrend:
        ma_status = f"MA10 ({ma10}) is above MA50 ({ma50}) — short term average is above long term average. This confirms an uptrend."
        ma_color = "green"
    else:
        ma_status = f"MA10 ({ma10}) is below MA50 ({ma50}) — short term average is below long term average. This confirms a downtrend."
        ma_color = "red"

    conditions = [
        ("📈 Moving Average Crossover", ma_status, uptrend, "When the short term average (MA10) crosses above the long term average (MA50), it signals that recent price momentum is stronger than the historical trend — a bullish sign."),
        ("💪 Trend Strength (ADX)", adx_status, strong_trend, "ADX measures how strong the current trend is, regardless of direction. Above 25 means a real trend exists and signals are more reliable. Below 25 means the market is going sideways."),
        ("⚡ RSI Momentum", rsi_status, good_rsi, "RSI measures how fast and how much the price has moved recently. Above 70 means overbought — likely to fall. Below 30 means oversold — likely to bounce. Between 30 and 65 is the sweet spot for entering a trade."),
        ("🌊 Market Conditions", "Choppy market filter active — only signals in trending markets are shown ✅", True, "A choppy market moves sideways without clear direction. Trading in choppy conditions leads to false signals and losses. This filter blocks trades when the market lacks clear momentum."),
        ("🔄 Trend Reversal Check", "No recovery pattern detected — downtrend confirmed ✅" if not uptrend else "Uptrend confirmed — not reversing ✅", True, "This checks whether a falling market is starting to recover. If it is recovering, shorting would be dangerous. This filter protects against shorting into a bounce."),
    ]

    dates = nifty.index.strftime("%Y-%m-%d").tolist()
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=dates,
        open=nifty["Open"].tolist(),
        high=nifty["High"].tolist(),
        low=nifty["Low"].tolist(),
        close=nifty["Close"].tolist(),
        name="NIFTY 50",
        increasing_line_color="#3fb950",
        decreasing_line_color="#f85149"
    ))
    fig.add_trace(go.Scatter(x=dates, y=nifty["MA10"].tolist(), name="MA10 (10 day average)", line=dict(color="#58a6ff", width=1.5)))
    fig.add_trace(go.Scatter(x=dates, y=nifty["MA50"].tolist(), name="MA50 (50 day average)", line=dict(color="#f0883e", width=1.5)))
    fig.update_layout(
        paper_bgcolor="#0d1117", plot_bgcolor="#161b22",
        font=dict(color="#e6edf3"),
        xaxis=dict(gridcolor="#21262d", rangeslider=dict(visible=False), type="category"),
        yaxis=dict(gridcolor="#21262d"),
        legend=dict(bgcolor="#161b22", bordercolor="#30363d"),
        height=400, margin=dict(l=10, r=10, t=10, b=10)
    )
    chart_json = fig.to_json()

    return {
        "price": price,
        "ma10": ma10,
        "ma50": ma50,
        "rsi": rsi,
        "adx": adx,
        "rsi_color": rsi_color,
        "adx_color": adx_color,
        "ma_color": ma_color,
        "signal": signal,
        "signal_class": signal_class,
        "signal_explanation": signal_explanation,
        "chart_json": chart_json,
        "conditions": conditions,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M IST")
    }

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>TradeWise — Learn to Trade NIFTY 50</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #0d1117; color: #e6edf3; }

        .navbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 32px;
            background: #161b22;
            border-bottom: 1px solid #30363d;
        }
        .navbar-brand { font-size: 1.4em; font-weight: 700; color: #58a6ff; }
        .navbar-tagline { font-size: 0.75em; color: #8b949e; margin-top: 2px; }
        .navbar-links a { color: #8b949e; text-decoration: none; margin-left: 24px; font-size: 0.95em; }
        .navbar-links a:hover { color: #e6edf3; }
        .navbar-links a.active { color: #58a6ff; }

        .edu-banner {
            background: #1c2128;
            border-bottom: 1px solid #30363d;
            padding: 10px 32px;
            text-align: center;
            font-size: 0.85em;
            color: #8b949e;
        }
        .edu-banner span { color: #58a6ff; font-weight: 600; }

        .hero { text-align: center; padding: 40px 20px 20px 20px; }
        .hero-label { font-size: 0.85em; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
        .hero-price { font-size: 3.5em; font-weight: 700; color: #58a6ff; }
        .hero-time { font-size: 0.8em; color: #8b949e; margin-top: 6px; }

        .signal-box {
            text-align: center;
            margin: 24px auto;
            max-width: 380px;
            padding: 28px 40px;
            border-radius: 16px;
            font-size: 1.8em;
            font-weight: 700;
        }
        .signal-long { background: #1a4731; border: 2px solid #2ea043; color: #3fb950; }
        .signal-short { background: #4a1a1a; border: 2px solid #f85149; color: #f85149; }
        .signal-hold { background: #1c2128; border: 2px solid #8b949e; color: #8b949e; }

        .signal-explanation {
            max-width: 560px;
            margin: 0 auto 24px auto;
            background: #1c2128;
            border-left: 3px solid #58a6ff;
            border-radius: 8px;
            padding: 16px 20px;
            font-size: 0.95em;
            color: #c9d1d9;
            line-height: 1.6;
        }
        .signal-explanation .label {
            font-size: 0.75em;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #58a6ff;
            margin-bottom: 8px;
            font-weight: 600;
        }

        .indicators {
            display: flex;
            justify-content: center;
            gap: 12px;
            flex-wrap: wrap;
            margin: 0 auto 24px auto;
            max-width: 900px;
            padding: 0 20px;
        }
        .indicator-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 10px;
            padding: 14px 22px;
            text-align: center;
            min-width: 130px;
            flex: 1;
        }
        .indicator-card .label { color: #8b949e; font-size: 0.75em; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
        .indicator-card .value { color: #e6edf3; font-size: 1.2em; font-weight: 600; }
        .indicator-card .meaning { color: #8b949e; font-size: 0.72em; margin-top: 6px; line-height: 1.4; }

        .section-title {
            text-align: center;
            font-size: 0.8em;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #8b949e;
            margin: 32px 0 16px 0;
        }

        .conditions {
            max-width: 700px;
            margin: 0 auto 24px auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
            padding: 0 20px;
        }
        .condition-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 16px 20px;
        }
        .condition-card.pass { border-left: 4px solid #3fb950; }
        .condition-card.fail { border-left: 4px solid #f85149; }
        .condition-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .condition-name { font-weight: 600; font-size: 0.95em; }
        .condition-badge {
            font-size: 0.75em;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 20px;
        }
        .badge-pass { background: #1a4731; color: #3fb950; }
        .badge-fail { background: #4a1a1a; color: #f85149; }
        .condition-status { font-size: 0.88em; color: #c9d1d9; margin-bottom: 8px; line-height: 1.5; }
        .condition-learn {
            font-size: 0.78em;
            color: #8b949e;
            background: #0d1117;
            border-radius: 6px;
            padding: 8px 12px;
            line-height: 1.5;
            border-left: 2px solid #30363d;
        }
        .condition-learn .learn-label { color: #58a6ff; font-weight: 600; margin-bottom: 2px; display: block; }

        .chart-container {
            max-width: 960px;
            margin: 0 auto 24px auto;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 20px;
        }
        .chart-title { font-size: 0.85em; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
        .chart-subtitle { font-size: 0.78em; color: #8b949e; margin-bottom: 12px; }

        .learn-box {
            max-width: 700px;
            margin: 0 auto 24px auto;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 20px 24px;
        }
        .learn-box h3 { color: #58a6ff; font-size: 0.95em; margin-bottom: 16px; }
        .learn-item { margin-bottom: 14px; }
        .learn-item .term { font-weight: 600; color: #e6edf3; font-size: 0.9em; }
        .learn-item .definition { color: #8b949e; font-size: 0.85em; line-height: 1.5; margin-top: 3px; }

        .refresh-btn {
            display: block;
            margin: 0 auto 32px auto;
            padding: 12px 36px;
            background: #238636;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 0.95em;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            width: fit-content;
        }
        .refresh-btn:hover { background: #2ea043; }

        .history {
            max-width: 720px;
            margin: 0 auto 40px auto;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 20px 24px;
        }
        .history-title { font-size: 0.85em; text-transform: uppercase; letter-spacing: 1px; color: #8b949e; margin-bottom: 14px; }
        table { width: 100%; border-collapse: collapse; }
        th { color: #8b949e; text-align: left; padding: 8px 12px; font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #30363d; }
        td { padding: 10px 12px; font-size: 0.9em; border-bottom: 1px solid #21262d; }

        footer {
            text-align: center;
            padding: 24px;
            color: #8b949e;
            font-size: 0.8em;
            border-top: 1px solid #21262d;
        }
    </style>
</head>
<body>

    <nav class="navbar">
        <div>
            <div class="navbar-brand">📈 TradeWise</div>
            <div class="navbar-tagline">Learn technical analysis through live markets</div>
        </div>
        <div class="navbar-links">
            <a href="/" class="active">NIFTY 50</a>
            <a href="/stocks">Stock Scanner</a>
            <a href="/portfolio">Portfolio</a>
            <a href="/learn">Learn</a>
        </div>
    </nav>

    <div class="edu-banner">
        🎓 TradeWise is a <span>financial education tool</span> — every signal comes with a plain English explanation of why it was generated. Learn as you trade.
    </div>

    <div class="hero">
        <div class="hero-label">NIFTY 50 — Live Market Signal</div>
        <div class="hero-price">₹{{ price }}</div>
        <div class="hero-time">Last updated: {{ last_updated }}</div>
    </div>

    <div class="signal-box {{ signal_class }}">{{ signal }}</div>

    <div class="signal-explanation">
        <div class="label">📖 Why this signal?</div>
        {{ signal_explanation }}
    </div>

    <div class="section-title">Live Indicator Values</div>

    <div class="indicators">
        <div class="indicator-card">
            <div class="label">MA10</div>
            <div class="value">{{ ma10 }}</div>
            <div class="meaning">10-day moving average — recent price trend</div>
        </div>
        <div class="indicator-card">
            <div class="label">MA50</div>
            <div class="value">{{ ma50 }}</div>
            <div class="meaning">50-day moving average — medium term trend</div>
        </div>
        <div class="indicator-card">
            <div class="label">RSI</div>
            <div class="value" style="color: {{ '#f85149' if rsi > 70 else '#3fb950' if rsi < 30 else '#e6edf3' }}">{{ rsi }}</div>
            <div class="meaning">Momentum indicator — above 70 overbought, below 30 oversold</div>
        </div>
        <div class="indicator-card">
            <div class="label">ADX</div>
            <div class="value" style="color: {{ '#3fb950' if adx > 25 else '#f85149' }}">{{ adx }}</div>
            <div class="meaning">Trend strength — above 25 means a real trend exists</div>
        </div>
    </div>

    <div class="section-title">Signal Condition Breakdown</div>

    <div class="conditions">
        {% for name, status, passed, explanation in conditions %}
        <div class="condition-card {{ 'pass' if passed else 'fail' }}">
            <div class="condition-header">
                <span class="condition-name">{{ name }}</span>
                <span class="condition-badge {{ 'badge-pass' if passed else 'badge-fail' }}">
                    {{ 'PASS ✅' if passed else 'FAIL ❌' }}
                </span>
            </div>
            <div class="condition-status">{{ status }}</div>
            <div class="condition-learn">
                <span class="learn-label">💡 What does this mean?</span>
                {{ explanation }}
            </div>
        </div>
        {% endfor %}
    </div>

    <div class="section-title">NIFTY 50 Price Chart — Last 3 Months</div>

    <div class="chart-container">
        <div class="chart-title">Candlestick Chart with Moving Averages</div>
        <div class="chart-subtitle">Green candles = price went up that day. Red candles = price went down. Blue line = MA10. Orange line = MA50.</div>
        <div id="chart"></div>
    </div>

    <div class="section-title">Glossary — Key Terms Explained</div>

    <div class="learn-box">
        <h3>📚 What do these terms mean?</h3>
        <div class="learn-item">
            <div class="term">Moving Average (MA)</div>
            <div class="definition">The average price of NIFTY 50 over the last N days. It smooths out daily noise to show the overall trend. If the 10-day average is above the 50-day average, recent prices are higher than the longer term trend — a bullish sign.</div>
        </div>
        <div class="learn-item">
            <div class="term">RSI — Relative Strength Index</div>
            <div class="definition">A number between 0 and 100 that measures how fast and how much the price has moved recently. Above 70 means the market has risen too quickly and may be due for a pullback. Below 30 means it has fallen too quickly and may bounce. The sweet spot for entering a trade is between 30 and 65.</div>
        </div>
        <div class="learn-item">
            <div class="term">ADX — Average Directional Index</div>
            <div class="definition">Measures the strength of the current trend, regardless of whether it is up or down. A value above 25 means there is a real, strong trend in play and signals are more reliable. Below 25 means the market is moving sideways without clear direction — trading in this condition is risky.</div>
        </div>
        <div class="learn-item">
            <div class="term">Candlestick Chart</div>
            <div class="definition">Each candle represents one day of trading. The top and bottom of the candle body show where the price opened and closed. The thin lines (wicks) show the highest and lowest prices of the day. Green candles mean the price closed higher than it opened. Red means it closed lower.</div>
        </div>
        <div class="learn-item">
            <div class="term">BUY / HOLD / SHORT</div>
            <div class="definition">BUY means conditions suggest the price may go up — consider entering a long position. SHORT means conditions suggest the price may fall — consider a short position. HOLD means conditions are not clear enough to act — waiting is the safest choice.</div>
        </div>
    </div>

    <a href="/" class="refresh-btn">🔄 Refresh Signal</a>

    <div class="history">
        <div class="history-title">📋 Signal History</div>
        <table>
            <tr>
                <th>Time</th>
                <th>Price</th>
                <th>Signal</th>
            </tr>
            <tr>
                <td>{{ last_updated[:16] }}</td>
                <td>₹{{ price }}</td>
                <td>{{ signal }}</td>
            </tr>
        </table>
    </div>

    <footer>
        TradeWise is an educational tool. This is not financial advice. Always do your own research before investing.
    </footer>

    <script>
        var chartData = {{ chart_json | safe }};
        Plotly.newPlot('chart', chartData.data, chartData.layout);
    </script>

</body>
</html>
"""

@app.route("/")
def home():
    data = get_nifty_data()
    return render_template_string(HTML, **data)

@app.route("/stocks")
def stocks():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>TradeWise — Stock Scanner</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: Arial, sans-serif; background: #0d1117; color: #e6edf3; }
            .navbar { display: flex; justify-content: space-between; align-items: center; padding: 16px 32px; background: #161b22; border-bottom: 1px solid #30363d; }
            .navbar-brand { font-size: 1.4em; font-weight: 700; color: #58a6ff; }
            .navbar-links a { color: #8b949e; text-decoration: none; margin-left: 24px; font-size: 0.95em; }
            .navbar-links a.active { color: #58a6ff; }
            .page-title { text-align: center; padding: 40px 20px 8px; font-size: 1.5em; font-weight: 700; }
            .page-sub { text-align: center; color: #8b949e; font-size: 0.9em; padding-bottom: 32px; }
            .coming-soon { text-align: center; color: #8b949e; padding: 40px; font-size: 1em; background: #161b22; border: 1px solid #30363d; border-radius: 12px; max-width: 500px; margin: 0 auto; }
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-brand">📈 TradeWise</div>
            <div class="navbar-links">
                <a href="/">NIFTY 50</a>
                <a href="/stocks" class="active">Stock Scanner</a>
                <a href="/portfolio">Portfolio</a>
                <a href="/learn">Learn</a>
            </div>
        </nav>
        <div class="page-title">📊 Stock Scanner</div>
        <div class="page-sub">Technical and fundamental analysis for Indian equities</div>
        <div class="coming-soon">Stock scanner coming soon — connect stock_scanner.py to populate this page with live data for Laurus Labs, ICICI Bank, APL Apollo, NRB Bearings, and Tilaknagar Industries.</div>
    </body>
    </html>
    """)

@app.route("/portfolio")
def portfolio():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>TradeWise — Portfolio</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: Arial, sans-serif; background: #0d1117; color: #e6edf3; }
            .navbar { display: flex; justify-content: space-between; align-items: center; padding: 16px 32px; background: #161b22; border-bottom: 1px solid #30363d; }
            .navbar-brand { font-size: 1.4em; font-weight: 700; color: #58a6ff; }
            .navbar-links a { color: #8b949e; text-decoration: none; margin-left: 24px; font-size: 0.95em; }
            .navbar-links a.active { color: #58a6ff; }
            .page-title { text-align: center; padding: 40px 20px 8px; font-size: 1.5em; font-weight: 700; }
            .page-sub { text-align: center; color: #8b949e; font-size: 0.9em; padding-bottom: 32px; }
            .coming-soon { text-align: center; color: #8b949e; padding: 40px; font-size: 1em; background: #161b22; border: 1px solid #30363d; border-radius: 12px; max-width: 500px; margin: 0 auto; }
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-brand">📈 TradeWise</div>
            <div class="navbar-links">
                <a href="/">NIFTY 50</a>
                <a href="/stocks">Stock Scanner</a>
                <a href="/portfolio" class="active">Portfolio</a>
                <a href="/learn">Learn</a>
            </div>
        </nav>
        <div class="page-title">💼 Paper Trading Portfolio</div>
        <div class="page-sub">Track your virtual trades and learn from real market conditions</div>
        <div class="coming-soon">Portfolio tracker coming soon — connect paper_trader.py to track virtual trades automatically when signals fire.</div>
    </body>
    </html>
    """)

@app.route("/learn")
def learn():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>TradeWise — Learn</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: Arial, sans-serif; background: #0d1117; color: #e6edf3; }
            .navbar { display: flex; justify-content: space-between; align-items: center; padding: 16px 32px; background: #161b22; border-bottom: 1px solid #30363d; }
            .navbar-brand { font-size: 1.4em; font-weight: 700; color: #58a6ff; }
            .navbar-links a { color: #8b949e; text-decoration: none; margin-left: 24px; font-size: 0.95em; }
            .navbar-links a.active { color: #58a6ff; }
            .page-title { text-align: center; padding: 40px 20px 8px; font-size: 1.5em; font-weight: 700; }
            .page-sub { text-align: center; color: #8b949e; font-size: 0.9em; padding-bottom: 32px; }
            .content { max-width: 700px; margin: 0 auto 40px auto; padding: 0 20px; }
            .topic { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; }
            .topic h3 { color: #58a6ff; font-size: 1em; margin-bottom: 10px; }
            .topic p { color: #8b949e; font-size: 0.9em; line-height: 1.7; }
            .topic .key { color: #e6edf3; font-weight: 600; }
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-brand">📈 TradeWise</div>
            <div class="navbar-links">
                <a href="/">NIFTY 50</a>
                <a href="/stocks">Stock Scanner</a>
                <a href="/portfolio">Portfolio</a>
                <a href="/learn" class="active">Learn</a>
            </div>
        </nav>
        <div class="page-title">📚 Learn Technical Analysis</div>
        <div class="page-sub">Plain English explanations for every concept used in TradeWise</div>
        <div class="content">

            <div class="topic">
                <h3>📈 What is the NIFTY 50?</h3>
                <p>The <span class="key">NIFTY 50</span> is India's most important stock market index. It tracks the performance of the 50 largest companies listed on the National Stock Exchange (NSE) — including companies like Reliance, HDFC Bank, Infosys, and TCS. When people say "the market went up today," they usually mean the NIFTY 50 went up. It is the benchmark against which all Indian investments are measured.</p>
            </div>

            <div class="topic">
                <h3>📊 What is Technical Analysis?</h3>
                <p><span class="key">Technical analysis</span> is the study of price movements and patterns to predict where the market might go next. Instead of looking at a company's profits or management, technical analysts look at charts, trends, and mathematical indicators. It is based on the idea that market psychology — fear, greed, momentum — creates repeatable patterns that can be identified and traded.</p>
            </div>

            <div class="topic">
                <h3>〰️ Moving Averages (MA)</h3>
                <p>A <span class="key">moving average</span> is the average price of a stock over the last N days. The MA10 is the average of the last 10 days. The MA50 is the average of the last 50 days. When the shorter average (MA10) crosses above the longer average (MA50), it signals that recent momentum is stronger than the historical trend — this is called a <span class="key">bullish crossover</span> and is one of the most widely used buy signals in trading.</p>
            </div>

            <div class="topic">
                <h3>⚡ RSI — Relative Strength Index</h3>
                <p>RSI is a number between <span class="key">0 and 100</span> that measures how fast and how much the price has moved recently. If RSI is <span class="key">above 70</span>, the market has risen very quickly and may be due for a pullback — this is called overbought. If RSI is <span class="key">below 30</span>, the market has fallen very quickly and may bounce — this is called oversold. The ideal zone for entering a trade is <span class="key">between 30 and 65</span>, where the market has room to move in either direction.</p>
            </div>

            <div class="topic">
                <h3>💪 ADX — Average Directional Index</h3>
                <p>ADX measures the <span class="key">strength</span> of the current trend, regardless of whether prices are going up or down. A value <span class="key">above 25</span> means a real trend exists and trading signals are more reliable. A value <span class="key">below 25</span> means the market is moving sideways without clear direction — trading in these conditions leads to more false signals and losses. ADX does not tell you which way the market is going, only how strongly it is going there.</p>
            </div>

            <div class="topic">
                <h3>🕯️ Candlestick Charts</h3>
                <p>A <span class="key">candlestick</span> represents one period of trading — in our case, one day. The body of the candle shows where the price opened and closed. The thin lines (wicks) show the highest and lowest prices reached during the day. <span class="key">Green candles</span> mean the price closed higher than it opened — a bullish day. <span class="key">Red candles</span> mean the price closed lower — a bearish day. Patterns in consecutive candles can signal reversals or continuations of trends.</p>
            </div>

            <div class="topic">
                <h3>📉 What does SHORT mean?</h3>
                <p>When you <span class="key">short</span> a stock or index, you are betting that the price will fall. You borrow shares, sell them at the current price, and hope to buy them back cheaper later — keeping the difference as profit. Shorting is more complex than buying and carries higher risk, but it allows traders to profit from falling markets. In TradeWise, a SHORT signal means the algorithm has identified conditions that historically precede a price decline.</p>
            </div>

            <div class="topic">
                <h3>📄 What is Paper Trading?</h3>
                <p><span class="key">Paper trading</span> means simulating real trades without using real money. You follow signals, record entries and exits, and track your virtual portfolio as if it were real — but no actual capital is at risk. It is the most important step between learning about trading and actually trading. Professional traders and quantitative analysts always paper trade a new strategy extensively before going live. TradeWise's paper trading engine does this automatically every time a signal fires.</p>
            </div>

        </div>
    </body>
    </html>
    """)

if __name__ == "__main__":
    print("Starting TradeWise...")
    print("Open http://127.0.0.1:5000 in your browser")
    app.run(debug=False, port=5000)