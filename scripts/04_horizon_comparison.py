#!/usr/bin/env python3
"""
04 — Build Figure 4 of the paper: three matched Polymarket/Kalshi pairs around
the Feb 28, 2026 strike, showing the wedge declines monotonically with horizon.

Three panels:
  Polymarket Feb 28 -> Kalshi Mar 01  (1-day mismatch, headline)
  Polymarket Mar 31 -> Kalshi Apr 01  (1-day mismatch, 31-day horizon)
  Polymarket Dec 31 -> Kalshi Sep 01  (4-month mismatch — loose, 184-day horizon)

Outputs:
  figures/horizon_comparison.png
  figures/horizon_summary.csv

Usage:
  python scripts/04_horizon_comparison.py
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

PAIRS = [
    {
        "label": "Polymarket Feb 28  vs  Kalshi Mar 01",
        "poly_slug": "khamenei-out-as-supreme-leader-of-iran-by-february-28",
        "kalshi_ticker": "KXKHAMENEIOUT-AKHA-26MAR01",
        "horizon_days": 1,
    },
    {
        "label": "Polymarket Mar 31  vs  Kalshi Apr 01",
        "poly_slug": "khamenei-out-as-supreme-leader-of-iran-by-march-31",
        "kalshi_ticker": "KXKHAMENEIOUT-AKHA-26APR01",
        "horizon_days": 31,
    },
    {
        "label": "Polymarket Dec 31  vs  Kalshi Sep 01",
        "poly_slug": "khamenei-out-as-supreme-leader-of-iran-by-december-31-2026",
        "kalshi_ticker": "KXKHAMENEIOUT-AKHA-26SEP01",
        "horizon_days": 184,
    },
]


def parse_close(s):
    if pd.isna(s) or s == "{}":
        return None
    d = ast.literal_eval(s) if isinstance(s, str) else s
    v = d.get("close_dollars") if isinstance(d, dict) else None
    return float(v) if v is not None else None


def load_poly(slug: str) -> pd.DataFrame:
    p = pd.read_csv(
        f"data/polymarket/{slug}__yes_minute_event_window.csv",
        parse_dates=["ts_utc"],
    )
    return p.rename(columns={"mid": "p_poly"})[["ts_utc", "p_poly"]]


def load_kalshi(ticker: str) -> pd.DataFrame:
    k = pd.read_csv(
        f"data/kalshi/{ticker}__candles_minute.csv", parse_dates=["ts_utc"]
    )
    k["bid"] = k["yes_bid"].apply(parse_close)
    k["ask"] = k["yes_ask"].apply(parse_close)
    k["p_kalshi"] = (k["bid"] + k["ask"]) / 2
    return k[["ts_utc", "p_kalshi"]].dropna()


def merge_pair(poly: pd.DataFrame, kalshi: pd.DataFrame, freq: str = "1min") -> pd.DataFrame:
    p = poly.set_index("ts_utc").resample(freq)["p_poly"].mean().ffill()
    k = kalshi.set_index("ts_utc").resample(freq)["p_kalshi"].mean().ffill()
    w = pd.concat([p, k], axis=1, sort=True).dropna(subset=["p_poly", "p_kalshi"])
    w["W"] = w["p_poly"] - w["p_kalshi"]
    return w.reset_index()


def main():
    fig, axes = plt.subplots(3, 1, figsize=(13, 11), sharex=True)
    news_ts = pd.Timestamp("2026-02-28 06:15", tz="UTC")
    halt_ts = pd.Timestamp("2026-03-01 03:06:25", tz="UTC")
    plateau_start = pd.Timestamp("2026-02-28 22:00", tz="UTC")

    rows = []
    for ax, pair in zip(axes, PAIRS):
        poly = load_poly(pair["poly_slug"])
        kalshi = load_kalshi(pair["kalshi_ticker"])
        w = merge_pair(poly, kalshi)
        mask = (w["ts_utc"] >= "2026-02-27 18:00") & (w["ts_utc"] <= "2026-03-01 04:00")
        w = w[mask]

        ax.plot(w["ts_utc"], w["p_poly"], label="Polymarket", color="#1f77b4", linewidth=1.1)
        ax.plot(w["ts_utc"], w["p_kalshi"], label="Kalshi", color="#d62728", linewidth=1.1)
        ax.fill_between(
            w["ts_utc"], w["p_kalshi"], w["p_poly"],
            where=(w["p_poly"] > w["p_kalshi"]),
            alpha=0.15, color="black", label="Wedge",
        )
        ax.set_ylim(-0.02, 1.05)
        ax.set_ylabel("YES price")
        ax.grid(alpha=0.3)
        ax.axhline(1.0, ls=":", alpha=0.3, color="grey")
        ax.axhline(0.0, ls=":", alpha=0.3, color="grey")
        ax.axvline(news_ts, ls="--", alpha=0.6, color="black", lw=0.8)
        ax.axvline(halt_ts, ls=":", alpha=0.6, color="black", lw=0.8)

        plateau = w[(w["ts_utc"] >= plateau_start) & (w["ts_utc"] <= halt_ts)]
        plateau_W = plateau["W"].mean()
        plateau_poly = plateau["p_poly"].mean()
        plateau_kalshi = plateau["p_kalshi"].mean()

        ax.set_title(
            f"{pair['label']}   |   horizon ≈ {pair['horizon_days']} day(s)   |   "
            f"plateau: P_Poly={plateau_poly:.2f}, P_Kalshi={plateau_kalshi:.2f}, W={plateau_W:.2f}",
            fontsize=10,
        )
        ax.legend(loc="upper left", fontsize=8, framealpha=0.95)

        rows.append({
            "pair": pair["label"],
            "horizon_days": pair["horizon_days"],
            "plateau_poly": round(plateau_poly, 4),
            "plateau_kalshi": round(plateau_kalshi, 4),
            "plateau_wedge": round(plateau_W, 4),
        })

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b %d %H:%M"))
    axes[-1].set_xlabel("UTC")
    fig.suptitle(
        "Settlement-wedge across the Khamenei contract horizon\n"
        "Three matched Polymarket/Kalshi pairs around the Feb 28, 2026 strike",
        fontsize=13, y=0.995,
    )
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT / "horizon_comparison.png", dpi=160, bbox_inches="tight")
    print(f"Saved: {OUT / 'horizon_comparison.png'}")

    sdf = pd.DataFrame(rows)
    sdf.to_csv(OUT / "horizon_summary.csv", index=False)
    print("\n=== Horizon summary ===")
    print(sdf.to_string(index=False))


if __name__ == "__main__":
    main()
