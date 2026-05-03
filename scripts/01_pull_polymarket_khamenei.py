#!/usr/bin/env python3
"""
01 — Pull Polymarket data for the three Khamenei contracts.

Pulls from the public Gamma metadata API and the public CLOB price-history
endpoint. No authentication required.

For each contract:
  - market metadata (slug, conditionId, CLOB token IDs, dates, volume)
  - full-lifecycle hourly midprice
  - minute-resolution midprice for the Feb 26 - Mar 2 event window
  - trades up to the API's 3,500-offset pagination cap

Outputs (under data/polymarket/):
  <slug>__metadata.json
  <slug>__yes_hourly_lifecycle.csv
  <slug>__yes_minute_event_window.csv
  <slug>__trades.csv

Usage:
  python scripts/01_pull_polymarket_khamenei.py
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
DATA_API = "https://data-api.polymarket.com"

OUT = Path("data/polymarket")
OUT.mkdir(parents=True, exist_ok=True)

SLUGS = [
    "khamenei-out-as-supreme-leader-of-iran-by-february-28",
    "khamenei-out-as-supreme-leader-of-iran-by-march-31",
    "khamenei-out-as-supreme-leader-of-iran-by-december-31-2026",
]

# Event-window (minute fidelity)
EVENT_START = pd.Timestamp("2026-02-26", tz="UTC")
EVENT_END = pd.Timestamp("2026-03-02", tz="UTC")
LIFECYCLE_END = pd.Timestamp("2026-03-05", tz="UTC")

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "wedge-replication/1.0"})


def get_market_meta(slug: str) -> Optional[dict]:
    """Find a Polymarket market by slug. Closed/archived markets need
    explicit query flags."""
    r = SESSION.get(
        f"{GAMMA}/markets",
        params={"slug": slug, "closed": "true", "archived": "true", "limit": 5},
        timeout=20,
    )
    r.raise_for_status()
    arr = r.json()
    if not arr:
        return None
    # Filter to exact slug match
    return next((m for m in arr if m.get("slug") == slug), arr[0])


def prices_history(token_id: str, start_ts: int, end_ts: int,
                   fidelity: int = 60, chunk_days: int = 7) -> pd.DataFrame:
    """Paginate the prices-history endpoint over time. fidelity is in minutes."""
    rows: list[dict] = []
    chunk_seconds = chunk_days * 86400
    cur = start_ts
    while cur < end_ts:
        seg_end = min(cur + chunk_seconds, end_ts)
        params = {
            "market": token_id,
            "startTs": cur,
            "endTs": seg_end,
            "fidelity": fidelity,
        }
        r = SESSION.get(f"{CLOB}/prices-history", params=params, timeout=30)
        r.raise_for_status()
        chunk = r.json().get("history") or []
        rows.extend(chunk)
        cur = seg_end
        time.sleep(0.2)
    if not rows:
        return pd.DataFrame(columns=["ts_utc", "mid"])
    df = pd.DataFrame(rows)
    df["ts_utc"] = pd.to_datetime(df["t"], unit="s", utc=True)
    df = df.rename(columns={"p": "mid"}).sort_values("ts_utc").drop_duplicates("ts_utc")
    return df[["ts_utc", "mid"]].reset_index(drop=True)


def fetch_trades(condition_id: str, max_offset: int = 3500) -> pd.DataFrame:
    """Trades are paginated by offset; the Data API caps at offset 3500."""
    all_rows = []
    offset = 0
    page = 500
    while offset < max_offset:
        try:
            r = SESSION.get(
                f"{DATA_API}/trades",
                params={"market": condition_id, "limit": page, "offset": offset},
                timeout=30,
            )
            r.raise_for_status()
        except requests.HTTPError as e:
            print(f"  trades: ERROR {e}")
            break
        chunk = r.json()
        if not chunk:
            break
        all_rows.extend(chunk)
        if len(chunk) < page:
            break
        offset += page
        time.sleep(0.2)

    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows)
    if "timestamp" in df.columns:
        df["ts_utc"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    return df.sort_values("ts_utc" if "ts_utc" in df.columns else df.columns[0]).reset_index(drop=True)


def main():
    for slug in SLUGS:
        print(f"\n=== {slug} ===")
        mkt = get_market_meta(slug)
        if mkt is None:
            print(f"  [WARN] no market found for slug={slug}")
            continue

        cid = mkt.get("conditionId")
        question = mkt.get("question")
        end_iso = mkt.get("endDate")
        volume = mkt.get("volume")
        liquidity = mkt.get("liquidity")
        token_ids = mkt.get("clobTokenIds")
        if isinstance(token_ids, str):
            token_ids = json.loads(token_ids)
        yes_tid = token_ids[0] if token_ids else None

        print(f"  conditionId: {cid}")
        print(f"  question:    {question}")
        print(f"  end_date:    {end_iso}")
        print(f"  volume:      {volume}")
        print(f"  liquidity:   {liquidity}")
        print(f"  YES token:   {yes_tid}")

        with open(OUT / f"{slug}__metadata.json", "w") as f:
            json.dump(mkt, f, default=str, indent=2)

        if not yes_tid:
            print("  [WARN] no YES token; skipping price/trade pulls")
            continue

        # Lifecycle hourly: from market startDate to Mar 5
        sd_str = mkt.get("startDate") or mkt.get("start_date_iso") or "2026-01-01"
        sd = pd.Timestamp(sd_str)
        if sd.tz is None:
            sd = sd.tz_localize("UTC")
        else:
            sd = sd.tz_convert("UTC")
        lifecycle_start = int(sd.timestamp())
        lifecycle_end = int(LIFECYCLE_END.timestamp())
        px = prices_history(yes_tid, lifecycle_start, lifecycle_end, fidelity=60, chunk_days=7)
        px.to_csv(OUT / f"{slug}__yes_hourly_lifecycle.csv", index=False)
        if not px.empty:
            print(f"  hourly price points: {len(px)} ({px['ts_utc'].min()} -> {px['ts_utc'].max()})")

        # Event window minute fidelity
        ev_start = int(EVENT_START.timestamp())
        ev_end = int(EVENT_END.timestamp())
        pxm = prices_history(yes_tid, ev_start, ev_end, fidelity=1, chunk_days=2)
        pxm.to_csv(OUT / f"{slug}__yes_minute_event_window.csv", index=False)
        print(f"  minute price points (event window): {len(pxm)}")

        # Trades (capped)
        trades = fetch_trades(cid)
        if not trades.empty:
            trades.to_csv(OUT / f"{slug}__trades.csv", index=False)
            print(f"  trades: {len(trades)}")


if __name__ == "__main__":
    main()
