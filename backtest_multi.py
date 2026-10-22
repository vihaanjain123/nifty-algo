# ============================================
# NIFTY Strategy - Multi-Stock Hourly Validation
# Author: Vihaan Jain
#
# Purpose: test the SAME rules on 25 liquid NIFTY stocks so that there are
#          hundreds of trades instead of 8-11 (a real sample size).
#
# Three-way split (by calendar time, same dates for every stock):
#     TRAIN       first 50%  -> tune settings here (--tune)
#     VALIDATION  next 25%   -> compare versions here (--eval)
#     FINAL TEST  last 25%   -> look ONCE at the very end (--final)
#
# Usage:
#     python3 backtest_multi.py --tune     # grid search, TRAIN data only
#     python3 backtest_multi.py --eval     # current settings on TRAIN + VALIDATION
#     python3 backtest_multi.py --final    # FINAL TEST, can only be run once
#     (add --refresh to re-download data instead of using data_cache.pkl)
#
# Every trade is Rs1,00,000 notional. P&L = 1,00,000 x trade return after costs.
# ============================================

import argparse
import datetime as dt
import os
import pickle
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

# ---------------- SETTINGS (change these between --eval runs) ----------------
ADX_MIN = 28              # trend-strength threshold
CHOP_MIN_PASS = 5         # how many of the 5 choppy-market filters must pass (5 = original rules)
STOP_MODE = "pct"         # "pct" = fixed % trailing stop, "atr" = ATR-based trailing stop
STOP_VALUE = 0.015        # 0.015 = 1.5% (pct mode)  |  2.0 = 2 x ATR14 (atr mode)
USE_REGIME_FILTER = True  # no shorts while NIFTY's previous daily close > its 200-day MA
COST_PER_SIDE = 0.0003    # 0.03% per side
MIN_HOLD = 6
COOLDOWN_BARS = 6
TRADE_SIZE = 100000

# Which strategy to run: "original" (MA + RSI + ADX + candles + choppy filters, long/short)
#                    or  "pullback" (new: buy dips inside a strong uptrend, long only)
STRATEGY = "pullback"
PB_ADX_MIN = 20           # pullback: minimum ADX (trend strength)
PB_RSI_DIP = 40           # pullback: RSI must have dipped below this in the last 3 bars
PB_RSI_EXIT = 60          # pullback: exit when RSI rises above this
PB_STOP_ATR = 2.0         # pullback: exit if close falls below entry - this x ATR14
PB_MAX_HOLD = 35          # pullback: exit after this many hourly bars (35 = 5 trading days)

TICKERS = ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "SBIN", "AXISBANK",
           "KOTAKBANK", "LT", "BHARTIARTL", "ITC", "BAJFINANCE", "HINDUNILVR",
           "MARUTI", "SUNPHARMA", "TITAN", "ASIANPAINT", "NTPC", "POWERGRID",
           "ONGC", "TATASTEEL", "M&M", "ULTRACEMCO", "WIPRO", "HCLTECH"]
CACHE_FILE = "data_cache.pkl"
LOCK_FILE = "FINAL_TEST_DONE.txt"


# ---------------- DATA ----------------
def fetch_data(refresh=False):
    if os.path.exists(CACHE_FILE) and not refresh:
        with open(CACHE_FILE, "rb") as f:
            print(f"Loaded cached data from {CACHE_FILE} (use --refresh to re-download)")
            return pickle.load(f)

    end = dt.date.today() + dt.timedelta(days=1)
    start = end - dt.timedelta(days=725)
    print("Downloading hourly data for", len(TICKERS), "stocks ...")
    names = [t + ".NS" for t in TICKERS]
    raw = yf.download(names, start=start, end=end, interval="1h",
                      group_by="ticker", progress=False, threads=True)
    stocks = {}
    for t, n in zip(TICKERS, names):
        try:
            d = raw[n].dropna()
            if len(d) > 800:
                stocks[t] = d
            else:
                print(f"  skipped {t}: only {len(d)} bars")
        except Exception as e:
            print(f"  skipped {t}: {e}")

    daily = yf.download("^NSEI", start=start - dt.timedelta(days=400), end=end,
                        interval="1d", progress=False)
    daily.columns = daily.columns.get_level_values(0)
    daily["MA200D"] = daily["Close"].rolling(200).mean()
    bull = (daily["Close"] > daily["MA200D"]).shift(1)
    bull.index = bull.index.tz_localize(None).normalize()

    data = {"stocks": stocks, "bull": bull}
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(data, f)
    print(f"Downloaded {len(stocks)} stocks, saved to {CACHE_FILE}")
    return data


