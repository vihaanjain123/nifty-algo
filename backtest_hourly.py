# ============================================
# NIFTY 50 Hourly Backtest - Official Version
# Author: Vihaan Jain
# Strategy: MA20/100/400 trend + RSI + ADX + candlestick patterns
#           + choppy-market filter + trend-reversal filter
#           + long/short + trailing stop + daily regime filter
# Data: hourly NIFTY (Yahoo Finance gives about 730 days max)
# Output: printed metrics for TRAIN and TEST separately,
#         equity curve PNGs, results_summary.txt
# ============================================

import datetime as dt

import matplotlib
matplotlib.use("Agg")  # save charts to files, no window needed
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

# ---------------- SETTINGS ----------------
STARTING_CAPITAL = 100000
TRAIN_FRACTION = 0.6          # first 60% of bars = training, rest = testing
USE_REGIME_FILTER = True      # no shorts while NIFTY daily close > its 200-day MA
COST_PER_SIDE = 0.0003        # 0.03% per side (rough brokerage + charges); set 0 to disable
MIN_HOLD = 6                  # bars
TRAILING_STOP_PCT = 0.015
COOLDOWN_BARS = 6
ADX_MIN = 28                  # trend-strength threshold used by the choppy-market detector
ATR_TRAIL_MULT = 2.0        # None = fixed % trailing stop; e.g. 3.0 = trail 3 x ATR(14) instead

# ---------------- DATA ----------------
end = dt.date.today() + dt.timedelta(days=1)
start = end - dt.timedelta(days=725)   # Yahoo hourly limit is ~730 days

nifty = yf.download("^NSEI", start=start, end=end, interval="1h", progress=False)
nifty.columns = nifty.columns.get_level_values(0)
nifty = nifty.dropna()

# Daily regime: is NIFTY above its 200-day MA? (uses the PREVIOUS day, so no look-ahead)
daily = yf.download("^NSEI", start=start - dt.timedelta(days=400), end=end,
                    interval="1d", progress=False)
daily.columns = daily.columns.get_level_values(0)
daily["MA200D"] = daily["Close"].rolling(200).mean()
daily["BULL"] = (daily["Close"] > daily["MA200D"]).shift(1)
bull_by_date = daily["BULL"].copy()
bull_by_date.index = bull_by_date.index.tz_localize(None).normalize()
hour_dates = nifty.index.tz_localize(None).normalize() if nifty.index.tz is not None \
    else nifty.index.normalize()
nifty["BULL_REGIME"] = bull_by_date.reindex(hour_dates, method="ffill").fillna(False).astype(bool).values

# ---------------- INDICATORS ----------------
nifty["MA20"] = nifty["Close"].rolling(window=20).mean()
nifty["MA100"] = nifty["Close"].rolling(window=100).mean()
nifty["MA400"] = nifty["Close"].rolling(window=400).mean()

delta = nifty["Close"].diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)
rs = gain.rolling(14).mean() / loss.rolling(14).mean()
nifty["RSI"] = 100 - (100 / (1 + rs))

high, low, close = nifty["High"], nifty["Low"], nifty["Close"]
plus_dm = high.diff()
minus_dm = low.diff().abs()
plus_dm[plus_dm < 0] = 0
minus_dm[minus_dm < 0] = 0
tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
               axis=1).max(axis=1)
atr_series = tr.rolling(14).mean()
plus_di = 100 * (plus_dm.rolling(14).mean() / atr_series)
minus_di = 100 * (minus_dm.rolling(14).mean() / atr_series)
dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
nifty["ADX"] = dx.rolling(14).mean()
nifty["ATR10"] = tr.rolling(10).mean()
nifty["ATR14"] = atr_series

# ---------------- TRAIN / TEST SPLIT ----------------
valid = nifty.dropna(subset=["MA20", "MA100", "MA400", "RSI", "ADX", "ATR10", "ATR14"])
split_i = int(len(valid) * TRAIN_FRACTION)
train = valid.iloc[:split_i]
test = valid.iloc[split_i:]


