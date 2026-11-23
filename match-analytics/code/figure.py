"""Render ../figures/overview.png: on the left a stretch of a real match log translated to text, on the right my results going
first and going second, computed by analysis.py.

Usage:  python figure.py
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analysis  # noqa: E402
from read_log import DATA, translate  # noqa: E402

SURFACE, TEXT, TEXT2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
WINS, LOSSES = "#2a78d6", "#eb6834"   # validated categorical pair (blue, orange)
SAMPLE_MATCH = "2026-11-23_15-54-44.json"
LINES = (77, 89)   # Kuriboh - Multiply! summons Artmage Power Patron during my turn


def main():
    matches = [m for m in (analysis.analyse(f) for f in sorted(DATA.glob("*.json"))) if m and m["result"] in ("win", "loss")]
    groups = [("Going first", [m for m in matches if m["first"]]), ("Going second", [m for m in matches if m["first"] is False])]
    r = json.load(open(DATA / SAMPLE_MATCH, encoding="utf-8"))
    excerpt = translate(r).split("\n")[LINES[0] - 1:LINES[1]]

    fig = plt.figure(figsize=(6.5, 3.1), dpi=220, facecolor=SURFACE)
    ax1 = fig.add_axes([0.01, 0.02, 0.56, 0.96])
    ax1.axis("off")
    ax1.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax1.transAxes, facecolor="#f3f2ee", edgecolor=GRID, linewidth=0.8))
    ax1.text(0.03, 0.95, "Translated duel log (real match, turn 1)", transform=ax1.transAxes, fontsize=7.5, fontweight="bold",
             color=TEXT, va="top", family="DejaVu Sans")
    for k, line in enumerate(excerpt):
        quiet = line.strip().startswith(("ACTIVATES", "resolves", "("))
        ax1.text(0.03, 0.85 - k * 0.064, line.strip(), transform=ax1.transAxes, fontsize=4.7, color=TEXT2 if quiet else TEXT,
                 va="top", family="DejaVu Sans Mono")
    ax2 = fig.add_axes([0.66, 0.2, 0.31, 0.58], facecolor=SURFACE)
    for y, (name, ms) in enumerate(reversed(groups)):
        w = sum(m["result"] == "win" for m in ms)
        lo = sum(m["result"] == "loss" for m in ms)
        ax2.barh(y, w, height=0.42, color=WINS, edgecolor=SURFACE, linewidth=1.2)
        ax2.barh(y, lo, left=w, height=0.42, color=LOSSES, edgecolor=SURFACE, linewidth=1.2)
        ax2.text(w + lo + 0.15, y, "%d-%d" % (w, lo), va="center", fontsize=7, color=TEXT, family="DejaVu Sans")
    ax2.set_yticks(range(len(groups)))
    ax2.set_yticklabels([n for n, _ in reversed(groups)], fontsize=7, color=TEXT, family="DejaVu Sans")
    ax2.set_xlim(0, max(len(ms) for _, ms in groups) + 1.2)
    ax2.tick_params(axis="x", labelsize=6, colors=TEXT2, length=0)
    ax2.tick_params(axis="y", length=0)
    ax2.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax2.grid(axis="x", color=GRID, linewidth=0.6)
    ax2.set_axisbelow(True)
    for s in ax2.spines.values():
        s.set_visible(False)
    ax2.set_xlabel("matches", fontsize=6, color=TEXT2, family="DejaVu Sans")
    fig.text(0.66, 0.93, "Results by turn order", fontsize=7.5, fontweight="bold", color=TEXT, family="DejaVu Sans")
    fig.text(0.66, 0.86, "%d of my own matches, 23 Nov 2026" % len(matches), fontsize=6, color=TEXT2, family="DejaVu Sans")
    fig.patches.extend([plt.Rectangle((0.66, 0.065), 0.014, 0.03, transform=fig.transFigure, facecolor=WINS),
                        plt.Rectangle((0.80, 0.065), 0.014, 0.03, transform=fig.transFigure, facecolor=LOSSES)])
    fig.text(0.678, 0.068, "wins", fontsize=6, color=TEXT, family="DejaVu Sans")
    fig.text(0.818, 0.068, "losses", fontsize=6, color=TEXT, family="DejaVu Sans")
    target = DATA.parent / "figures" / "overview.png"
    target.parent.mkdir(exist_ok=True)
    fig.savefig(target, facecolor=SURFACE)
    print("figure:", target)


if __name__ == "__main__":
    main()
