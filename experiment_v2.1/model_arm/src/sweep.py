"""
Sweep runner: orchestrates trials across (model x prompt_variant) combinations.

Architecture
------------
Each (model_id, prompt_variant) combination becomes one self-contained trial,
written into a subfolder of the sweep root. A trial that fails partway
through can be re-run by name without touching other trials. Aggregation
across the sweep is performed at the analysis stage by walking the sweep
folder.

Output layout:

    outputs/sweep_<YYYYMMDD_HHMMSS>_<sweep_id>_<n>/
        sweep_manifest.json
        <model_safe>__<variant>/         <- a regular trial folder
            manifest.json
            raw/...
            parsed/...
            figures/...
        <model_safe>__<variant>/
            ...

Why per-combo isolation rather than one mega-trial:
- Reproducibility: each manifest is self-contained. A reviewer can re-run
  one cell from its manifest without re-running the sweep.
- Failure containment: an OOM or parse-failure cascade in one cell does not
  contaminate others.
- Compute scheduling: cells can be run on different machines / sessions and
  combined later via the sweep folder.
- Existing `run_trial()` and `visualise.render_all()` work unchanged on each
  cell.

Usage
-----
    from src.sweep import run_sweep

    run_sweep(
        sweep_id="prompt_pilot",
        models=["Qwen/Qwen2.5-7B-Instruct"],
        prompt_variants=["v1_original", "v2_full_scale", "v3_strict", "v4_full_strict"],
        story_ids=["hospital_incident"],
        conditions=["linear"],
        seeds=[0, 1, 2, 3, 4],
        stimuli=stimuli,
        conversation_factory_for_model=my_factory,
    )
"""

from __future__ import annotations

import itertools
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from .runner import TrialSpec, run_trial, _fmt_duration
from .stimuli_loader import StimulusBundle
from .sweep_config import resolve_prompt_variants, resolve_tasks


def _sanitize_for_filesystem(s: str) -> str:
    """Make a model_id like 'Qwen/Qwen2.5-7B-Instruct' filesystem-safe."""
    return s.replace("/", "-").replace(" ", "_")


def _next_sweep_run_number(outputs_root: Path, sweep_id: str) -> int:
    """Next 1-based run index for this sweep_id (counts prior sweep_*_<id> folders)."""
    if not outputs_root.is_dir():
        return 1
    pat = re.compile(rf"^sweep_.+_{re.escape(sweep_id)}(?:_(\d+))?$")
    max_n = 0
    for p in outputs_root.iterdir():
        m = pat.match(p.name)
        if m:
            n = int(m.group(1)) if m.group(1) else 1
            max_n = max(max_n, n)
    return max_n + 1


