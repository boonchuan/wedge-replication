#!/usr/bin/env python3
"""15 — Audit Table 1 + §4.3 numbers from real data files."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

POLY_DIR = Path("data/polymarket")
KALSHI_DIR = Path("data/kalshi")

POLY_SLUGS = {
    "khamenei-out-as-supreme-leader-of-iran-by-february-28": ("Feb 28, 2026", "Polymarket"),
    "khamenei-out-as-supreme-leader-of-iran-by-march-31": ("Mar 31, 2026", "Polymarket"),
    "khamenei-out-as-supreme-leader-of-iran-by-december-31-2026": ("Dec 31, 2026", "Polymarket"),
}
KALSHI_TICKERS = [
    ("KXKHAMENEIOUT-AKHA-26MAR01", "Mar 1, 2026"),
    ("KXKHAMENEIOUT-AKHA-26APR01", "Apr 1, 2026"),
    ("KXKHAMENEIOUT-AKHA-26JUL01", "Jul 1, 2026"),
    ("KXKHAMENEIOUT-AKHA-26SEP01", "Sep 1, 2026"),
]

def fmt_dollars(v):
    if v is None: return "n/a"
    if v >= 1_000_000: return f"${v/1_000_000:.1f}M"
    if v >= 1_000: return f"${v/1_000:.1f}K"
    return f"${v:.0f}"

print("=" * 70)
print("TABLE 1 — Real values for paste-into-manuscript")
print("=" * 70)
print()
print("| Venue | Identifier | Deadline | Notional volume | Status |")
print("|---|---|---|---:|---|")

poly_total = 0.0
for slug, (deadline, venue) in POLY_SLUGS.items():
    meta_path = POLY_DIR / f"{slug}__metadata.json"
    if not meta_path.exists():
        print(f"| {venue} | (missing) | {deadline} | METADATA MISSING | ? |")
        continue
    meta = json.loads(meta_path.read_text())
    vol = meta.get("volume") or meta.get("volumeNum")
    try: vol = float(vol) if vol is not None else None
    except (TypeError, ValueError): vol = None
    if vol is not None: poly_total += vol
    status = "Resolved YES (early Mar 1)" if "december-31" in slug else "Resolved YES"
    short_id = slug.replace("khamenei-out-as-supreme-leader-of-iran-", "khamenei...")
    print(f"| {venue} | {short_id} | {deadline} | {fmt_dollars(vol)} | {status} |")

for ticker, deadline in KALSHI_TICKERS:
    meta_path = KALSHI_DIR / f"{ticker}__metadata.json"
    if not meta_path.exists():
        print(f"| Kalshi | {ticker} | {deadline} | METADATA MISSING | ? |")
        continue
    meta = json.loads(meta_path.read_text())
    vol_dollars = meta.get("dollar_recent_volume") or meta.get("dollar_volume")
    oi = meta.get("open_interest")
    oi_dollars = meta.get("dollar_open_interest")
    vol_str = ""
    if vol_dollars:
        try: vol_str = fmt_dollars(float(vol_dollars))
        except: pass
    if not vol_str and oi_dollars:
        try: vol_str = f"OI: {fmt_dollars(float(oi_dollars))}"
        except: pass
    if not vol_str and oi:
        vol_str = f"OI: {oi:,} contracts"
    if not vol_str: vol_str = "n/a"
    print(f"| Kalshi | {ticker} | {deadline} | {vol_str} | Halted, paid pre-strike LTP |")

print()
print(f"Polymarket total (matched 3 contracts): {fmt_dollars(poly_total)}")
print()
print("=" * 70)
print("SECTION 4.3 — Real file-size numbers")
print("=" * 70)
print()

mar01_candles = KALSHI_DIR / "KXKHAMENEIOUT-AKHA-26MAR01__candles_minute.csv"
mar01_trades = KALSHI_DIR / "KXKHAMENEIOUT-AKHA-26MAR01__trades.csv"
if mar01_candles.exists():
    n = sum(1 for _ in open(mar01_candles)) - 1
    print(f"Mar 01 Kalshi candles: {n:,} minute observations")
if mar01_trades.exists():
    n = sum(1 for _ in open(mar01_trades)) - 1
    print(f"Mar 01 Kalshi trades: {n:,} trades")

feb28_minute = POLY_DIR / "khamenei-out-as-supreme-leader-of-iran-by-february-28__yes_minute_event_window.csv"
feb28_hourly = POLY_DIR / "khamenei-out-as-supreme-leader-of-iran-by-february-28__yes_hourly.csv"
if feb28_minute.exists():
    n = sum(1 for _ in open(feb28_minute)) - 1
    print(f"Feb 28 Polymarket minute (event window): {n:,} observations")
if feb28_hourly.exists():
    n = sum(1 for _ in open(feb28_hourly)) - 1
    print(f"Feb 28 Polymarket hourly (lifecycle): {n:,} observations")

print()
if mar01_trades.exists():
    df = pd.read_csv(mar01_trades)
    if "ts_utc" in df.columns:
        df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    elif "created_time" in df.columns:
        df["ts_utc"] = pd.to_datetime(df["created_time"], utc=True)
    plateau_start = pd.Timestamp("2026-02-28 17:11", tz="UTC")
    plateau_end = pd.Timestamp("2026-03-01 03:06", tz="UTC")
    plateau = df[(df["ts_utc"] >= plateau_start) & (df["ts_utc"] <= plateau_end)]
    print(f"Mar 01 Kalshi plateau-regime trades (17:11 -> 03:06): {len(plateau):,}")
    if "yes_price_dollars" in plateau.columns:
        print(f"  median price: {plateau['yes_price_dollars'].median()}")
