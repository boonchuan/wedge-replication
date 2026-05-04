"""Compute realized notional traded for each Kalshi Khamenei contract."""
import pandas as pd
from pathlib import Path

KALSHI_DIR = Path("data/kalshi")
TICKERS = [
    "KXKHAMENEIOUT-AKHA-26MAR01",
    "KXKHAMENEIOUT-AKHA-26APR01",
    "KXKHAMENEIOUT-AKHA-26JUL01",
    "KXKHAMENEIOUT-AKHA-26SEP01",
]

def fmt(v):
    if v >= 1_000_000: return f"${v/1_000_000:.1f}M"
    if v >= 1_000: return f"${v/1_000:.1f}K"
    return f"${v:.0f}"

print()
print("Kalshi realized notional traded (sum of count_fp * yes_price_dollars):")
print()
for ticker in TICKERS:
    p = KALSHI_DIR / f"{ticker}__trades.csv"
    if not p.exists():
        print(f"  {ticker}: missing")
        continue
    df = pd.read_csv(p)
    notional = (df["count_fp"] * df["yes_price_dollars"]).sum()
    n_trades = len(df)
    print(f"  {ticker}: {fmt(notional)} ({n_trades:,} trades)")
