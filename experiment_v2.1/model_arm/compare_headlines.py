#!/usr/bin/env python3
"""
Lay out headline.png from every trial_* under a sweep folder in one figure.

Reads manifest.json per trial for titles (pair_scaling_variant + model id).

Usage:
    python compare_headlines.py outputs/sweep_20260507_190915_prompt_pilot
    python compare_headlines.py outputs/sweep_... -o my_comparison.png
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt


def _variant_and_model(trial_dir: Path) -> tuple[str, str]:
    manifest = trial_dir / "manifest.json"
    variant: str | None = None
    model_id = ""
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        variant = data.get("pair_scaling_variant")
        model_id = data.get("model_id") or ""
    if not variant:
        parts = trial_dir.name.split("__")
        variant = parts[-1] if len(parts) >= 2 else trial_dir.name
    short_model = model_id.split("/")[-1] if model_id else ""
    return variant, short_model


def _collect_trials(sweep_dir: Path) -> list[Path]:
    trials = sorted(
        p
        for p in sweep_dir.glob("trial_*")
        if p.is_dir() and (p / "figures" / "headline.png").is_file()
    )
    return sorted(trials, key=lambda p: _variant_and_model(p)[0].lower())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "sweep_dir",
        type=Path,
        help="Sweep directory containing trial_* subfolders",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output PNG path (default: <sweep>/compare_headlines.png)",
    )
    args = ap.parse_args()

    sweep = args.sweep_dir.resolve()
    if not sweep.is_dir():
        print(f"Not a directory: {sweep}", file=sys.stderr)
        sys.exit(1)

    trials = _collect_trials(sweep)
    if not trials:
        print(
            f"No trial_* with figures/headline.png under {sweep}",
            file=sys.stderr,
        )
        sys.exit(1)

    out = args.output or (sweep / "compare_headlines.png")
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    n = len(trials)
    cols = min(2, n) if n <= 4 else math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)

    fig_w = 7.0 * cols
    fig_h = 5.2 * rows + 1.2
    fig, axes = plt.subplots(rows, cols, figsize=(fig_w, fig_h), squeeze=False)

    for ax in axes.flat:
        ax.axis("off")

    for i, trial_dir in enumerate(trials):
        r, c = divmod(i, cols)
        ax = axes[r][c]
        img_path = trial_dir / "figures" / "headline.png"
        img = mpimg.imread(img_path)
        ax.imshow(img)
        variant, short_model = _variant_and_model(trial_dir)
        title = variant if not short_model else f"{variant}\n{short_model}"
        ax.set_title(title, fontsize=11, fontweight="semibold", color="#111827")

    sweep_label = sweep.name
    fig.suptitle(
        f"{sweep_label}\n(pair_scaling_variant · model)",
        fontsize=13,
        fontweight="bold",
        color="#0f172a",
        y=1.02,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    print(f"Wrote {out} ({n} panel(s))")


if __name__ == "__main__":
    main()
