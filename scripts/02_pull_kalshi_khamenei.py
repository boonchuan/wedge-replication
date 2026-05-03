#!/usr/bin/env python3
"""
02 — Pull Kalshi data for the four Khamenei contracts.

Pulls from the public Kalshi trade-api v2. No authentication required for
read-only data.

For each contract:
  - market metadata (ticker, status, deadlines, volume, open interest)
  - minute-resolution candlesticks (open, high, low, close, yes_bid, yes_ask,
    volume, open_interest) for the full lifecycle Jan 1 - Mar 5 2026
  - all trades (count_fp, yes_price_dollars, taker_side, ts_utc)

Outputs (under data/kalshi/):
  <ticker>__metadata.json
  <ticker>__candles_minute.csv
  <ticker>__trades.csv

Usage:
  python scripts/02_pull_kalshi_khamenei.py
"""

from __future__ import annotations
import json
import time
from pathlib import Path

import pandas as pd
import requests

API = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = "KXKHAMENEIOUT-AKHA"

OUT = Path("data/kalshi")
OUT.mkdir(parents=True, exist_ok=True)

LIFECYCLE_START = pd.Timestamp("2026-01-01", tz="UTC")
LIFECYCLE_END = pd.Timestamp("2026-03-05", tz="UTC")

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "wedge-replication/1.0"})


def list_markets() -> list[dict]:
    """List markets in the Khamenei series, with nested-market expansion."""
    r = SESSION.get(
        f"{API}/series/{SERIES}/markets",
        params={"with_nested_markets": "true"},
        timeout=20,
    )
    r.raise_for_status()
    payload = r.json()
    # Schema: {"markets": [...]} or {"events": [{"markets": [...]}]}
    if "markets" in payload:
        return payload["markets"]
    if "events" in payload:
        out = []
        for ev in payload["events"]:
            out.extend(ev.get("markets") or [])
        return out
    return []


def fetch_candles(ticker: str) -> pd.DataFrame:
    """Pull minute candlesticks. Endpoint requires start_ts/end_ts in seconds and
    period_interval in minutes (1 for minute fidelity)."""
    rows: list[dict] = []
    chunk_seconds = 7 * 86400  # 7-day chunks
    cur = int(LIFECYCLE_START.timestamp())
    end = int(LIFECYCLE_END.timestamp())
    while cur < end:
        seg_end = min(cur + chunk_seconds, end)
        try:
            r = SESSION.get(
                f"{API}/markets/{ticker}/candlesticks",
                params={"start_ts": cur, "end_ts": seg_end, "period_interval": 1},
                timeout=30,
            )
            r.raise_for_status()
        except requests.HTTPError as e:
            print(f"  candles: ERROR {e}")
            break
        candles = r.json().get("candlesticks") or []
        rows.extend(candles)
        cur = seg_end
        time.sleep(0.3)

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # Normalize timestamp column
    if "end_period_ts" in df.columns:
        df["ts_utc"] = pd.to_datetime(df["end_period_ts"], unit="s", utc=True)
    elif "ts" in df.columns:
        df["ts_utc"] = pd.to_datetime(df["ts"], unit="s", utc=True)
    df = df.sort_values("ts_utc").drop_duplicates("ts_utc").reset_index(drop=True)
    return df


def fetch_trades(ticker: str) -> pd.DataFrame:
    """Paginate trades. Uses cursor-based pagination."""
    rows = []
    cursor = None
    page = 1000
    while True:
        params = {"ticker": ticker, "limit": page}
        if cursor:
            params["cursor"] = cursor
        try:
            r = SESSION.get(f"{API}/markets/trades", params=params, timeout=30)
            r.raise_for_status()
        except requests.HTTPError as e:
            print(f"  trades: ERROR {e}")
            break
        payload = r.json()
        chunk = payload.get("trades") or []
        rows.extend(chunk)
        cursor = payload.get("cursor")
        if not cursor or not chunk:
            break
        time.sleep(0.2)

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # Schema includes count_fp, created_time, yes_price_dollars, no_price_dollars,
    # taker_side, trade_id; we add ts_utc for convenience.
    if "created_time" in df.columns:
        df["ts_utc"] = pd.to_datetime(df["created_time"], utc=True)
    return df.sort_values("ts_utc").reset_index(drop=True)


def main():
    markets = list_markets()
    print(f"Found {len(markets)} markets in series {SERIES}")
    for mkt in markets:
        ticker = mkt.get("ticker")
        if not ticker:
            continue
        print(f"\n=== {ticker} ===")
        with open(OUT / f"{ticker}__metadata.json", "w") as f:
            json.dump(mkt, f, default=str, indent=2)

        candles = fetch_candles(ticker)
        candles.to_csv(OUT / f"{ticker}__candles_minute.csv", index=False)
        print(f"  candles: {len(candles)}")

        trades = fetch_trades(ticker)
        trades.to_csv(OUT / f"{ticker}__trades.csv", index=False)
        print(f"  trades: {len(trades)}")


if __name__ == "__main__":
    main()
