# Replication package — *Kalshi's Ceiling*

Replication code and data for:

> Lim, Boon Chuan (2026). "Kalshi's Ceiling: Settlement Asymmetry and the Intraday Limits of Cross-Venue Repricing in Event Contracts."
> SSRN Working Paper. Available at: [SSRN URL once posted]

## What this repo contains

```
.
├── README.md                   <- this file
├── LICENSE                     <- MIT
├── CITATION.cff                <- citation metadata for GitHub auto-cite
├── requirements.txt            <- Python dependencies
├── scripts/
│   ├── 01_pull_polymarket_khamenei.py
│   ├── 02_pull_kalshi_khamenei.py
│   ├── 03_build_wedge.py
│   ├── 04_horizon_comparison.py
│   ├── 11_anomaly_1600.py
│   ├── 12_spread_analysis.py
│   └── 13_implied_pi.py
├── data/
│   ├── polymarket/             <- pulled CSVs (created by 01_*.py)
│   └── kalshi/                 <- pulled CSVs (created by 02_*.py)
├── figures/                    <- generated PNG outputs
└── docs/
    ├── methodology.md          <- API quirks, schema notes, regime definitions
    └── changelog.md            <- version history
```

## Reproducing the paper end-to-end

### 1. Environment

```bash
git clone https://github.com/<your-handle>/wedge-replication.git
cd wedge-replication
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Tested on Python 3.11+ on Ubuntu 24.04 LTS and Windows 11. No authentication or
API keys required — both Polymarket Gamma/CLOB and Kalshi trade-api v2 are
public read endpoints.

### 2. Pull data

```bash
python scripts/01_pull_polymarket_khamenei.py
python scripts/02_pull_kalshi_khamenei.py
```

Each script pulls all four-or-three contracts in its venue, writes one CSV per
contract to `data/polymarket/` or `data/kalshi/`. Total disk: ~50 MB. Wall
clock: ~3 minutes for Polymarket, ~5 minutes for Kalshi.

### 3. Build figures

```bash
python scripts/03_build_wedge.py            # Figure 1
python scripts/04_horizon_comparison.py     # Figure 4
python scripts/11_anomaly_1600.py           # Figure 2
python scripts/12_spread_analysis.py        # Figure 3
python scripts/13_implied_pi.py             # Figure 5
```

PNGs land in `figures/`. Summary CSVs land alongside each figure
(e.g. `figures/horizon_summary.csv`). Each script is independent — you can run
them in any order after step 2.

## Reproducing without re-pulling data

The CSVs in `data/` are the snapshot used in the paper. If the upstream APIs
change schemas or rate-limit, the existing CSVs let downstream analysis still run.
Skip step 2 if `data/polymarket/*.csv` and `data/kalshi/*.csv` already exist.

## Caveats and known issues

- **Polymarket Data API trade pagination caps at offset 3,500.** Trade-level
  analysis on the Polymarket side hits this cap on the headline contract. The
  paper's empirical content does not depend on the trades beyond this cap; minute
  midprices are complete. The full ~50,000+ trade history would require the
  Polygon subgraph (left for future work).
- **Kalshi candle bid/ask cells are nested dicts.** The `yes_bid` and `yes_ask`
  fields in the Kalshi candlesticks endpoint return strings like
  `"{'price': 9, 'close_dollars': 0.09}"`. Extraction requires
  `ast.literal_eval` — see `docs/methodology.md`.
- **News timestamps are wire-service approximate.** The 06:15 UTC news-arrival
  marker is identified from Polymarket's price reaction, not from any wire
  timestamp. The 17:10 UTC informed-anticipation sweep on Kalshi is identified
  from order-flow data. Both are robust to ±5 minutes (Appendix B of the paper).

## Citation

If you use this code or data, please cite:

```bibtex
@article{lim2026kalshi,
  title  = {Kalshi's Ceiling: Settlement Asymmetry and the Intraday Limits
            of Cross-Venue Repricing in Event Contracts},
  author = {Lim, Boon Chuan},
  year   = {2026},
  note   = {SSRN Working Paper},
  url    = {https://ssrn.com/abstract=XXXXXXX}
}
```

GitHub provides automatic citation export via `CITATION.cff` — click "Cite this
repository" on the repo home page.

## License

Code: MIT (see `LICENSE`). Data files in `data/` are pulled from public APIs and
remain subject to those APIs' terms of use (Polymarket and Kalshi). No
proprietary content is redistributed.

## Contact

Lim Boon Chuan, Independent researcher, Singapore
boonchuan@singapore.to · SSRN Author ID 11094408