# ---------------- FEATURES (computed once per stock) ----------------
def build_features(df, bull_by_date):
    c, o, h, l = df["Close"], df["Open"], df["High"], df["Low"]

    ma20 = c.rolling(20).mean()
    ma100 = c.rolling(100).mean()
    ma400 = c.rolling(400).mean()

    delta = c.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    rsi = 100 - (100 / (1 + gain.rolling(14).mean() / loss.rolling(14).mean()))

    plus_dm = h.diff().clip(lower=0)
    minus_dm = l.diff().abs()
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean()
    plus_di = 100 * plus_dm.rolling(14).mean() / atr14
    minus_di = 100 * minus_dm.rolling(14).mean() / atr14
    adx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).rolling(14).mean()
    atr10 = tr.rolling(10).mean()

    # Choppy-market detector (the 4 filters that don't depend on ADX_MIN)
    cross = (((c.shift(1) < ma20.shift(1)) & (c > ma20)) |
             ((c.shift(1) > ma20.shift(1)) & (c < ma20))).astype(float)
    crosses = cross.shift(1).rolling(9).sum()
    ma_separated = (ma20 - ma100).abs() / ma100 * 100 > 0.5
    not_oscillating = crosses <= 3
    atr_justified = (c.shift(1) - c.shift(10)).abs() > atr10 * 0.5
    swing_meaningful = (h.shift(1).rolling(10).max() - l.shift(1).rolling(10).min()) > c * 0.01
    chop_others = (ma_separated.astype(int) + not_oscillating.astype(int) +
                   atr_justified.astype(int) + swing_meaningful.astype(int))

    not_recovering = l.shift(1).rolling(10).mean() <= l.shift(11).rolling(10).mean() * 1.005

    # Candlestick patterns
    o1, c1, h1, l1 = o.shift(1), c.shift(1), h.shift(1), l.shift(1)
    o2, c2 = o.shift(2), c.shift(2)
    body = (c - o).abs()
    lower_wick = np.minimum(c, o) - l
    upper_wick = h - np.maximum(c, o)
    body1 = (c1 - o1).abs()
    body2 = (c2 - o2).abs()
    mid2 = (o2 + c2) / 2

    bull_engulf = (c1 < o1) & (c > o) & (c > o1) & (o < c1)
    hammer = (body > 0) & (lower_wick >= 2 * body) & (upper_wick <= 0.3 * body)
    morning_star = (c2 < o2) & (body1 < body2 * 0.3) & (c > o) & (c > mid2) & (body > body2 * 0.5)
    tweezer_bottom = (c1 < o1) & (c > o) & ((l - l1).abs() <= 0.001 * l1)
    bear_engulf = (c1 > o1) & (c < o) & (c < o1) & (o > c1)
    shooting_star = (body > 0) & (upper_wick >= 2 * body) & (lower_wick <= 0.3 * body)
    evening_star = (c2 > o2) & (body1 < body2 * 0.3) & (c < o) & (c < mid2) & (body > body2 * 0.5)
    tweezer_top = (c1 > o1) & (c < o) & ((h - h1).abs() <= 0.001 * h1)

    good_candle = bull_engulf | hammer | morning_star | tweezer_bottom | (c > o)
    bad_candle = bear_engulf | shooting_star | evening_star | tweezer_top | (c < o)
    no_upper_rej = upper_wick <= 1.5 * body
    no_lower_rej = (lower_wick <= 1.5 * body) | (body == 0)

    ma_sig = ma20 > ma100
    ma_sig_short = ma20 < ma100
    long_base = (ma_sig & (c > ma400) & (ma100 > ma400) & (rsi > 20) & (rsi < 65) &
                 (c > ma20) & good_candle & no_upper_rej)
    short_base = (ma_sig_short & (c < ma400) & (ma100 < ma400) & (rsi > 35) & (rsi < 75) &
                  (c < ma20) & bad_candle & no_lower_rej & not_recovering)

    uptrend = (ma100 > ma400) & (c > ma400)
    rsi_dip_min = rsi.shift(1).rolling(3).min()
    rsi_up = rsi > rsi.shift(1)

    dates = df.index.tz_localize(None).normalize() if df.index.tz is not None else df.index.normalize()
    bull = bull_by_date.reindex(dates, method="ffill").fillna(False).astype(bool).values

    valid = (ma400.notna() & rsi.notna() & adx.notna() & atr10.notna() & atr14.notna() &
             crosses.notna() & l.shift(11).notna() & np.isfinite(rsi)).values

    return {
        "index": df.index, "close": c.values, "atr14": atr14.values, "adx": adx.values,
        "chop_others": chop_others.values, "long_base": long_base.values,
        "short_base": short_base.values, "ma_sig": ma_sig.values,
        "ma_sig_short": ma_sig_short.values, "bull": bull, "valid": valid,
        "open": o.values, "rsi": rsi.values, "uptrend": uptrend.values,
        "rsi_dip_min": rsi_dip_min.values, "rsi_up": rsi_up.values,
        "good_candle": good_candle.values,
    }


