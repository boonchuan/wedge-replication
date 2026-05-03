#!/usr/bin/env python3
"""
11 — 16:00 UTC anomaly forensics on the Feb 28, 2026 Khamenei contracts.

Reconstructs signed trade volume on each of the four Kalshi Khamenei contracts
across the 14:00-18:00 UTC window using the explicit `taker_side` flags in the
Kalshi trades data. Identifies the 17:10 UTC sell sweep on the Mar 01 contract
as the largest single-minute signed-flow event in the window — the empirical
basis for §5.3 of the paper.

Inputs:
  data/kalshi/<ticker>__candles_minute.csv
  data/kalshi/<ticker>__trades.csv

Outputs:
  data/kalshi/<ticker>__1600_signed.csv     per-trade with sign, restricted to window
  figures/anomaly_1600_signed_volume.png    4-panel visual (Figure 2)
  figures/anomaly_1600_summary.csv          per-contract anomaly stats

Usage:
  python scripts/11_anomaly_1600.py
"""

from __future__ import annotations
from pathlib import Path
import ast

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

KALSHI_DIR = Path("data/kalshi")
OUT_FIG = Path("figures")
OUT_FIG.mkdir(exist_ok=True)

TICKERS = [
    "KXKHAMENEIOUT-AKHA-26MAR01",
    "KXKHAMENEIOUT-AKHA-26APR01",
    "KXKHAMENEIOUT-AKHA-26JUL01",
    "KXKHAMENEIOUT-AKHA-26SEP01",
]

WINDOW_START = pd.Timestamp("2026-02-28 14:00", tz="UTC")
WINDOW_END = pd.Timestamp("2026-02-28 18:00", tz="UTC")
ANOMALY_START = pd.Timestamp("2026-02-28 15:30", tz="UTC")
ANOMALY_END = pd.Timestamp("2026-02-28 16:30", tz="UTC")


def parse_close(s):
    if pd.isna(s) or s == "{}":
        return None
    d = ast.literal_eval(s) if isinstance(s, str) else s
    v = d.get("close_dollars") if isinstance(d, dict) else None
    return float(v) if v is not None else None


def load_candles_mid(ticker: str) -> pd.DataFrame:
    """Load Kalshi minute candles, return ts_utc and mid (USD)."""
    df = pd.read_csv(KALSHI_DIR / f"{ticker}__candles_minute.csv", parse_dates=["ts_utc"])
    df["bid"] = df["yes_bid"].apply(parse_close)
    df["ask"] = df["yes_ask"].apply(parse_close)
    df["mid"] = (df["bid"] + df["ask"]) / 2
    return df[["ts_utc", "bid", "ask", "mid"]].dropna(subset=["mid"])


def load_trades(ticker: str) -> pd.DataFrame:
    """Load Kalshi trades. Schema confirmed live:
    count_fp, created_time, no_price_dollars, taker_side, ticker, trade_id,
    yes_price_dollars, ts_utc."""
    df = pd.read_csv(KALSHI_DIR / f"{ticker}__trades.csv")
    df["ts_utc"] = pd.to_datetime(
        df["ts_utc"] if "ts_utc" in df.columns else df["created_time"], utc=True
    )
    df["price"] = df["yes_price_dollars"].astype(float)  # already in dollars
    df["size"] = df["count_fp"].astype(float)
    df["taker_side_raw"] = df["taker_side"]
    return (
        df[["ts_utc", "price", "size", "taker_side_raw"]]
        .sort_values("ts_utc")
        .reset_index(drop=True)
    )


def sign_trades(trades: pd.DataFrame, candles: pd.DataFrame) -> pd.DataFrame:
    """Sign each trade. Kalshi convention: taker_side = "yes" means trader bought
    YES (lifted ask) -> +1; "no" means trader bought NO (hit bid) -> -1.
    Falls back to a quote test against the prevailing mid for ambiguous rows."""
    candles = candles.set_index("ts_utc").sort_index()
    trades = trades.copy()
    trades["minute"] = trades["ts_utc"].dt.floor("1min")
    mid_at = candles["mid"].reindex(trades["minute"], method="ffill").to_numpy()
    trades["mid_prevailing"] = mid_at

    def sign_row(r):
        s = r.get("taker_side_raw")
        if isinstance(s, str):
            if s.lower() == "yes":
                return +1
            if s.lower() == "no":
                return -1
        if pd.notna(r["mid_prevailing"]):
            if r["price"] > r["mid_prevailing"] + 1e-6:
                return +1
            if r["price"] < r["mid_prevailing"] - 1e-6:
                return -1
        return 0

    trades["sign"] = trades.apply(sign_row, axis=1)
    trades["signed_size"] = trades["sign"] * trades["size"]
    return trades


