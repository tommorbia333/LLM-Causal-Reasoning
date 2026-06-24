#!/usr/bin/env python3
"""
For each PNG under trial_*/figures/diagnostics/, build one multi-panel figure
across all trials in a sweep (same layout/titles as compare_headlines.py).

Writes into <sweep>/compare_diagnostics/<filename>.png

Usage:
    python compare_diagnostics.py outputs/sweep_20260507_190915_prompt_pilot
    python compare_diagnostics.py outputs/sweep_... --output-dir path/to/dir
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
    trials = []
    for p in sweep_dir.glob("trial_*"):
        if not p.is_dir():
            continue
        diag = p / "figures" / "diagnostics"
        if diag.is_dir() and any(diag.glob("*.png")):
            trials.append(p)
    return sorted(trials, key=lambda p: _variant_and_model(p)[0].lower())


def _grid_dims(n: int) -> tuple[int, int]:
    cols = min(2, n) if n <= 4 else math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    return rows, cols


def _all_diagnostic_basenames(trials: list[Path]) -> list[str]:
    names: set[str] = set()
    for t in trials:
        diag = t / "figures" / "diagnostics"
        if diag.is_dir():
            names.update(p.name for p in diag.glob("*.png"))
    return sorted(names)


def _montage_one(
    trials: list[Path],
    basename: str,
    sweep_name: str,
    out_path: Path,
) -> None:
    rows, cols = _grid_dims(len(trials))
    fig_w = 7.0 * cols
    fig_h = 5.2 * rows + 1.2
    fig, axes = plt.subplots(rows, cols, figsize=(fig_w, fig_h), squeeze=False)

    for ax in axes.flat:
        ax.axis("off")

    for i, trial_dir in enumerate(trials):
        r, c = divmod(i, cols)
        ax = axes[r][c]
        img_path = trial_dir / "figures" / "diagnostics" / basename
        variant, short_model = _variant_and_model(trial_dir)
        title = variant if not short_model else f"{variant}\n{short_model}"
        ax.set_title(title, fontsize=11, fontweight="semibold", color="#111827")

        if img_path.is_file():
            ax.imshow(mpimg.imread(img_path))
        else:
            ax.set_facecolor("#f3f4f6")
            ax.text(
                0.5,
                0.5,
                "missing",
                ha="center",
                va="center",
                fontsize=14,
                color="#6b7280",
                transform=ax.transAxes,
            )

    fig.suptitle(
        f"{sweep_name}\n{basename}",
        fontsize=13,
        fontweight="bold",
        color="#0f172a",
        y=1.02,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "sweep_dir",
        type=Path,
        help="Sweep directory containing trial_* subfolders",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Folder for montages (default: <sweep>/compare_diagnostics)",
    )
    args = ap.parse_args()

    sweep = args.sweep_dir.resolve()
    if not sweep.is_dir():
        print(f"Not a directory: {sweep}", file=sys.stderr)
        sys.exit(1)

    trials = _collect_trials(sweep)
    if not trials:
        print(
            f"No trial_* with figures/diagnostics/*.png under {sweep}",
            file=sys.stderr,
        )
        sys.exit(1)

    names = _all_diagnostic_basenames(trials)
    if not names:
        print(f"No diagnostic PNGs found under trials in {sweep}", file=sys.stderr)
        sys.exit(1)

    out_root = args.output_dir or (sweep / "compare_diagnostics")
    out_root = out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    sweep_label = sweep.name
    for name in names:
        _montage_one(trials, name, sweep_label, out_root / name)

    print(f"Wrote {len(names)} montage(s) to {out_root}")


if __name__ == "__main__":
    main()
