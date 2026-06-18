# NIFTY 50 Trading Algorithm

A Python-based algorithmic trading bot that analyses NIFTY 50 index data 
and generates buy/sell signals using technical indicators.

## Strategy
- MA Crossover (MA20 vs MA100)
- RSI (Relative Strength Index)
- ADX (Average Directional Index) trend filter
- Candlestick pattern recognition (Engulfing, Hammer, Morning Star, Shooting Star)
- Long and Short positions
- Trailing stop loss

## Results
- Training period (Jun–Dec 2025): +0.85%
- Testing period (Jan–Jun 2026): +1.39% on unseen data

## Tech Stack
- Python
- yfinance
- pandas
- matplotlib

## Status
Summer 2026: Backtesting phase
September 2026: Live signal generator
