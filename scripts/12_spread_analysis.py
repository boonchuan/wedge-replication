#!/usr/bin/env python3
"""
Session 1.2 — Spread analysis across regimes.

Question: did Kalshi spreads change between pre-news, news-arrival, path-resolution,
and plateau regimes? If spreads stay tight throughout, the wedge is structural,
not liquidity-driven. If spreads widen during the plateau, that's evidence of
inventory risk priced into the carveout-binding state.

Method:
  1. Load minute candles for all four Kalshi contracts.
  2. Compute spread = ask - bid.
  3. Classify each minute by regime based on Polymarket Feb 28 price arc.
  4. Compute mean / median / 95th-pct spread per regime per contract.
  5. Plot spread time-series with regime shading.

Run on OrangeVPS:
  cd /home/delta-dev/research/settlement_wedge
  source .venv/bin/activate
  python3 12_spread_analysis.py
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
OUT = Path("figures")
OUT.mkdir(exist_ok=True)

TICKERS = [
    "KXKHAMENEIOUT-AKHA-26MAR01",
    "KXKHAMENEIOUT-AKHA-26APR01",
    "KXKHAMENEIOUT-AKHA-26JUL01",
    "KXKHAMENEIOUT-AKHA-26SEP01",
]

# Regime boundaries (UTC) identified from Polymarket Feb 28 price arc
REGIMES = {
    "pre_news":      (pd.Timestamp("2026-02-27 18:00", tz="UTC"), pd.Timestamp("2026-02-28 06:14", tz="UTC")),
    "news_arrival":  (pd.Timestamp("2026-02-28 06:15", tz="UTC"), pd.Timestamp("2026-02-28 13:00", tz="UTC")),
    "path_resolve":  (pd.Timestamp("2026-02-28 13:00", tz="UTC"), pd.Timestamp("2026-02-28 19:00", tz="UTC")),
    "plateau":       (pd.Timestamp("2026-02-28 19:00", tz="UTC"), pd.Timestamp("2026-03-01 03:06", tz="UTC")),
}


def parse_close(s):
    if pd.isna(s) or s == "{}":
        return None
    d = ast.literal_eval(s) if isinstance(s, str) else s
    v = d.get("close_dollars") if isinstance(d, dict) else None
    return float(v) if v is not None else None


def load_kalshi_with_spread(ticker: str) -> pd.DataFrame:
    df = pd.read_csv(KALSHI_DIR / f"{ticker}__candles_minute.csv", parse_dates=["ts_utc"])
    df["bid"] = df["yes_bid"].apply(parse_close)
    df["ask"] = df["yes_ask"].apply(parse_close)
    df["mid"] = (df["bid"] + df["ask"]) / 2
    df["spread"] = df["ask"] - df["bid"]
    return df[["ts_utc", "bid", "ask", "mid", "spread"]].dropna()


def classify_regime(ts: pd.Timestamp) -> str:
    for name, (s, e) in REGIMES.items():
        if s <= ts < e:
            return name
    return "out_of_window"


def regime_summary(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    df = df.copy()
    df["regime"] = df["ts_utc"].apply(classify_regime)
    df = df[df["regime"] != "out_of_window"]

    # Drop the halt-state spreads (1.0 = halted book) so we measure trading spreads
    df = df[df["spread"] < 0.99]

    out = (df.groupby("regime")["spread"]
             .agg(["count", "mean", "median",
                   lambda x: x.quantile(0.95)])
             .rename(columns={"<lambda_0>": "p95"})
             .round(4))
    out["ticker"] = ticker
    return out.reset_index()


def plot_spread_panel(stats_per_ticker: dict[str, pd.DataFrame]) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(13, 11), sharex=True)
    for ax, ticker in zip(axes, TICKERS):
        df = load_kalshi_with_spread(ticker)
        win = df[(df["ts_utc"] >= REGIMES["pre_news"][0]) & (df["ts_utc"] <= REGIMES["plateau"][1])].copy()
        # Drop halt artifacts
        plot_df = win[win["spread"] < 0.99]

        # Shade regimes
        for name, (s, e) in REGIMES.items():
            color = {"pre_news": "#cccccc", "news_arrival": "#ffe5b4",
                     "path_resolve": "#ffb380", "plateau": "#ff8866"}[name]
            ax.axvspan(s, e, alpha=0.15, color=color)

        ax.plot(plot_df["ts_utc"], plot_df["spread"], color="black", linewidth=0.7)
        ax.set_ylabel("Spread (USD)")
        ax.set_title(f"{ticker}", fontsize=10)
        ax.set_ylim(0, max(0.05, plot_df["spread"].quantile(0.99) * 1.2))
        ax.grid(alpha=0.3)

        # Annotate regime medians on the right
        for name, (s, e) in REGIMES.items():
            sub = plot_df[(plot_df["ts_utc"] >= s) & (plot_df["ts_utc"] < e)]
            if not sub.empty:
                med = sub["spread"].median()
                mid_ts = s + (e - s) / 2
                ax.text(mid_ts, ax.get_ylim()[1] * 0.92, f"med={med:.3f}",
                        fontsize=7, ha="center", alpha=0.8)

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b %d %H:%M"))
    axes[-1].set_xlabel("UTC")
    # Manual legend for regime colors
    handles = [plt.Rectangle((0,0), 1, 1, fc=c, alpha=0.3, label=l)
               for l, c in [("Pre-news", "#cccccc"), ("News arrival", "#ffe5b4"),
                            ("Path resolution", "#ffb380"), ("Plateau", "#ff8866")]]
    axes[0].legend(handles=handles, loc="upper right", fontsize=7, ncol=4)

    fig.suptitle("Kalshi spread dynamics across regimes (Feb 27 18:00 → Mar 01 03:06 UTC)\n"
                 "Halt-state quotes (spread ≥ $0.99) excluded.",
                 fontsize=12, y=0.995)
    fig.tight_layout()
    fig.savefig(OUT / "spread_regimes.png", dpi=160, bbox_inches="tight")
    print(f"\nSaved figure: {OUT / 'spread_regimes.png'}")


def main():
    all_stats = []
    for ticker in TICKERS:
        df = load_kalshi_with_spread(ticker)
        stats = regime_summary(df, ticker)
        all_stats.append(stats)
        print(f"\n=== {ticker} ===")
        print(stats[["regime", "count", "mean", "median", "p95"]].to_string(index=False))

    combined = pd.concat(all_stats, ignore_index=True)
    combined.to_csv(OUT / "spread_regimes_summary.csv", index=False)
    print(f"\nSaved summary: {OUT / 'spread_regimes_summary.csv'}")

    plot_spread_panel({})


if __name__ == "__main__":
    main()
