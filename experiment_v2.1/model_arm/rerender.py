#!/usr/bin/env python3
"""
Re-render all figures for an existing trial directory, without running the model.

Use this after editing visualise.py / meta_rsa.py / inferred_graph.py to regenerate
plots from the same raw data, or to apply new figure types to a previously-run trial.

Usage:
    python rerender.py                              # auto-pick latest trial under outputs/
    python rerender.py outputs/trial_20260505_...   # specific trial (has parsed/)
    python rerender.py outputs/sweep_*_my_run       # all trial_* cells under a sweep folder
    python rerender.py --root some_other_dir        # search a different outputs root
    python rerender.py --all                        # re-render every trial under root
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from src import stimuli_loader, visualise


def find_trials(root: Path) -> list[Path]:
    return sorted(p for p in root.glob("trial_*") if (p / "parsed").exists())


def resolve_trial_targets(path: Path) -> list[Path]:
    """Single trial dir (has parsed/) or a sweep folder containing trial_* subdirs."""
    if not path.exists():
        print(f"Not found: {path}", file=sys.stderr)
        sys.exit(1)
    if path.is_file():
        print(f"Expected a directory, got file: {path}", file=sys.stderr)
        sys.exit(1)
    if (path / "parsed").exists():
        return [path]
    nested = find_trials(path)
    if nested:
        return nested
    print(
        f"{path}: not a trial directory (no parsed/) and no trial_* subdirectories "
        f"with parsed/ — nothing to re-render.",
        file=sys.stderr,
    )
    sys.exit(1)


def _is_sweep_root(path: Path) -> bool:
    """Heuristic: contains at least one trial_* subdir but is not itself a trial."""
    if (path / "parsed").exists():
        return False
    return any(p.is_dir() and p.name.startswith("trial_") for p in path.iterdir())


def rerender_one(trial_dir: Path, stimuli) -> bool:
    if not (trial_dir / "parsed").exists():
        print(f"  ✗ {trial_dir}: no parsed/ subdirectory — skipping", file=sys.stderr)
        return False
    if not (trial_dir / "parsed" / "pair_scaling_matrices.json").exists():
        print(f"  ✗ {trial_dir}: missing pair_scaling_matrices.json — skipping", file=sys.stderr)
        return False

    t0 = time.time()
    print(f"  → {trial_dir} ", end="", flush=True)
    visualise.render_all(trial_dir, stimuli)
    print(f"✓ {time.time() - t0:.1f}s")
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("trial_dir", nargs="?", default=None,
                   help="Path to a specific trial directory. If omitted, picks the latest.")
    p.add_argument("--root", default="outputs",
                   help="Outputs root to search (default: outputs)")
    p.add_argument("--all", action="store_true",
                   help="Re-render every trial under --root, not just the latest.")
    args = p.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"Root not found: {root}", file=sys.stderr)
        sys.exit(1)

    print("Loading stimuli...")
    stimuli = stimuli_loader.load()

    if args.trial_dir:
        targets = resolve_trial_targets(Path(args.trial_dir))
        if len(targets) > 1:
            print(f"Re-rendering {len(targets)} trial(s) under {args.trial_dir}")
    elif args.all:
        targets = find_trials(root)
        if not targets:
            print(f"No trial_* directories found under {root}", file=sys.stderr)
            sys.exit(1)
        print(f"Re-rendering {len(targets)} trial(s) under {root}")
    else:
        all_trials = find_trials(root)
        if not all_trials:
            print(f"No trial_* directories found under {root}", file=sys.stderr)
            sys.exit(1)
        targets = [all_trials[-1]]
        print(f"Re-rendering latest: {targets[0]}")

    n_ok = sum(rerender_one(t, stimuli) for t in targets)
    print(f"\nDone. {n_ok}/{len(targets)} trial(s) re-rendered.")
    if n_ok > 0:
        print(f"Figures at:")
        for t in targets[:3]:
            if (t / "figures").exists():
                print(f"  {t / 'figures'}")
        if len(targets) > 3:
            print(f"  ... and {len(targets) - 3} more")

    # Sweep-level interactive meta map: pools cells across every trial in the
    # sweep root. Rendered when (a) the user pointed rerender at a sweep folder,
    # or (b) --all was used and targets share a single sweep parent.
    from src import interactive_graph

    sweep_roots: list[Path] = []
    if args.trial_dir:
        explicit = Path(args.trial_dir)
        if _is_sweep_root(explicit):
            sweep_roots.append(explicit)
    if not sweep_roots:
        # Collect any unique sweep parents from targets that look like sweep cells
        for t in targets:
            parent = t.parent
            if _is_sweep_root(parent) and parent not in sweep_roots:
                sweep_roots.append(parent)

    for sr in sweep_roots:
        n = interactive_graph.render_sweep_meta_map(sr, stimuli)
        if n:
            print(f"Sweep meta map: {sr / 'meta_map.html'}")


if __name__ == "__main__":
    main()