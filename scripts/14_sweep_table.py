#!/usr/bin/env python3
"""
14 — Extract the 17:10 UTC sweep on the Kalshi Mar 01 contract for Table 5
of the paper. Produces a compact table:

  - Per-minute aggregates over 17:05-17:15 UTC
  - One row per minute showing: ts_utc, signed_volume_contracts,
    buy_size, sell_size, mid_open, mid_close, % of full-window volume

The output goes into the paper as Table 5 to support §5.3 (the 17:10 sweep
narrative).

Inputs: data/kalshi/KXKHAMENEIOUT-AKHA-26MAR01__1600_signed.csv
        data/kalshi/KXKHAMENEIOUT-AKHA-26MAR01__candles_minute.csv

Outputs: figures/sweep_17_10_table.csv
         figures/sweep_17_10_table.md  (markdown for paste-into-manuscript)

Usage:
  python scripts/14_sweep_table.py
"""

from __future__ import annotations
from pathlib import Path
import ast

import pandas as pd

KALSHI_DIR = Path("data/kalshi")
OUT = Path("figures")
OUT.mkdir(exist_ok=True)

TICKER = "KXKHAMENEIOUT-AKHA-26MAR01"

ZOOM_START = pd.Timestamp("2026-02-28 17:05", tz="UTC")
ZOOM_END = pd.Timestamp("2026-02-28 17:15", tz="UTC")
WINDOW_START = pd.Timestamp("2026-02-28 14:00", tz="UTC")
WINDOW_END = pd.Timestamp("2026-02-28 18:00", tz="UTC")


def parse_close(s):
    if pd.isna(s) or s == "{}":
        return None
    d = ast.literal_eval(s) if isinstance(s, str) else s
    v = d.get("close_dollars") if isinstance(d, dict) else None
    return float(v) if v is not None else None


def main():
    trades = pd.read_csv(
        KALSHI_DIR / f"{TICKER}__1600_signed.csv",
        parse_dates=["ts_utc"],
    )
    candles = pd.read_csv(
        KALSHI_DIR / f"{TICKER}__candles_minute.csv",
        parse_dates=["ts_utc"],
    )
    candles["bid"] = candles["yes_bid"].apply(parse_close)
    candles["ask"] = candles["yes_ask"].apply(parse_close)
    candles["mid"] = (candles["bid"] + candles["ask"]) / 2

    # Total signed volume in the 14:00-18:00 window for percent calculation
    win_trades = trades[(trades["ts_utc"] >= WINDOW_START) & (trades["ts_utc"] <= WINDOW_END)]
    total_window_volume = win_trades["size"].sum()

    # Restrict to the 10-minute zoom
    z = trades[(trades["ts_utc"] >= ZOOM_START) & (trades["ts_utc"] <= ZOOM_END)].copy()
    z["minute"] = z["ts_utc"].dt.floor("1min")

    # Per-minute aggregates
    rows = []
    for minute, g in z.groupby("minute"):
        buys = g[g["sign"] == +1]["size"].sum()
        sells = g[g["sign"] == -1]["size"].sum()
        net = g["signed_size"].sum()
        n_trades = len(g)

        cmin = candles[candles["ts_utc"] == minute]
        if not cmin.empty:
            mid_close = cmin["mid"].iloc[0]
        else:
            mid_close = None

        rows.append({
            "minute_utc": minute.strftime("%H:%M"),
            "n_trades": n_trades,
            "buy_size": int(buys),
            "sell_size": int(sells),
            "net_signed": int(net),
            "mid_close": round(mid_close, 4) if mid_close is not None else None,
            "pct_of_window_volume": round(100 * (buys + sells) / total_window_volume, 2),
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "sweep_17_10_table.csv", index=False)

    # Markdown
    md_lines = [
        "**Table 5: Per-minute order flow around the 17:10 UTC sweep on Kalshi Mar 01.**",
        "",
        "| Minute (UTC) | Trades | Buy size | Sell size | Net signed | Kalshi mid | % of 14:00-18:00 window volume |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        md_lines.append(
            f"| {r['minute_utc']} | {r['n_trades']} | {r['buy_size']:,} | {r['sell_size']:,} | "
            f"{r['net_signed']:+,} | {r['mid_close']} | {r['pct_of_window_volume']}% |"
        )
    md_lines.append("")
    md_lines.append(
        f"Notes: signed-volume sums computed from explicit Kalshi `taker_side` flags. "
        f"Window volume denominator is total contracts traded across all 14:00-18:00 UTC trades on the Mar 01 contract "
        f"(N = {int(total_window_volume):,} contracts)."
    )

    md_text = "\n".join(md_lines)
    (OUT / "sweep_17_10_table.md").write_text(md_text)

    print("=== 17:10 sweep table ===")
    print(df.to_string(index=False))
    print()
    print(f"Total window volume (denominator): {int(total_window_volume):,} contracts")
    print(f"\nSaved: {OUT / 'sweep_17_10_table.csv'}")
    print(f"Saved: {OUT / 'sweep_17_10_table.md'}")


if __name__ == "__main__":
    main()