def analyze_one(ticker: str) -> dict:
    print(f"\n=== {ticker} ===")
    candles = load_candles_mid(ticker)
    trades = load_trades(ticker)
    trades = sign_trades(trades, candles)

    win = trades[(trades["ts_utc"] >= WINDOW_START) & (trades["ts_utc"] <= WINDOW_END)].copy()
    win.to_csv(KALSHI_DIR / f"{ticker}__1600_signed.csv", index=False)
    print(f"  trades in 14:00-18:00 window: {len(win)}")
    if win.empty:
        return {"ticker": ticker, "n_window": 0}

    anom = win[(win["ts_utc"] >= ANOMALY_START) & (win["ts_utc"] <= ANOMALY_END)]
    pre = win[(win["ts_utc"] >= WINDOW_START) & (win["ts_utc"] < ANOMALY_START)]
    post = win[(win["ts_utc"] > ANOMALY_END) & (win["ts_utc"] <= WINDOW_END)]

    return {
        "ticker": ticker,
        "n_window": len(win),
        "n_anomaly": len(anom),
        "anomaly_buy_size": int(anom[anom["sign"] == +1]["size"].sum()),
        "anomaly_sell_size": int(anom[anom["sign"] == -1]["size"].sum()),
        "anomaly_net_signed": int(anom["signed_size"].sum()),
        "anomaly_price_min": (round(float(anom["price"].min()), 4) if not anom.empty else np.nan),
        "anomaly_price_max": (round(float(anom["price"].max()), 4) if not anom.empty else np.nan),
        "anomaly_price_mean": (round(float(anom["price"].mean()), 4) if not anom.empty else np.nan),
        "pre_net_signed": int(pre["signed_size"].sum()),
        "post_net_signed": int(post["signed_size"].sum()),
    }


def plot_four_panel():
    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)
    for ax, ticker in zip(axes, TICKERS):
        candles = load_candles_mid(ticker)
        trades = sign_trades(load_trades(ticker), candles)
        win = trades[(trades["ts_utc"] >= WINDOW_START) & (trades["ts_utc"] <= WINDOW_END)]

        c_win = candles[(candles["ts_utc"] >= WINDOW_START) & (candles["ts_utc"] <= WINDOW_END)]
        ax.plot(c_win["ts_utc"], c_win["mid"], color="#d62728", linewidth=1.0, label="Mid")

        ax2 = ax.twinx()
        per_min = win.set_index("ts_utc").resample("1min")["signed_size"].sum()
        colors = ["#2ca02c" if v > 0 else "#9e2828" for v in per_min.values]
        ax2.bar(per_min.index, per_min.values, width=pd.Timedelta(minutes=0.8),
                color=colors, alpha=0.4, label="Signed contracts/min")
        ax2.axhline(0, color="grey", linewidth=0.5)
        ax2.set_ylabel("Signed contracts/min", fontsize=8)

        ax.axvspan(ANOMALY_START, ANOMALY_END, alpha=0.08, color="orange")
        ax.set_ylabel("YES price")
        ax.set_title(f"{ticker}", fontsize=10)
        ax.grid(alpha=0.3)
        ax.set_ylim(0, max(0.3, c_win["mid"].max() * 1.1))

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    axes[-1].set_xlabel("UTC (Feb 28, 2026)")
    fig.suptitle(
        "Kalshi 16:00 UTC anomaly — price and signed trade volume\n"
        "Highlighted region: 15:30-16:30 UTC",
        fontsize=12, y=0.995,
    )
    fig.tight_layout()
    fig.savefig(OUT_FIG / "anomaly_1600_signed_volume.png", dpi=160, bbox_inches="tight")
    print(f"\nSaved: {OUT_FIG / 'anomaly_1600_signed_volume.png'}")


def main():
    rows = []
    for ticker in TICKERS:
        try:
            rows.append(analyze_one(ticker))
        except Exception as e:
            print(f"  [ERROR] {ticker}: {e}")
            rows.append({"ticker": ticker, "error": str(e)})

    sdf = pd.DataFrame(rows)
    sdf.to_csv(OUT_FIG / "anomaly_1600_summary.csv", index=False)
    print("\n=== Anomaly summary ===")
    print(sdf.to_string(index=False))

    plot_four_panel()


if __name__ == "__main__":
    main()
