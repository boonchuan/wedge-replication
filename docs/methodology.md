# Methodology notes

Practical notes on data pulling, schema parsing, and analysis decisions. Useful
for replicators who want to extend the analysis or apply the same framework to
other dual-listed prediction-market contracts.

## Polymarket data

### Endpoints used

- `https://gamma-api.polymarket.com/markets` — market metadata (slug, conditionId,
  CLOB token IDs, market description, dates, volume, status). Requires
  `closed=true&archived=true` for resolved markets.
- `https://clob.polymarket.com/prices-history` — historical price data. Requires
  `market` (CLOB token ID), `startTs` and `endTs` Unix timestamps, and `fidelity`
  in minutes.

### Pagination quirk

The `prices-history` endpoint silently returns empty arrays for closed markets
queried with `interval=...` parameters. Use explicit `startTs` / `endTs` instead.
For minute-fidelity data, paginate in 7-day chunks to stay under server limits.

### Trades cap

The Data API trades endpoint (`https://data-api.polymarket.com/trades`) caps at
offset 3,500 per market. For full trade history (~50k+ on heavily traded
markets), use the Polygon subgraph instead. The paper's analysis does not
require trades beyond the cap.

## Kalshi data

### Endpoints used

- `https://api.elections.kalshi.com/trade-api/v2/series/<series>/markets` — market
  metadata. Requires `with_nested_markets=true` to expand the series into its
  individual markets.
- `https://api.elections.kalshi.com/trade-api/v2/markets/<ticker>/candlesticks`
  — minute-resolution OHLC + bid/ask + volume + open interest.
- `https://api.elections.kalshi.com/trade-api/v2/markets/trades?ticker=<ticker>`
  — individual trade prints.

### Candlestick schema (the nested-dict gotcha)

Each candlestick row's `yes_bid`, `yes_ask`, and `price` cells are returned as
dictionaries, not floats:

```python
yes_bid: {'price': 9, 'close_dollars': 0.09, 'mean_dollars': 0.09, ...}
yes_ask: {'price': 10, 'close_dollars': 0.10, 'mean_dollars': 0.10, ...}
```

When the candlestick CSVs are reloaded with `pd.read_csv`, these cells come back
as Python-literal *strings*. Extraction:

```python
import ast
def parse_close(s):
    if pd.isna(s) or s == "{}":
        return None
    d = ast.literal_eval(s) if isinstance(s, str) else s
    v = d.get("close_dollars") if isinstance(d, dict) else None
    return float(v) if v is not None else None

df["bid"] = df["yes_bid"].apply(parse_close)
df["ask"] = df["yes_ask"].apply(parse_close)
df["mid"] = (df["bid"] + df["ask"]) / 2
df["spread"] = df["ask"] - df["bid"]
```

### Trades schema

```
count_fp, created_time, no_price_dollars, taker_side, ticker, trade_id,
yes_price_dollars, ts_utc
```

Prices are already in dollars (no /100 conversion). `taker_side` is `"yes"` or
`"no"` indicating which side lifted the book — directly identifies the
aggressor for signed-volume reconstruction without recourse to the Lee-Ready
quote test.

## Regime definitions for the Feb 28 event window

The four regimes used in §5 of the paper, all UTC:

| Regime | Start | End | Identifier |
|---|---|---|---|
| Pre-news | Feb 27 18:00 | Feb 28 06:14 | Polymarket flat at 0.013 |
| News arrival | Feb 28 06:15 | Feb 28 13:00 | Polymarket reacts; news ambiguous |
| Path resolution | Feb 28 13:00 | Feb 28 17:10 | Netanyahu/IDF reports; wedge widens |
| Plateau | Feb 28 17:10 | Mar 1 03:06 | Kalshi locks at 0.08; wedge ≈ 0.89 |

The 17:10 transition is identified from Kalshi's signed-volume series (a
~150,000-contract net sell sweep concentrated in five minutes). See
§5.3 of the paper.

## Time-zone handling

All timestamps in the analysis are UTC. Iran Standard Time (IRST) is UTC+3:30
year-round (Iran abolished daylight saving in 2022). The 9:30 AM IRST strike
timestamp converts cleanly to 06:00 UTC.

## Reproducibility notes

- Random number generators are not used anywhere; results are deterministic.
- Plot rendering depends on matplotlib backend; PNGs in `figures/` were
  generated with `matplotlib.use("Agg")` for headless rendering.
- `pandas` floor/resample behavior on tz-aware indices changed between 2.0 and
  2.2; pinning `pandas>=2.0` is sufficient.