def run_backtest(data, label, save_chart=True):
    capital = STARTING_CAPITAL
    position = 0
    buy_price = 0
    hold_bars = 0
    cooldown = 0
    highest_price = 0
    trades = []
    equity_dates, equity_values = [], []
    buy_dates, buy_prices_list, sell_dates, sell_prices_list = [], [], [], []

    print(f"\n--- {label} RESULTS ---")
    print(f"Period: {data.index[0]}  to  {data.index[-1]}  ({len(data)} hourly bars)\n")

    for date, row in data.iterrows():
        close = float(row["Close"])
        ma20, ma100, ma400 = float(row["MA20"]), float(row["MA100"]), float(row["MA400"])
        rsi, adx, atr10 = float(row["RSI"]), float(row["ADX"]), float(row["ATR10"])
        atr14 = float(row["ATR14"])
        bull_regime = bool(row["BULL_REGIME"])

        open_curr, high_curr = float(row["Open"]), float(row["High"])
        low_curr, close_curr = float(row["Low"]), close

        idx = nifty.index.get_loc(date)
        if idx < 20:
            continue

        prev_row = nifty.iloc[idx - 1]
        prev2_row = nifty.iloc[idx - 2]
        open_prev, close_prev = float(prev_row["Open"]), float(prev_row["Close"])
        high_prev, low_prev = float(prev_row["High"]), float(prev_row["Low"])
        open_prev2, close_prev2 = float(prev2_row["Open"]), float(prev2_row["Close"])

        last10 = nifty.iloc[idx - 10:idx]
        last10_high, last10_low = float(last10["High"].max()), float(last10["Low"].min())
        last10_close_start = float(last10["Close"].iloc[0])
        last10_close_end = float(last10["Close"].iloc[-1])
        last20 = nifty.iloc[idx - 20:idx]

        ma20_crosses = 0
        for i in range(1, len(last10)):
            pc, cc = float(last10["Close"].iloc[i - 1]), float(last10["Close"].iloc[i])
            pm, cm = float(last10["MA20"].iloc[i - 1]), float(last10["MA20"].iloc[i])
            if (pc < pm and cc > cm) or (pc > pm and cc < cm):
                ma20_crosses += 1

        # Choppy market detector (5 filters)
        adx_strong = adx > ADX_MIN
        ma_separated = abs(ma20 - ma100) / ma100 * 100 > 0.5
        not_oscillating = ma20_crosses <= 3
        atr_justified = abs(last10_close_end - last10_close_start) > atr10 * 0.5
        swing_meaningful = (last10_high - last10_low) > close * 0.01
        not_choppy = adx_strong and ma_separated and not_oscillating and atr_justified and swing_meaningful

        # Trend reversal filter
        last20_lows = last20["Low"].values
        not_recovering = float(last20_lows[10:].mean()) <= float(last20_lows[:10].mean()) * 1.005

        # Candlestick patterns
        body = abs(close_curr - open_curr)
        lower_wick = min(close_curr, open_curr) - low_curr
        upper_wick = high_curr - max(close_curr, open_curr)
        body_prev = abs(close_prev - open_prev)
        body_prev2 = abs(close_prev2 - open_prev2)
        mid_prev2 = (open_prev2 + close_prev2) / 2

        bullish_engulfing = close_prev < open_prev and close_curr > open_curr and \
            close_curr > open_prev and open_curr < close_prev
        hammer = body > 0 and lower_wick >= 2 * body and upper_wick <= 0.3 * body
        morning_star = close_prev2 < open_prev2 and body_prev < body_prev2 * 0.3 and \
            close_curr > open_curr and close_curr > mid_prev2 and body > body_prev2 * 0.5
        tweezer_bottom = close_prev < open_prev and close_curr > open_curr and \
            abs(low_curr - low_prev) <= 0.001 * low_prev
        bearish_engulfing = close_prev > open_prev and close_curr < open_curr and \
            close_curr < open_prev and open_curr > close_prev
        shooting_star = body > 0 and upper_wick >= 2 * body and lower_wick <= 0.3 * body
        evening_star = close_prev2 > open_prev2 and body_prev < body_prev2 * 0.3 and \
            close_curr < open_curr and close_curr < mid_prev2 and body > body_prev2 * 0.5
        tweezer_top = close_prev > open_prev and close_curr < open_curr and \
            abs(high_curr - high_prev) <= 0.001 * high_prev

        good_candle = bullish_engulfing or hammer or morning_star or tweezer_bottom or (close_curr > open_curr)
        bad_candle = bearish_engulfing or shooting_star or evening_star or tweezer_top or (close_curr < open_curr)
        no_upper_wick_rejection = upper_wick <= 1.5 * body
        no_lower_wick_rejection = lower_wick <= 1.5 * body if body > 0 else True

        # Signal conditions
        ma_signal = ma20 > ma100
        uptrend = close > ma400 and ma100 > ma400
        good_rsi = 20 < rsi < 65
        price_above_ma20 = close > ma20

        ma_signal_short = ma20 < ma100
        downtrend = close < ma400 and ma100 < ma400
        bad_rsi = 35 < rsi < 75
        price_below_ma20 = close < ma20
        regime_allows_short = (not bull_regime) if USE_REGIME_FILTER else True

        if cooldown > 0:
            cooldown -= 1

        if (ma_signal and uptrend and good_rsi and price_above_ma20 and good_candle
                and no_upper_wick_rejection and not_choppy and position == 0 and cooldown == 0):
            position = capital * (1 - COST_PER_SIDE) / close
            buy_price = close
            capital = 0
            hold_bars = 0
            highest_price = close
            buy_dates.append(date)
            buy_prices_list.append(close)
            print(f"{date} | LONG BUY at {round(close, 2)} | Units: {round(position, 4)}")

        elif (ma_signal_short and downtrend and bad_rsi and price_below_ma20 and bad_candle
              and no_lower_wick_rejection and not_choppy and not_recovering and regime_allows_short
              and position == 0 and cooldown == 0):
            position = -(capital * (1 - COST_PER_SIDE) / close)
            buy_price = close
            capital = 0
            hold_bars = 0
            highest_price = close
            buy_dates.append(date)
            buy_prices_list.append(close)
            print(f"{date} | SHORT at {round(close, 2)} | Units: {round(abs(position), 4)}")

        elif position > 0:
            hold_bars += 1
            highest_price = max(highest_price, close)
            trailing_stop = (highest_price - ATR_TRAIL_MULT * atr14) if ATR_TRAIL_MULT else highest_price * (1 - TRAILING_STOP_PCT)
            if hold_bars >= MIN_HOLD and ((not ma_signal) or close < trailing_stop):
                exit_reason = "TRAILING STOP" if close < trailing_stop else "SIGNAL"
                capital = position * close * (1 - COST_PER_SIDE)
                trades.append({"exit": exit_reason, "side": "LONG", "pnl": round(capital - position * buy_price / (1 - COST_PER_SIDE), 2)})
                sell_dates.append(date)
                sell_prices_list.append(close)
                print(f"{date} | LONG {exit_reason} SELL at {round(close, 2)} | Capital: Rs{round(capital, 2)}")
                position = 0
                hold_bars = 0
                highest_price = 0
                if exit_reason == "TRAILING STOP":
                    cooldown = COOLDOWN_BARS

        elif position < 0:
            hold_bars += 1
            highest_price = min(highest_price, close)
            trailing_stop_short = (highest_price + ATR_TRAIL_MULT * atr14) if ATR_TRAIL_MULT else highest_price * (1 + TRAILING_STOP_PCT)
            if hold_bars >= MIN_HOLD and ((not ma_signal_short) or close > trailing_stop_short):
                exit_reason = "TRAILING STOP" if close > trailing_stop_short else "SIGNAL"
                units = abs(position)
                capital = units * (2 * buy_price - close) * (1 - COST_PER_SIDE)
                trades.append({"exit": exit_reason, "side": "SHORT", "pnl": round(capital - units * buy_price / (1 - COST_PER_SIDE), 2)})
                sell_dates.append(date)
                sell_prices_list.append(close)
                print(f"{date} | SHORT COVER {exit_reason} at {round(close, 2)} | Capital: Rs{round(capital, 2)}")
                position = 0
                hold_bars = 0
                highest_price = 0
                if exit_reason == "TRAILING STOP":
                    cooldown = COOLDOWN_BARS

        # Mark-to-market equity for the equity curve
        if position > 0:
            equity = position * close
        elif position < 0:
            equity = abs(position) * (2 * buy_price - close)
        else:
            equity = capital
        equity_dates.append(date)
        equity_values.append(equity)

    final_value = round(equity_values[-1], 2) if equity_values else STARTING_CAPITAL
    equity_series = pd.Series(equity_values, index=equity_dates)
    max_dd = round(((equity_series / equity_series.cummax()) - 1).min() * 100, 2) if len(equity_series) else 0
    ret = round((final_value - STARTING_CAPITAL) / STARTING_CAPITAL * 100, 2)
    bh_ret = round((float(data["Close"].iloc[-1]) / float(data["Close"].iloc[0]) - 1) * 100, 2)

    winners = [t for t in trades if t["pnl"] > 0]
    losers = [t for t in trades if t["pnl"] <= 0]
    win_rate = round(len(winners) / len(trades) * 100, 2) if trades else 0
    avg_win = round(sum(t["pnl"] for t in winners) / len(winners), 2) if winners else 0
    avg_loss = round(sum(t["pnl"] for t in losers) / len(losers), 2) if losers else 0
    longs = sum(1 for t in trades if t["side"] == "LONG")
    shorts = len(trades) - longs

    lines = [
        f"{label}",
        f"  Period: {data.index[0].date()} to {data.index[-1].date()}",
        f"  Final portfolio value: Rs{final_value}",
        f"  Total return: {ret}%",
        f"  NIFTY buy-and-hold over same period: {bh_ret}%",
        f"  Max drawdown: {max_dd}%",
        f"  Total trades: {len(trades)} (long {longs}, short {shorts})",
        f"  Winning trades: {len(winners)}   Losing trades: {len(losers)}",
        f"  Win rate: {win_rate}%",
        f"  Average win: Rs{avg_win}   Average loss: Rs{avg_loss}",
    ]
    print("\n--- PERFORMANCE METRICS ---")
    print("\n".join(lines))

    if trades:
        print("\n--- TRADE BREAKDOWN ---")
        for i, t in enumerate(trades):
            print(f"Trade {i + 1}: {'WIN' if t['pnl'] > 0 else 'LOSS'} | {t['side']} | P&L: Rs{t['pnl']} | Exit: {t['exit']}")

    # Equity curve chart (portfolio value vs NIFTY buy-and-hold, both start at Rs1,00,000)
    if save_chart and len(equity_series):
        bh_curve = data["Close"].loc[equity_series.index] / float(data["Close"].iloc[0]) * STARTING_CAPITAL
        fig, ax = plt.subplots(figsize=(14, 6))
        ax.plot(range(len(equity_series)), equity_series.values, color="green", linewidth=1.5, label="Algorithm equity")
        ax.plot(range(len(bh_curve)), bh_curve.values, color="grey", linewidth=1, label="NIFTY buy-and-hold")
        ax.axhline(STARTING_CAPITAL, color="black", linewidth=0.6, linestyle="--")
        ticks = list(range(0, len(equity_series), max(1, len(equity_series) // 8)))
        ax.set_xticks(ticks)
        ax.set_xticklabels([str(equity_series.index[i].date()) for i in ticks], rotation=30)
        ax.set_title(f"Equity curve - {label} ({ret}% vs buy-and-hold {bh_ret}%)")
        ax.set_xlabel("Date (non-trading hours removed)")
        ax.set_ylabel("Portfolio value (Rs)")
        ax.grid(True)
        ax.legend()
        plt.tight_layout()
        fname = f"{label.lower().replace(' ', '_')}_equity_curve.png"
        plt.savefig(fname, dpi=150)
        plt.close()
        print(f"Equity curve saved as {fname}")

    return lines, ret, win_rate, len(trades)


import contextlib
import io
import sys

if "--tune" in sys.argv:
    # TUNING MODE: only the TRAINING data is used. The test data is never touched.
    print("TUNING ON TRAINING DATA ONLY (test data not used)\n")
    print(f"{'ADX_MIN':>8} {'ATR_TRAIL':>10} {'return%':>9} {'win%':>7} {'trades':>7}")
    for adx_min in (20, 24, 28):
        for atr_mult in (None, 2.0, 3.0, 4.0):
            ADX_MIN, ATR_TRAIL_MULT = adx_min, atr_mult
            with contextlib.redirect_stdout(io.StringIO()):
                _, r, w, n = run_backtest(train, "TUNE", save_chart=False)
            print(f"{adx_min:>8} {str(atr_mult):>10} {r:>9} {w:>7} {n:>7}")
    print("\nPick ONE setting from this table, set ADX_MIN / ATR_TRAIL_MULT at the top of the")
    print("file, then run normally (no --tune) to see the test result once.")
    sys.exit()

print("=" * 50)
print("TRAINING PHASE")
print("=" * 50)
train_lines, _, _, _ = run_backtest(train, "TRAINING")

print("\n" + "=" * 50)
print("TESTING PHASE - unseen data")
print("=" * 50)
test_lines, _, _, _ = run_backtest(test, "TESTING")

with open("results_summary.txt", "w") as f:
    f.write("\n\n".join(["\n".join(train_lines), "\n".join(test_lines)]))
    f.write(f"\n\nSettings: regime filter={USE_REGIME_FILTER}, cost per side={COST_PER_SIDE}, "
            f"ADX_MIN={ADX_MIN}, ATR_TRAIL_MULT={ATR_TRAIL_MULT}\n")

print("\n" + "=" * 50)
print("Summary saved to results_summary.txt")
print("=" * 50)