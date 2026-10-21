# ============================================
# Multi-Stock Technical & Fundamental Scanner
# Author: Vihaan Jain
# Purpose: Full analysis for long term investors
# ============================================

import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

STOCKS = {
    "Laurus Labs": "LAURUSLABS.NS",
    "Tilaknagar Industries": "TI.NS",
    "NRB Bearings": "NRBBEARING.NS",
    "ICICI Bank": "ICICIBANK.NS",
    "APL Apollo": "APLAPOLLO.NS"
}

def safe_round(val, decimals=2):
    try:
        return round(float(val), decimals)
    except:
        return None

def generate_stock_chart(ticker, projection_3m, projection_6m, current_price):
    try:
        data = yf.download(ticker, period="6mo", interval="1d", progress=False)
        data.columns = data.columns.get_level_values(0)
        dates = data.index.strftime("%Y-%m-%d").tolist()
        closes = [float(x) for x in data["Close"].tolist()]
        last_date = data.index[-1]
        date_3m = (last_date + timedelta(days=90)).strftime("%Y-%m-%d")
        date_6m = (last_date + timedelta(days=180)).strftime("%Y-%m-%d")

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=dates,
            y=closes,
            name="Price",
            line=dict(color="#58a6ff", width=2),
            fill="tozeroy",
            fillcolor="rgba(88, 166, 255, 0.05)"
        ))

        if projection_3m:
            fig.add_trace(go.Scatter(
                x=[dates[-1], date_3m],
                y=[current_price, projection_3m],
                name="3M Projection",
                line=dict(color="#3fb950", width=2, dash="dash")
            ))

        if projection_6m:
            fig.add_trace(go.Scatter(
                x=[dates[-1], date_6m],
                y=[current_price, projection_6m],
                name="6M Projection",
                line=dict(color="#f0883e", width=2, dash="dot")
            ))

        fig.update_layout(
            paper_bgcolor="#0d1117",
            plot_bgcolor="#161b22",
            font=dict(color="#e6edf3", size=10),
            xaxis=dict(gridcolor="#21262d", showgrid=True),
            yaxis=dict(gridcolor="#21262d", showgrid=True),
            legend=dict(bgcolor="#161b22", bordercolor="#30363d", font=dict(size=9)),
            height=200,
            margin=dict(l=10, r=10, t=10, b=30)
        )

        return fig.to_json()
    except Exception as e:
        print(f"Chart error for {ticker}: {e}")
        return None

