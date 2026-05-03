#!/usr/bin/env python3
"""
Session 1.3 (revised) — Implied-π analysis.

The full implied-hazard recovery requires knowing π(T) for each horizon, which
is not observable for the longer horizons (because pre-strike Kalshi prices
on Apr 01 / Sep 01 reflect both legitimate non-death exit probability AND any
residual death-by-other-means risk). Instead, this script reverses the question:

For each matched pair, given the observed plateau wedge W and Polymarket price p,
what value of π would the model require to exactly match W?

  W = p * q * (1 - π)
  =>  for q ∈ [0.7, 0.95] (a plausible range given the strike context),
      what π is required?

This is a clean diagnostic. If the implied π for the Mar 01 contract matches
the *observed* pre-strike Kalshi LTP (~0.015), the model is point-identified
on the headline pair. For the longer horizons, the implied π will be higher,
reflecting their broader ex-ante non-death probability mass.

Inputs: figures/horizon_summary.csv (or hard-coded plateau values from §6.2).
Outputs:
  figures/implied_pi.png
  figures/implied_pi_table.csv

Run on OrangeVPS:
  python3 13_implied_pi.py
"""

from __future__ import annotations
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path("figures")

# Plateau values from §6.2 of v0.1 paper
PAIRS = [
    {"label": "Mar 01 (1-day)",   "p": 0.97, "W": 0.89, "observed_pi": 0.015},
    {"label": "Apr 01 (31-day)",  "p": 0.98, "W": 0.57, "observed_pi": None},
    {"label": "Sep 01 (184-day)", "p": 0.99, "W": 0.40, "observed_pi": None},
]


def implied_pi(p, W, q):
    # W = p * q * (1 - pi)  =>  pi = 1 - W/(p*q)
    return 1 - W / (p * q)


def main():
    q_grid = np.linspace(0.50, 1.00, 51)

    # Build a table of implied pi at central q values
    rows = []
    for pair in PAIRS:
        for q in [0.70, 0.80, 0.90, 0.93, 0.95]:
            pi = implied_pi(pair["p"], pair["W"], q)
            rows.append({
                "pair": pair["label"],
                "q_assumed": q,
                "p": pair["p"],
                "W_observed": pair["W"],
                "pi_implied": round(pi, 4),
                "pi_observed": pair["observed_pi"],
                "match": "Y" if pair["observed_pi"] is not None and abs(pi - pair["observed_pi"]) < 0.05 else "",
            })
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "implied_pi_table.csv", index=False)
    print("=== Implied π table ===")
    print(df.to_string(index=False))

    # Plot: implied π as function of assumed q, one line per pair
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]
    for pair, color in zip(PAIRS, colors):
        pi_grid = [implied_pi(pair["p"], pair["W"], q) for q in q_grid]
        ax.plot(q_grid, pi_grid, label=pair["label"], color=color, linewidth=2)
        if pair["observed_pi"] is not None:
            ax.axhline(pair["observed_pi"], linestyle=":", color=color, alpha=0.6,
                       label=f"   observed pre-strike π = {pair['observed_pi']:.3f}")

    ax.set_xlabel(r"Assumed conditional disqualifying-path probability  $q$")
    ax.set_ylabel(r"Implied recovery rate  $\pi = 1 - W/(p q)$")
    ax.set_title("Implied recovery rate by horizon, as a function of assumed $q$\n"
                 r"$W = p \cdot q \cdot (1-\pi)$")
    ax.set_xlim(0.5, 1.0)
    ax.set_ylim(-0.1, 1.0)
    ax.axhline(0, linestyle="-", color="grey", linewidth=0.4)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", fontsize=9)

    # Annotation for the key result
    pi_mar = implied_pi(0.97, 0.89, 0.93)
    ax.annotate(f"Mar 01 plateau:\n  q=0.93 ⇒ π={pi_mar:.3f}\n  matches observed π=0.015",
                xy=(0.93, pi_mar), xytext=(0.55, 0.4),
                fontsize=10, arrowprops=dict(arrowstyle="->", alpha=0.6))

    fig.tight_layout()
    fig.savefig(OUT / "implied_pi.png", dpi=160, bbox_inches="tight")
    print(f"\nSaved figure: {OUT / 'implied_pi.png'}")


if __name__ == "__main__":
    main()