def run_sweep(
    sweep_id: str,
    models: list[str],
    prompt_variants: list[str],
    story_ids: list[str],
    conditions: list[str],
    seeds: list[int],
    stimuli: StimulusBundle,
    conversation_factory_for_model: Callable[[str], Callable],
    outputs_root: Path | str = "outputs",
    temperature: float = 0.7,
    max_new_tokens: int = 80,
    skip_existing: bool = False,
    tasks: dict[str, bool] | None = None,
) -> Path:
    """Run sweep cells. Returns the sweep root path.

    When pair scaling is enabled, each cell is (model x prompt_variant). Otherwise
    each cell is one model only (prompt_variants ignored).

    Parameters
    ----------
    conversation_factory_for_model : callable
        Given a model_id, returns a `conversation_factory(story, seed)` callable
        suitable for `run_trial`. The factory is responsible for loading the
        model (typically once, then reused across stories/seeds within the cell).
    tasks : dict[str, bool], optional
        Per-task flags from ``resolve_tasks(config)``. Defaults to all tasks on.
    skip_existing : bool
        If True and a trial subfolder already exists for a (model, variant)
        cell, skip it. Useful for resuming partial sweeps.
    """
    if tasks is None:
        tasks = {name: True for name in ("comprehension", "ordering", "pair_scaling", "counterfactual")}

    sweep_stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_n = _next_sweep_run_number(Path(outputs_root), sweep_id)
    sweep_root = Path(outputs_root) / f"sweep_{sweep_stamp}_{sweep_id}_{run_n}"
    sweep_root.mkdir(parents=True, exist_ok=True)

    pair_scaling_on = tasks.get("pair_scaling", False)
    if pair_scaling_on:
        cells = [(m, v) for m, v in itertools.product(models, prompt_variants)]
    else:
        cells = [(m, None) for m in models]

    n_cells = len(cells)
    n_runs_per_cell = len(story_ids) * len(conditions) * len(seeds)
    enabled_tasks = [name for name, on in tasks.items() if on]

    print()
    print("=" * 70)
    print(f" SWEEP {sweep_id}")
    print(f" sweep dir:        {sweep_root}")
    print(f" models:           {len(models)} ({', '.join(models)})")
    if pair_scaling_on:
        print(f" prompt variants:  {len(prompt_variants)} ({', '.join(prompt_variants)})")
    else:
        print(" prompt variants:  (n/a — pair_scaling not in tasks)")
    print(f" tasks:            {', '.join(enabled_tasks)}")
    print(f" cells:            {n_cells}")
    print(f" runs per cell:    {n_runs_per_cell} (stories x conditions x seeds)")
    print(f" total runs:       {n_cells * n_runs_per_cell}")
    print("=" * 70)
    print()

    trial_dirs: list[Path] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []  # (cell_name, error)
    sweep_t0 = time.time()

    for idx, (model_id, variant) in enumerate(cells, 1):
        model_safe = _sanitize_for_filesystem(model_id)
        cell_run_id = f"{model_safe}__{variant}" if variant else model_safe

        cell_dir_pattern = list(sweep_root.glob(f"trial_*_{cell_run_id}"))
        if skip_existing and cell_dir_pattern:
            print(f"[{idx}/{n_cells}] SKIP (exists): {cell_run_id}")
            skipped.append(cell_run_id)
            trial_dirs.append(cell_dir_pattern[0])
            continue

        print(f"[{idx}/{n_cells}] {cell_run_id}")
        print("-" * 70)

        spec = TrialSpec(
            model_id=model_id,
            story_ids=story_ids,
            conditions=conditions,
            seeds=seeds,
            run_id=cell_run_id,
            outputs_root=sweep_root,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            pair_scaling_variant=variant or "v1_original",
            n_comprehension=tasks.get("comprehension", False),
            n_ordering=tasks.get("ordering", False),
            n_pair_scaling=tasks.get("pair_scaling", False),
            n_counterfactual=tasks.get("counterfactual", False),
        )

        try:
            conversation_factory = conversation_factory_for_model(model_id)
            trial_dir = run_trial(spec, stimuli, conversation_factory)
            trial_dirs.append(trial_dir)
        except Exception as e:
            logging.exception("Cell %s failed", cell_run_id)
            failed.append((cell_run_id, str(e)))
            print(f"  CELL FAILED: {e}")
            print()
            continue

        elapsed = time.time() - sweep_t0
        avg = elapsed / idx
        remaining = (n_cells - idx) * avg
        print(f"  cell complete. sweep elapsed {_fmt_duration(elapsed)}, "
              f"ETA {_fmt_duration(remaining)}")
        print()

    # Sweep manifest
    manifest = {
        "sweep_id": sweep_id,
        "sweep_dir": str(sweep_root),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "models": models,
        "prompt_variants": prompt_variants if pair_scaling_on else None,
        "tasks": tasks,
        "story_ids": story_ids,
        "conditions": conditions,
        "seeds": seeds,
        "temperature": temperature,
        "max_new_tokens": max_new_tokens,
        "n_cells": n_cells,
        "n_completed": len(trial_dirs) - len(skipped),
        "n_skipped": len(skipped),
        "n_failed": len(failed),
        "failed_cells": failed,
        "trial_dirs": [str(p) for p in trial_dirs],
        "elapsed_seconds": round(time.time() - sweep_t0, 1),
    }
    (sweep_root / "sweep_manifest.json").write_text(json.dumps(manifest, indent=2))

    # Footer
    print("=" * 70)
    print(f" SWEEP {sweep_id} complete in {_fmt_duration(time.time() - sweep_t0)}")
    print(f" cells completed: {len(trial_dirs) - len(skipped)} / {n_cells}")
    if skipped:
        print(f" cells skipped:   {len(skipped)}")
    if failed:
        print(f" cells FAILED:    {len(failed)}")
        for name, err in failed:
            print(f"    {name}: {err[:60]}")
    print(f" sweep dir: {sweep_root}")
    print("=" * 70)

    return sweep_root
