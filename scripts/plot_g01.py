#!/usr/bin/env python3
"""Rebuild the G0-1 scientific overview from the published exact grid.

Usage: python scripts/plot_g01.py
Requires matplotlib (plotting only; not required by the exact experiment).
All plotted values come from grid.csv.  No confidence intervals are displayed:
these are exhaustive finite-model expectations, not learned-model estimates.
"""
import argparse
import csv
from fractions import Fraction
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle


ROOT = Path(__file__).resolve().parents[1]


def q(value):
    return Fraction(str(value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "results" / "g01")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output stem without extension; defaults to RESULTS/overview")
    args = parser.parse_args()
    out = args.out or args.results / "overview"
    with (args.results / "grid.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    summary = json.loads((args.results / "summary.json").read_text(encoding="utf-8"))
    chosen = summary["selected_cell"]
    if chosen is None:
        raise ValueError("No selected operating cell; this overview requires one")
    keys = ("branch", "byte_cost", "inspect_cost", "extra_update_fee", "jobs_per_phase")
    selected = [r for r in rows if r["branch"] == chosen["branch"] and
                all(q(r[k]) == q(chosen[k]) for k in keys[1:])]
    if len(selected) != 1:
        raise ValueError("Selected cell does not identify exactly one grid row")
    selected = selected[0]
    cells = [r for r in rows if r["branch"] == "C" and
             q(r["extra_update_fee"]) == 1 and q(r["jobs_per_phase"]) == 100]
    inspect = sorted({q(r["inspect_cost"]) for r in cells})
    price = sorted({q(r["byte_cost"]) for r in cells})
    table = {(q(r["inspect_cost"]), q(r["byte_cost"])): r for r in cells}
    if len(table) != len(inspect) * len(price):
        raise ValueError("Incomplete heatmap slice")
    gain = [[float(q(table[i, b]["forced_gain_min"])) for b in price] for i in inspect]

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "svg.fonttype": "none",
        "svg.hashsalt": "etal-g01-overview-v1",
        "savefig.facecolor": "white",
    })
    fig, axes = plt.subplots(1, 2, figsize=(13.6, 6.6),
                             gridspec_kw={"width_ratios": [1.0, 1.18]})
    fig.subplots_adjust(left=.065, right=.965, bottom=.29, top=.78, wspace=.58)
    fig.suptitle("G0-1: When does codec migration pay?", x=.065, y=.965,
                 ha="left", fontsize=19, fontweight="bold")
    fig.text(.065, .902,
             "Exact finite-state oracle  |  Modeled normalized utility  |  No learning or speed claim",
             ha="left", color="#425466", fontsize=11.5)

    ax = axes[0]
    im = ax.imshow(gain, cmap="BrBG", norm=TwoSlopeNorm(vmin=-.10, vcenter=0, vmax=.10),
                   aspect="auto")
    ax.set_title("A  Forced migration: target-phase gain", loc="left", pad=14,
                 fontweight="bold")
    ax.set_xticks(range(len(price)), [f"{float(x):.2f}" for x in price])
    ax.set_yticks(range(len(inspect)), [f"{float(x):.2f}" for x in inspect])
    ax.set_xlabel("Modeled cost per transmitted byte", labelpad=10)
    ax.set_ylabel("Modeled inspection cost", labelpad=10)
    for y, i in enumerate(inspect):
        for x, b in enumerate(price):
            cell = table[i, b]
            lower, upper = q(cell["forced_gain_min"]), q(cell["forced_gain_max"])
            label = (f"{float(lower):+.4f}" if lower == upper else
                     f"[{float(lower):+.4f}, {float(upper):+.4f}]")
            ax.text(x, y, label, ha="center", va="center", fontsize=12,
                    color="white" if abs(float(lower)) >= .065 else "#172b4d",
                    fontweight="bold")
    sy = inspect.index(q(selected["inspect_cost"]))
    sx = price.index(q(selected["byte_cost"]))
    ax.add_patch(Rectangle((sx - .49, sy - .49), .98, .98, fill=False,
                           edgecolor="#111827", linewidth=2.5, zorder=10))
    ax.set_xticks([x - .5 for x in range(1, len(price))], minor=True)
    ax.set_yticks([y - .5 for y in range(1, len(inspect))], minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", bottom=False, left=False)
    cb = fig.colorbar(im, ax=ax, fraction=.047, pad=.035, ticks=[-.10, 0, .10])

    ax = axes[1]
    labels = ["Retained codec", "Best static codec", "No communication",
              "Sufficient fixed codec", "Adaptive oracle"]
    fields = ["retained_lifecycle_min", "best_static_lifecycle",
              "no_communication_lifecycle", "sufficient_lifecycle",
              "optional_lifecycle_min"]
    values = [float(q(selected[field])) for field in fields]
    colors = ["#9aa5b1", "#9aa5b1", "#6ba3bd", "#246c89", "#d97924"]
    bars = ax.barh(range(5), values, height=.57, color=colors)
    ax.set_yticks(range(5), labels)
    ax.invert_yaxis()
    ax.set_xlim(0, .92)
    ax.set_xticks([0, .2, .4, .6, .8])
    ax.set_xlabel("Mean utility per job across both phases", labelpad=10)
    ax.set_title("B  Selected cell: full lifecycle", loc="left", pad=14,
                 fontweight="bold")
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, color="#e5e9ee", linewidth=.8)
    for bar, value in zip(bars, values):
        ax.text(value + .012, bar.get_y() + bar.get_height()/2,
                f"{value:.4f}", va="center", ha="left", fontsize=11,
                fontweight="bold")
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(axis="y", length=0)

    advantage = float(q(selected["lifecycle_advantage_min"]))
    fig.text(.565, .155, f"Adaptive oracle minus best fixed control: {advantage:+.4f}",
             fontsize=11.5, fontweight="bold", color="#243b53")
    fig.text(.065, .155, "Outlined cell: prospective selection rule.", fontsize=10.5,
             color="#425466")
    fig.text(.065, .104,
             "C branch; 100 source + 100 target jobs. Extra migration fee: 1. "
             "Framing, inspection and codebook transfer costs are included.", fontsize=10.3,
             color="#425466")
    fig.text(.065, .064,
             "Panel A: worst source-optimal tie; all ties coincide in this slice. "
             "Panel B: byte cost 0.05, inspection cost 0.10. Exact expectations; no confidence intervals.",
             fontsize=9.7, color="#425466")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".svg"),
                metadata={"Date": None, "Creator": "ETAL scripts/plot_g01.py"})
    fig.savefig(out.with_suffix(".png"), dpi=180,
                metadata={"Software": "ETAL scripts/plot_g01.py"})
    plt.close(fig)
    print(f"Wrote {out.with_suffix('.svg')} and {out.with_suffix('.png')}")


if __name__ == "__main__":
    main()
