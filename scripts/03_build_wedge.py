#!/usr/bin/env python3
"""
03 — Build Figure 1 of the paper: Polymarket Feb 28 vs Kalshi Mar 01 wedge
during the Feb 28, 2026 strike repricing.

Two-panel chart:
  Top:    YES price for both venues, with news-arrival and Kalshi-halt markers
  Bottom: wedge W = P_Poly - P_Kalshi shaded

Inputs:
  data/polymarket/khamenei-out-as-supreme-leader-of-iran-by-february-28__yes_minute_event_window.csv
  data/kalshi/KXKHAMENEIOUT-AKHA-26MAR01__candles_minute.csv

Outputs:
  figures/wedge_khamenei_feb28.png

Usage:
  python scripts/03_build_wedge.py
"""

from __future__ import annotations
from pathlib import Path
import ast

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

OUT = Path("figures")
OUT.mkdir(exist_ok=True)

POLY_SLUG = "khamenei-out-as-supreme-leader-of-iran-by-february-28"
KALSHI_TICKER = "KXKHAMENEIOUT-AKHA-26MAR01"

WIN_START = pd.Timestamp("2026-02-27 18:00", tz="UTC")
WIN_END = pd.Timestamp("2026-03-01 04:00", tz="UTC")
NEWS_ARRIVAL = pd.Timestamp("2026-02-28 06:15", tz="UTC")
KALSHI_HALT = pd.Timestamp("2026-03-01 03:06:25", tz="UTC")


def parse_close(s):
    if pd.isna(s) or s == "{}":
        return None
    d = ast.literal_eval(s) if isinstance(s, str) else s
    v = d.get("close_dollars") if isinstance(d, dict) else None
    return float(v) if v is not None else None


def load_poly() -> pd.DataFrame:
    p = pd.read_csv(
        f"data/polymarket/{POLY_SLUG}__yes_minute_event_window.csv",
        parse_dates=["ts_utc"],
    )
    return p.rename(columns={"mid": "p_poly"})[["ts_utc", "p_poly"]]


def load_kalshi() -> pd.DataFrame:
    k = pd.read_csv(
        f"data/kalshi/{KALSHI_TICKER}__candles_minute.csv", parse_dates=["ts_utc"]
    )
    k["bid"] = k["yes_bid"].apply(parse_close)
    k["ask"] = k["yes_ask"].apply(parse_close)
    k["p_kalshi"] = (k["bid"] + k["ask"]) / 2
    return k[["ts_utc", "p_kalshi"]].dropna()


def main():
    poly = load_poly()
    kalshi = load_kalshi()

    # Resample to common 1-minute grid
    p = poly.set_index("ts_utc").resample("1min")["p_poly"].mean().ffill()
    k = kalshi.set_index("ts_utc").resample("1min")["p_kalshi"].mean().ffill()
    df = pd.concat([p, k], axis=1, sort=True).dropna()
    df["W"] = df["p_poly"] - df["p_kalshi"]
    df = df.reset_index()
    df = df[(df["ts_utc"] >= WIN_START) & (df["ts_utc"] <= WIN_END)]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(13, 7), sharex=True,
        gridspec_kw={"height_ratios": [2, 1]},
    )

    ax1.plot(df["ts_utc"], df["p_poly"], label="Polymarket (YES mid)", color="#1f77b4", lw=1.0)
    ax1.plot(df["ts_utc"], df["p_kalshi"], label="Kalshi (YES mid)", color="#d62728", lw=1.0)
    ax1.axhline(1.0, ls=":", c="grey", alpha=0.4)
    ax1.axhline(0.0, ls=":", c="grey", alpha=0.4)
    ax1.axvline(NEWS_ARRIVAL, ls="--", c="black", alpha=0.6, lw=0.8)
    ax1.axvline(KALSHI_HALT, ls=":", c="black", alpha=0.6, lw=0.8)
    ax1.text(NEWS_ARRIVAL, 0.92, " news arrival\n 06:15 UTC", fontsize=9, va="top")
    ax1.text(KALSHI_HALT, 0.92, " Kalshi halt\n 03:06 UTC", fontsize=9, va="top", ha="right")
    ax1.set_ylim(-0.02, 1.05)
    ax1.set_ylabel("YES price (USD)")
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(alpha=0.3)
    ax1.set_title(
        "Khamenei out as Supreme Leader — Polymarket Feb 28 vs Kalshi Mar 01\n"
        "Cross-venue YES price during the Feb 28 strike repricing",
        fontsize=11,
    )

    ax2.plot(df["ts_utc"], df["W"], color="black", lw=0.8)
    ax2.fill_between(df["ts_utc"], 0, df["W"], where=(df["W"] > 0),
                     color="grey", alpha=0.3)
    ax2.fill_between(df["ts_utc"], 0, df["W"], where=(df["W"] < 0),
                     color="#d62728", alpha=0.3)
    ax2.axhline(0, c="grey", lw=0.5)
    ax2.axvline(NEWS_ARRIVAL, ls="--", c="black", alpha=0.6, lw=0.8)
    ax2.axvline(KALSHI_HALT, ls=":", c="black", alpha=0.6, lw=0.8)
    ax2.set_ylabel("Wedge  W = P_Poly − P_Kalshi")
    ax2.set_xlabel("UTC")
    ax2.grid(alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d %H:%M"))
    fig.autofmt_xdate()

    fig.tight_layout()
    fig.savefig(OUT / "wedge_khamenei_feb28.png", dpi=160, bbox_inches="tight")
    print(f"Saved: {OUT / 'wedge_khamenei_feb28.png'}")

    # Print plateau summary
    plateau_start = pd.Timestamp("2026-02-28 22:00", tz="UTC")
    plateau = df[(df["ts_utc"] >= plateau_start) & (df["ts_utc"] <= KALSHI_HALT)]
    print("\n=== Plateau summary (22:00 UTC -> halt) ===")
    print(f"  P_Poly  mean: {plateau['p_poly'].mean():.4f}")
    print(f"  P_Kalshi mean: {plateau['p_kalshi'].mean():.4f}")
    print(f"  Wedge    mean: {plateau['W'].mean():.4f}")


if __name__ == "__main__":
    main()