# ---------------- SIMULATION ----------------
def simulate(F, lo, hi, ticker, adx_min, chop_pass, stop_mode, stop_value, regime):
    trades = []
    pos = 0
    entry = 0.0
    hold = 0
    cooldown = 0
    extreme = 0.0
    last_i = None

    def close_trade(i, reason):
        cl = F["close"][i]
        ret = pos * (cl / entry - 1) - 2 * COST_PER_SIDE
        trades.append({"ticker": ticker, "side": "LONG" if pos > 0 else "SHORT",
                       "ret": ret, "pnl": ret * TRADE_SIZE, "exit": reason,
                       "time": F["index"][i]})

    for i in range(lo, hi):
        if not F["valid"][i]:
            continue
        last_i = i
        cl = F["close"][i]
        if cooldown > 0:
            cooldown -= 1

        if pos == 0:
            if cooldown == 0 and (F["chop_others"][i] + (F["adx"][i] > adx_min)) >= chop_pass:
                if F["long_base"][i]:
                    pos, entry, hold, extreme = 1, cl, 0, cl
                elif F["short_base"][i] and (not regime or not F["bull"][i]):
                    pos, entry, hold, extreme = -1, cl, 0, cl
        elif pos > 0:
            hold += 1
            extreme = max(extreme, cl)
            stop = extreme * (1 - stop_value) if stop_mode == "pct" else extreme - stop_value * F["atr14"][i]
            if hold >= MIN_HOLD and ((not F["ma_sig"][i]) or cl < stop):
                reason = "STOP" if cl < stop else "SIGNAL"
                close_trade(i, reason)
                pos = 0
                if reason == "STOP":
                    cooldown = COOLDOWN_BARS
        else:
            hold += 1
            extreme = min(extreme, cl)
            stop = extreme * (1 + stop_value) if stop_mode == "pct" else extreme + stop_value * F["atr14"][i]
            if hold >= MIN_HOLD and ((not F["ma_sig_short"][i]) or cl > stop):
                reason = "STOP" if cl > stop else "SIGNAL"
                close_trade(i, reason)
                pos = 0
                if reason == "STOP":
                    cooldown = COOLDOWN_BARS

    if pos != 0 and last_i is not None:
        close_trade(last_i, "PERIOD END")
    return trades


def simulate_pullback(F, lo, hi, ticker, adx_min, rsi_dip, rsi_exit, stop_atr, max_hold):
    """Long-only trend-pullback. Signals use bar i's close; fills happen at bar i+1's open."""
    trades = []
    pos = 0
    entry = 0.0
    stop_price = 0.0
    hold = 0
    pending_entry = False
    pending_atr = 0.0
    pending_exit = None
    last_i = None

    def record(i, price, reason):
        ret = (price / entry - 1) - 2 * COST_PER_SIDE
        trades.append({"ticker": ticker, "side": "LONG", "ret": ret, "pnl": ret * TRADE_SIZE,
                       "exit": reason, "time": F["index"][i]})

    for i in range(lo, hi):
        if not F["valid"][i]:
            continue
        last_i = i

        # 1) fill orders placed on the previous bar at THIS bar's open
        if pending_entry:
            pos, entry, hold = 1, F["open"][i], 0
            stop_price = entry - stop_atr * pending_atr
            pending_entry = False
            continue
        if pending_exit is not None:
            record(i, F["open"][i], pending_exit)
            pos, pending_exit = 0, None

        cl = F["close"][i]
        if pos == 0:
            if (F["uptrend"][i] and F["adx"][i] > adx_min and F["rsi_dip_min"][i] < rsi_dip
                    and F["rsi_up"][i] and F["good_candle"][i]):
                pending_entry = True
                pending_atr = F["atr14"][i]
        else:
            hold += 1
            if cl <= stop_price:
                pending_exit = "STOP"
            elif F["rsi"][i] > rsi_exit:
                pending_exit = "RSI TARGET"
            elif hold >= max_hold:
                pending_exit = "TIME"

    if pos != 0 and last_i is not None:
        record(last_i, F["close"][last_i], "PERIOD END")
    return trades