def calculate_indicators(ticker):
    try:
        data = yf.download(ticker, period="1y", interval="1d", progress=False)
        if data.empty:
            return None

        data.columns = data.columns.get_level_values(0)
        data["MA10"] = data["Close"].rolling(window=10).mean()
        data["MA50"] = data["Close"].rolling(window=50).mean()
        data["MA200"] = data["Close"].rolling(window=200).mean()

        delta = data["Close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        data["RSI"] = 100 - (100 / (1 + rs))

        high = data["High"]
        low = data["Low"]
        close = data["Close"]

        plus_dm = high.diff()
        minus_dm = low.diff().abs()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)

        atr = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        data["ADX"] = dx.rolling(14).mean()

        row = data.iloc[-1]
        price = safe_round(row["Close"])
        ma10 = safe_round(row["MA10"])
        ma50 = safe_round(row["MA50"])
        ma200 = safe_round(row["MA200"])
        rsi = safe_round(row["RSI"])
        adx = safe_round(row["ADX"])

        week52_high = safe_round(data["High"].max())
        week52_low = safe_round(data["Low"].min())
        pct_from_52h = safe_round((price - week52_high) / week52_high * 100)
        pct_from_52l = safe_round((price - week52_low) / week52_low * 100)

        last_3m = data.iloc[-63:]
        resistance = safe_round(last_3m["High"].max())
        support = safe_round(last_3m["Low"].min())

        last_3m_close = data["Close"].iloc[-63:]
        daily_returns = last_3m_close.pct_change().dropna()
        avg_daily_return = float(daily_returns.mean())
        std_daily = float(daily_returns.std())

        projection_3m = safe_round(price * ((1 + avg_daily_return) ** 63))
        projection_6m = safe_round(price * ((1 + avg_daily_return) ** 126))
        projection_3m_pct = safe_round((projection_3m - price) / price * 100)
        projection_6m_pct = safe_round((projection_6m - price) / price * 100)

        vol_3m = safe_round(std_daily * (63 ** 0.5) * price)
        vol_6m = safe_round(std_daily * (126 ** 0.5) * price)
        range_3m_low = safe_round(projection_3m - vol_3m)
        range_3m_high = safe_round(projection_3m + vol_3m)
        range_6m_low = safe_round(projection_6m - vol_6m)
        range_6m_high = safe_round(projection_6m + vol_6m)

        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info

        pe_ratio = safe_round(info.get("trailingPE"))
        forward_pe = safe_round(info.get("forwardPE"))
        eps = safe_round(info.get("trailingEps"))
        dividend_yield = safe_round(info.get("dividendYield", 0) * 100) if info.get("dividendYield") else None
        market_cap = info.get("marketCap")
        market_cap_cr = safe_round(market_cap / 10000000) if market_cap else None
        pb_ratio = safe_round(info.get("priceToBook"))
        roe = safe_round(info.get("returnOnEquity", 0) * 100) if info.get("returnOnEquity") else None
        debt_to_equity = safe_round(info.get("debtToEquity"))
        revenue_growth = safe_round(info.get("revenueGrowth", 0) * 100) if info.get("revenueGrowth") else None
        earnings_growth = safe_round(info.get("earningsGrowth", 0) * 100) if info.get("earningsGrowth") else None
        analyst_target = safe_round(info.get("targetMeanPrice"))
        analyst_upside = safe_round((analyst_target - price) / price * 100) if analyst_target else None
        analyst_recommendation = info.get("recommendationKey", "N/A").upper()

        uptrend = ma10 > ma50 and (ma200 is None or price > ma200)
        downtrend = ma10 < ma50 and (ma200 is None or price < ma200)
        strong_trend = adx > 25 if adx else False
        good_rsi_long = 20 < rsi < 65 if rsi else False
        good_rsi_short = 35 < rsi < 75 if rsi else False

        if uptrend and strong_trend and good_rsi_long:
            signal = "🟢 BUY"
        elif downtrend and strong_trend and good_rsi_short:
            signal = "🔴 SHORT"
        else:
            signal = "⚪ HOLD"

        chart_json = generate_stock_chart(ticker, projection_3m, projection_6m, price)

        chart_json = generate_stock_chart(ticker, projection_3m, projection_6m, price)
        print(f"  Chart generated: {chart_json is not None}")

        return {
            "price": price, "ma10": ma10, "ma50": ma50, "ma200": ma200,
            "rsi": rsi, "adx": adx, "signal": signal,
            "uptrend": uptrend, "downtrend": downtrend, "strong_trend": strong_trend,
            "week52_high": week52_high, "week52_low": week52_low,
            "pct_from_52h": pct_from_52h, "pct_from_52l": pct_from_52l,
            "support": support, "resistance": resistance,
            "projection_3m": projection_3m, "projection_6m": projection_6m,
            "projection_3m_pct": projection_3m_pct, "projection_6m_pct": projection_6m_pct,
            "range_3m_low": range_3m_low, "range_3m_high": range_3m_high,
            "range_6m_low": range_6m_low, "range_6m_high": range_6m_high,
            "pe_ratio": pe_ratio, "forward_pe": forward_pe, "eps": eps,
            "dividend_yield": dividend_yield, "market_cap_cr": market_cap_cr,
            "pb_ratio": pb_ratio, "roe": roe, "debt_to_equity": debt_to_equity,
            "revenue_growth": revenue_growth, "earnings_growth": earnings_growth,
            "analyst_target": analyst_target, "analyst_upside": analyst_upside,
            "analyst_recommendation": analyst_recommendation,
            "chart_json": chart_json,
        }

    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def scan_all_stocks():
    print("\n" + "=" * 60)
    print(f"STOCK SCANNER - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    results = {}
    for name, ticker in STOCKS.items():
        print(f"Scanning {name}...")
        result = calculate_indicators(ticker)
        if result:
            results[name] = result
            print(f"  Price: ₹{result['price']} | PE: {result['pe_ratio']} | ROE: {result['roe']}% | Signal: {result['signal']}")
            print(f"  3M: ₹{result['projection_3m']} ({result['projection_3m_pct']}%) | 6M: ₹{result['projection_6m']} ({result['projection_6m_pct']}%)")
        else:
            print(f"  Failed to fetch data")
    return results

if __name__ == "__main__":
    scan_all_stocks()