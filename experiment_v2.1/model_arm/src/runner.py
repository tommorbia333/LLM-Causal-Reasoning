"""
Trial runner: iterates (story × condition × seed), executes the task battery
on each, and writes structured outputs to a timestamped trial folder.

Output layout per trial:
    outputs/trial_<YYYYMMDD_HHMMSS>_<run_id>/
        manifest.json          (includes temperature, max_new_tokens for reproducibility)
        raw/<story_id>__<condition>__seed<seed>.jsonl   (one row per call)
        parsed/
            comprehension.json   (all stories)
            ordering.json
            pair_scaling_matrices.json
        figures/                 (populated by visualise.py)
        logs/run.log
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from . import prompts
from . import tasks
from . import pair_scaling_metrics
from .stimuli_loader import StimulusBundle, Story


def _json_float_or_none(x):
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


# -----------------------------------------------------------------------------
# Trial spec
# -----------------------------------------------------------------------------

class TrialSpec:
    def __init__(self, model_id: str, story_ids: list[str], conditions: list[str],
                 seeds: list[int], n_comprehension: bool = True, n_ordering: bool = True,
                 n_pair_scaling: bool = True, n_counterfactual: bool = True,
                 run_id: str = "pilot", outputs_root: Path | str = "outputs",
                 temperature: float = 0.7, max_new_tokens: int = 80,
                 pair_scaling_variant: str = "v1_original"):
        self.model_id = model_id
        self.story_ids = story_ids
        self.conditions = conditions
        self.seeds = seeds
        self.do_comprehension = n_comprehension
        self.do_ordering = n_ordering
        self.do_pair_scaling = n_pair_scaling
        self.do_counterfactual = n_counterfactual
        self.run_id = run_id
        self.outputs_root = Path(outputs_root)
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens
        self.pair_scaling_variant = pair_scaling_variant


# -----------------------------------------------------------------------------
# Main loop
# -----------------------------------------------------------------------------

def run_trial(spec: TrialSpec, stimuli: StimulusBundle, conversation_factory) -> Path:
    """
    Execute the trial. `conversation_factory(story, seed)` must return a fresh
    Conversation object with the system prompt + story already seeded.
    Returns the path to the trial folder.
    """
    trial_dir = _make_trial_dir(spec.outputs_root, spec.run_id)
    _setup_logging(trial_dir)
    log = logging.getLogger("trial")

    log.info(
        "Trial spec: model=%s stories=%s conditions=%s seeds=%s "
        "temperature=%s max_new_tokens=%s",
        spec.model_id,
        spec.story_ids,
        spec.conditions,
        spec.seeds,
        spec.temperature,
        spec.max_new_tokens,
    )

    raw_dir = trial_dir / "raw"
    parsed_dir = trial_dir / "parsed"
    raw_dir.mkdir(); parsed_dir.mkdir()

    all_results: list[tasks.StoryRunResult] = []
    n_total = len(spec.story_ids) * len(spec.conditions) * len(spec.seeds)
    counter = 0
    t0_trial = time.time()

    _print_trial_header(spec, trial_dir, n_total)

    for sid in spec.story_ids:
        for cond in spec.conditions:
            for seed in spec.seeds:
                counter += 1
                story = stimuli.get_story(sid, cond)

                # ---- story-run header (with trial-level ETA from run 2 onward) ----
                eta_str = ""
                if counter > 1:
                    elapsed_so_far = time.time() - t0_trial
                    avg = elapsed_so_far / (counter - 1)
                    remaining = (n_total - (counter - 1)) * avg
                    eta_str = f"   [elapsed {_fmt_duration(elapsed_so_far)}, ETA {_fmt_duration(remaining)}]"
                print(f"[{counter:2d}/{n_total}] {sid} | {cond:9s} | seed={seed}{eta_str}")
                log.info("[%d/%d] %s | %s | seed=%d", counter, n_total, sid, cond, seed)

                # ---- prime the conversation with the story ----
                t0_run = time.time()
                conv = conversation_factory(story, seed)
                t0_read = time.time()
                print(f"  {'reading story':14s} ", end="", flush=True)
                conv.seed_with_story(prompts.SYSTEM_PROMPT, prompts.reading_prompt(story))
                print(f"✓ {time.time() - t0_read:.1f}s")

                result = tasks.StoryRunResult(story_id=sid, condition=cond, seed=seed)

                if spec.do_comprehension:
                    items = stimuli.get_comprehension_items(sid)
                    result.comprehension = tasks.run_comprehension(conv, items)
                if spec.do_ordering:
                    result.ordering = tasks.run_ordering(conv, story, seed)
                if spec.do_pair_scaling:
                    result.pair_scaling = tasks.run_pair_scaling(conv, story, seed, variant=spec.pair_scaling_variant)
                if spec.do_counterfactual:
                    probes = stimuli.get_cf_probes(sid)
                    if probes:
                        result.counterfactual = tasks.run_counterfactual(conv, probes, seed)

                # ---- story-run footer ----
                elapsed_run = time.time() - t0_run
                run_calls = (
                    list(result.comprehension)
                    + ([result.ordering] if result.ordering else [])
                    + list(result.pair_scaling)
                    + list(result.counterfactual)
                )
                n_calls = len(run_calls)
                n_fails = sum(1 for c in run_calls if c.parsed is None)
                fail_str = "" if n_fails == 0 else f", \033[33mfails: {n_fails}\033[0m"
                print(f"  done in {_fmt_duration(elapsed_run)}  (calls: {n_calls}{fail_str})")
                print()

                _save_raw(raw_dir, result)
                all_results.append(result)

    elapsed = time.time() - t0_trial
    log.info("Trial complete. %d story-runs in %.1fs", n_total, elapsed)

    # Aggregate parsed outputs across all story-runs
    _save_parsed(parsed_dir, all_results, stimuli)

    # Manifest
    manifest = {
        "trial_dir": str(trial_dir),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "model_id": spec.model_id,
        "story_ids": spec.story_ids,
        "conditions": spec.conditions,
        "seeds": spec.seeds,
        "temperature": spec.temperature,
        "max_new_tokens": spec.max_new_tokens,
        "pair_scaling_variant": spec.pair_scaling_variant,
        "n_story_runs": n_total,
        "elapsed_seconds": round(elapsed, 1),
        "tasks_run": {
            "comprehension": spec.do_comprehension,
            "ordering": spec.do_ordering,
            "pair_scaling": spec.do_pair_scaling,
            "counterfactual": spec.do_counterfactual,
        },
    }
    (trial_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Final terminal summary
    total_calls = sum(
        len(r.comprehension) + (1 if r.ordering else 0)
        + len(r.pair_scaling) + len(r.counterfactual)
        for r in all_results
    )
    total_fails = sum(
        sum(1 for c in (
            list(r.comprehension)
            + ([r.ordering] if r.ordering else [])
            + list(r.pair_scaling)
            + list(r.counterfactual)
        ) if c.parsed is None)
        for r in all_results
    )
    _print_trial_footer(trial_dir, elapsed, n_total, total_calls, total_fails)

    try:
        from . import visualise

        print("Rendering figures ...")
        visualise.render_all(trial_dir, stimuli)
        print(f"Figures: {trial_dir / 'figures'}")
    except Exception as e:
        log.exception("Figure rendering failed")
        print(f"\nWARNING: figure rendering failed ({e}). Parsed data is saved; retry with:\n"
              f"  python rerender.py {trial_dir}\n")

    return trial_dir


# -----------------------------------------------------------------------------
# I/O helpers
# -----------------------------------------------------------------------------

def _make_trial_dir(root: Path, run_id: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    trial_dir = root / f"trial_{stamp}_{run_id}"
    trial_dir.mkdir()
    (trial_dir / "logs").mkdir()
    (trial_dir / "figures").mkdir()
    return trial_dir


def _setup_logging(trial_dir: Path):
    """File-only logging. Terminal output is handled separately via print() / tqdm."""
    log_path = trial_dir / "logs" / "run.log"
    handler = logging.FileHandler(log_path)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [handler]


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{int(m)}m {int(s):02d}s"
    h, rem = divmod(seconds, 3600)
    m, _ = divmod(rem, 60)
    return f"{int(h)}h {int(m):02d}m"


def _print_trial_header(spec: "TrialSpec", trial_dir: Path, n_total: int):
    bar = "=" * 70
    print()
    print(bar)
    print(f" model_arm {spec.run_id} trial")
    print(f" model:       {spec.model_id}")
    print(f" stories:     {', '.join(spec.story_ids)}")
    print(f" conditions:  {', '.join(spec.conditions)}")
    print(f" seeds:       {spec.seeds}")
    print(f" temperature: {spec.temperature}")
    print(f" prompt:      {spec.pair_scaling_variant}")
    print(f" max_tokens:  {spec.max_new_tokens}")
    enabled = [
        name for name, on in [
            ("comprehension", spec.do_comprehension),
            ("ordering", spec.do_ordering),
            ("pair_scaling", spec.do_pair_scaling),
            ("counterfactual", spec.do_counterfactual),
        ] if on
    ]
    print(f" tasks:       {', '.join(enabled)}")
    print(f" total runs:  {n_total} story-runs")
    print(f" trial dir:   {trial_dir}")
    print(bar)
    print()


def _print_trial_footer(trial_dir: Path, elapsed: float, n_total: int,
                        total_calls: int, total_fails: int):
    bar = "=" * 70
    print(bar)
    print(f" trial complete in {_fmt_duration(elapsed)}")
    print(f" story-runs:     {n_total}")
    print(f" total calls:    {total_calls}")
    print(f" parse failures: {total_fails}")
    print(f" trial dir:      {trial_dir}")
    print(bar)
    print()


def _save_raw(raw_dir: Path, result: tasks.StoryRunResult):
    fname = f"{result.story_id}__{result.condition}__seed{result.seed}.jsonl"
    with open(raw_dir / fname, "w") as f:
        for c in result.comprehension:
            f.write(json.dumps(asdict(c)) + "\n")
        if result.ordering is not None:
            f.write(json.dumps(asdict(result.ordering)) + "\n")
        for c in result.pair_scaling:
            f.write(json.dumps(asdict(c)) + "\n")
        for c in result.counterfactual:
            f.write(json.dumps(asdict(c)) + "\n")


def _save_parsed(parsed_dir: Path, results: list[tasks.StoryRunResult], stimuli: StimulusBundle):
    # Comprehension: per-item correctness
    comp_rows = []
    for r in results:
        items_by_id = {it.id: it for it in stimuli.get_comprehension_items(r.story_id)}
        for c in r.comprehension:
            gold = items_by_id[c.sub_id].correct
            comp_rows.append({
                "story_id": r.story_id, "condition": r.condition, "seed": r.seed,
                "item_id": c.sub_id, "parsed": c.parsed, "gold": gold,
                "correct": (c.parsed == gold) if c.parsed is not None else None,
                "n_retries": c.n_retries,
            })
    (parsed_dir / "comprehension.json").write_text(json.dumps(comp_rows, indent=2))

    # Ordering: list per (story, condition, seed) plus Kendall tau (computed later in visualise)
    ord_rows = []
    for r in results:
        if r.ordering is None:
            continue
        ord_rows.append({
            "story_id": r.story_id, "condition": r.condition, "seed": r.seed,
            "parsed": r.ordering.parsed,
            "raw": r.ordering.raw_response,
            "n_retries": r.ordering.n_retries,
        })
    (parsed_dir / "ordering.json").write_text(json.dumps(ord_rows, indent=2))

    # Pair scaling: 8x8 matrix per (story, condition, seed), keyed by chronological event ids
    matrices = []
    for r in results:
        if not r.pair_scaling:
            continue
        story = stimuli.get_story(r.story_id, r.condition)
        chrono_ids = [e.id for e in story.events_chronological]
        M = tasks.pair_scaling_to_matrix(r.pair_scaling, chrono_ids)
        gold_graph = stimuli.get_author_intended_graph(r.story_id)
        ps_metrics = pair_scaling_metrics.compute_all(
            {"event_ids_chronological": chrono_ids, "matrix": M},
            gold_graph,
        )
        ps_metrics = {k: _json_float_or_none(v) for k, v in ps_metrics.items()}
        matrices.append({
            "story_id": r.story_id, "condition": r.condition, "seed": r.seed,
            "event_ids_chronological": chrono_ids,
            "matrix": M,
            "n_parse_failures": sum(
                1 for c in r.pair_scaling if c.parsed is None
            ),
            **ps_metrics,
        })
    (parsed_dir / "pair_scaling_matrices.json").write_text(json.dumps(matrices, indent=2))

    # Counterfactual: anchor vector + null controls + discrimination index per (story, cond, seed)
    cf_rows = []
    for r in results:
        if not r.counterfactual:
            continue
        probes = stimuli.get_cf_probes(r.story_id)
        summary = tasks.cf_calls_to_summary(r.counterfactual, probes)
        cf_rows.append({
            "story_id": r.story_id, "condition": r.condition, "seed": r.seed,
            **summary,
        })
    (parsed_dir / "counterfactual.json").write_text(json.dumps(cf_rows, indent=2))