def run_period(features, start, end, **p):
    strategy = p.pop("strategy", "original")
    sim = simulate if strategy == "original" else simulate_pullback
    all_trades = []
    for ticker, F in features.items():
        lo = F["index"].searchsorted(start) if start is not None else 0
        hi = F["index"].searchsorted(end) if end is not None else len(F["index"])
        all_trades += sim(F, lo, hi, ticker, **p)
    return sorted(all_trades, key=lambda t: t["time"])


# ---------------- STATS ----------------
def stats(trades):
    n = len(trades)
    if n == 0:
        return {"n": 0, "win": 0, "pf": 0, "avg": 0, "total": 0, "dd": 0,
                "avg_win": 0, "avg_loss": 0, "longs": 0, "shorts": 0}
    pnl = np.array([t["pnl"] for t in trades])
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    cum = np.cumsum(pnl)
    dd = float((cum - np.maximum.accumulate(np.r_[0, cum])[1:]).min())
    return {
        "n": n,
        "win": round(len(wins) / n * 100, 1),
        "pf": round(wins.sum() / abs(losses.sum()), 2) if losses.sum() != 0 else float("inf"),
        "avg": round(pnl.mean() / TRADE_SIZE * 100, 3),
        "total": round(pnl.sum(), 0),
        "dd": round(dd, 0),
        "avg_win": round(wins.mean(), 0) if len(wins) else 0,
        "avg_loss": round(losses.mean(), 0) if len(losses) else 0,
        "longs": sum(1 for t in trades if t["side"] == "LONG"),
        "shorts": sum(1 for t in trades if t["side"] == "SHORT"),
    }


def report(label, trades, window):
    s = stats(trades)
    lines = [
        f"{label}  ({window})",
        f"  Trades: {s['n']}  (long {s['longs']}, short {s['shorts']})",
        f"  Win rate: {s['win']}%",
        f"  Profit factor (wins / losses): {s['pf']}",
        f"  Average return per trade: {s['avg']}% (after costs)",
        f"  Average win: Rs{s['avg_win']}   Average loss: Rs{s['avg_loss']}",
        f"  Total P&L at Rs{TRADE_SIZE:,} per trade: Rs{s['total']}",
        f"  Max drawdown of cumulative P&L: Rs{s['dd']}",
    ]
    print("\n".join(lines))
    return lines


def save_curve(trades, label):
    if not trades:
        return
    pnl = np.cumsum([t["pnl"] for t in trades])
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(range(len(pnl)), pnl, color="green", linewidth=1.5)
    ax.axhline(0, color="black", linewidth=0.6, linestyle="--")
    ax.set_title(f"Cumulative P&L - {label} ({len(trades)} trades, Rs{TRADE_SIZE:,} per trade)")
    ax.set_xlabel("Trade number (in order of exit time)")
    ax.set_ylabel("Cumulative P&L (Rs)")
    ax.grid(True)
    plt.tight_layout()
    fname = f"multi_{label.lower().replace(' ', '_')}_curve.png"
    plt.savefig(fname, dpi=150)
    plt.close()
    print(f"Saved {fname}")


# ---------------- MAIN ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tune", action="store_true")
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    if not (args.tune or args.eval or args.final):
        ap.print_help()
        return

    data = fetch_data(args.refresh)
    features = {t: build_features(d, data["bull"]) for t, d in data["stocks"].items()}

    # Common timeline: skip the first 400 bars (MA400 warm-up), then 50 / 25 / 25
    ref = max(features.values(), key=lambda F: len(F["index"]))["index"]
    tl = ref[400:]
    t0, s1, s2 = tl[0], tl[int(len(tl) * 0.50)], tl[int(len(tl) * 0.75)]
    t_end = tl[-1]
    w_train = f"{t0.date()} to {s1.date()}"
    w_val = f"{s1.date()} to {s2.date()}"
    w_test = f"{s2.date()} to {t_end.date()}"
    print(f"Stocks used: {len(features)}")
    print(f"TRAIN {w_train} | VALIDATION {w_val} | FINAL TEST {w_test}\n")

    if STRATEGY == "pullback":
        base = dict(strategy="pullback", adx_min=PB_ADX_MIN, rsi_dip=PB_RSI_DIP,
                    rsi_exit=PB_RSI_EXIT, stop_atr=PB_STOP_ATR, max_hold=PB_MAX_HOLD)
        settings_txt = (f"STRATEGY=pullback, PB_ADX_MIN={PB_ADX_MIN}, PB_RSI_DIP={PB_RSI_DIP}, "
                        f"PB_RSI_EXIT={PB_RSI_EXIT}, PB_STOP_ATR={PB_STOP_ATR}, PB_MAX_HOLD={PB_MAX_HOLD}")
    else:
        base = dict(strategy="original", adx_min=ADX_MIN, chop_pass=CHOP_MIN_PASS, stop_mode=STOP_MODE,
                    stop_value=STOP_VALUE, regime=USE_REGIME_FILTER)
        settings_txt = (f"STRATEGY=original, ADX_MIN={ADX_MIN}, CHOP_MIN_PASS={CHOP_MIN_PASS}, "
                        f"STOP={STOP_MODE} {STOP_VALUE}, regime={USE_REGIME_FILTER}")

    if args.tune and STRATEGY == "pullback":
        print("TUNING PULLBACK STRATEGY ON TRAIN DATA ONLY (validation and final test are not used)\n")
        print(f"{'ADX':>4} {'dip':>4} {'exit':>5} {'stopATR':>8} {'trades':>7} {'win%':>6} {'PF':>6} {'avg%/trade':>11} {'totalPnL':>10}")
        for adx_min in (15, 20, 25):
            for dip in (35, 40, 45):
                for ex in (55, 60, 65):
                    for st in (2.0, 3.0):
                        p = dict(base, adx_min=adx_min, rsi_dip=dip, rsi_exit=ex, stop_atr=st)
                        s_ = stats(run_period(features, t0, s1, **p))
                        flag = "  <- few trades" if s_["n"] < 60 else ""
                        print(f"{adx_min:>4} {dip:>4} {ex:>5} {st:>8} {s_['n']:>7} {s_['win']:>6} {s_['pf']:>6} "
                              f"{s_['avg']:>11} {s_['total']:>10}{flag}")
        print("\nPick ONE row (enough trades, PF above 1), put it in the PB_ settings, then run --eval.")
        return

    if args.tune:
        print("TUNING ON TRAIN DATA ONLY (validation and final test are not used)\n")
        print(f"{'ADX':>4} {'chop':>5} {'stop':>10} {'trades':>7} {'win%':>6} {'PF':>6} {'avg%/trade':>11} {'totalPnL':>10}")
        stops = [("pct", 0.015), ("pct", 0.025), ("atr", 2.0), ("atr", 3.0), ("atr", 4.0)]
        for adx_min in (20, 24, 28):
            for chop in (5, 4):
                for mode, val in stops:
                    p = dict(base, adx_min=adx_min, chop_pass=chop, stop_mode=mode, stop_value=val)
                    s = stats(run_period(features, t0, s1, **p))
                    stop_txt = f"{val * 100:.1f}%" if mode == "pct" else f"{val:.0f}xATR"
                    flag = "  <- few trades" if s["n"] < 60 else ""
                    print(f"{adx_min:>4} {chop:>5} {stop_txt:>10} {s['n']:>7} {s['win']:>6} {s['pf']:>6} "
                          f"{s['avg']:>11} {s['total']:>10}{flag}")
        print("\nPick ONE row (enough trades, PF above 1, sensible win rate), put it in SETTINGS,")
        print("then run --eval. Do not run --final until you are completely done.")
        return

    if args.eval:
        print(f"Settings: {settings_txt}, cost/side={COST_PER_SIDE}\n")
        tr_t = run_period(features, t0, s1, **base)
        va_t = run_period(features, s1, s2, **base)
        a = report("TRAIN", tr_t, w_train)
        print()
        b = report("VALIDATION", va_t, w_val)
        save_curve(tr_t, "TRAIN")
        save_curve(va_t, "VALIDATION")
        with open("multi_results.txt", "w") as f:
            f.write("\n".join(a) + "\n\n" + "\n".join(b) + "\n")
        return

    if args.final:
        if os.path.exists(LOCK_FILE):
            print(f"The final test was already run (see {LOCK_FILE}). It cannot be run again,")
            print("because looking twice would turn it into a tuning set.")
            return
        print("You are about to run the FINAL TEST. Settings are locked after this.")
        print(f"Settings: {settings_txt}")
        if input("Type YES to continue: ").strip() != "YES":
            print("Cancelled.")
            return
        te_t = run_period(features, s2, None, **base)
        c = report("FINAL TEST", te_t, w_test)
        save_curve(te_t, "FINAL_TEST")
        with open(LOCK_FILE, "w") as f:
            f.write("Final test run on " + str(dt.datetime.now()) + "\n" + "\n".join(c) + "\n")
        print(f"\nResult saved to {LOCK_FILE}")


if __name__ == "__main__":
    main()