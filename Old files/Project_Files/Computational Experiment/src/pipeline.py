"""
Pipeline: orchestrates the incremental event graph construction.

Feeds story segments one at a time to the model, collects the
evolving graph state at each step, then runs a revision pass.

Saves two graphs per trial:
  - incremental_graph.json  (final state after last segment)
  - revised_graph.json      (after model reviews and revises)

Output structure:
  outputs/{story_id}_trial_{N}/
    ├── incremental_graph.json
    ├── revised_graph.json
    ├── step_metadata.json
    └── evaluation.json

Usage:
    python -m src.pipeline --story medical_short_linear --model Qwen/Qwen2.5-7B-Instruct
"""

from __future__ import annotations

import json
import time
import argparse
from pathlib import Path
from datetime import datetime

from src.segmenter import get_segments, get_event_map, list_stories
from src.prompt_templates import (
    build_system_prompt, build_init_prompt, build_update_prompt,
    build_retry_prompt, build_revision_prompt
)
from src.inference import load_model, generate, extract_json
from src.graph_validator import validate_graph, repair_common_issues, is_valid
from src.evaluate import load_gold_standard, full_evaluation, print_evaluation


def _next_trial_number(output_dir: Path, story_id: str) -> int:
    """Find the next available trial number for a story."""
    existing = list(output_dir.glob(f"{story_id}_trial_*"))
    if not existing:
        return 1
    numbers = []
    for p in existing:
        try:
            n = int(p.name.split("_trial_")[-1])
            numbers.append(n)
        except ValueError:
            continue
    return max(numbers) + 1 if numbers else 1


def _generate_with_retries(
    model_bundle: dict,
    system_prompt: str,
    user_prompt: str,
    max_retries: int = 2,
    verbose: bool = False,
    label: str = "",
) -> tuple[dict | None, str]:
    """
    Generate and parse JSON with retries.

    Returns (parsed_graph_or_None, status_string).
    """
    parsed = None
    for attempt in range(max_retries + 1):
        raw_response = generate(
            model_bundle, system_prompt, user_prompt,
            verbose=verbose
        )
        parsed = extract_json(raw_response)
        if parsed is not None:
            parsed = repair_common_issues(parsed)
            issues = validate_graph(parsed)
            if not issues:
                return parsed, "ok"
            elif verbose:
                print(f"  {label} attempt {attempt + 1}: validation issues: {issues}")
        elif verbose:
            print(f"  {label} attempt {attempt + 1}: failed to parse JSON")

    # Return whatever we have, even if invalid
    if parsed is not None:
        issues = validate_graph(parsed)
        return parsed, f"invalid: {issues}"
    return None, "parse_failure"


def run_incremental_construction(
    model_bundle: dict,
    story_id: str,
    verbose: bool = False,
    max_retries: int = 2,
) -> dict:
    """
    Run the full incremental graph construction + revision for one story.

    Returns dict with:
        - incremental_graph: graph after last segment (pre-revision)
        - revised_graph: graph after revision pass
        - intermediate_states: graph state after each incremental step
        - step_metadata: timing and validation info per step
        - revision_metadata: timing and status of revision step
    """
    segments = get_segments(story_id)
    event_map = get_event_map(story_id)
    system_prompt = build_system_prompt()

    intermediate_states = []
    step_metadata = []
    current_graph = None
    current_graph_json = ""

    # === INCREMENTAL CONSTRUCTION ===
    for step, segment in enumerate(segments):
        step_start = time.time()
        expected_event = event_map[step]
        count_before = len(current_graph["events"]) if current_graph else 0

        if step == 0:
            user_prompt = build_init_prompt(segment)
        else:
            user_prompt = build_update_prompt(current_graph_json, segment)

        parsed, status = _generate_with_retries(
            model_bundle, system_prompt, user_prompt,
            max_retries=max_retries, verbose=verbose,
            label=f"Step {step}",
        )

        # Check if the model actually added a new event
        if parsed is not None and step > 0:
            count_after = len(parsed.get("events", []))
            if count_after <= count_before:
                if verbose:
                    print(f"  Step {step}: event count unchanged ({count_after}) — retrying with nudge")

                retry_prompt = build_retry_prompt(current_graph_json, segment)
                retry_parsed, retry_status = _generate_with_retries(
                    model_bundle, system_prompt, retry_prompt,
                    max_retries=max_retries, verbose=verbose,
                    label=f"Step {step} retry",
                )
                if retry_parsed is not None and len(retry_parsed.get("events", [])) > count_before:
                    parsed = retry_parsed
                    status = f"ok (after retry)"
                    if verbose:
                        print(f"  Step {step}: retry succeeded — {len(parsed['events'])} events")
                elif verbose:
                    print(f"  Step {step}: retry did not add event — model may have merged it")

        step_time = time.time() - step_start

        if parsed is not None:
            current_graph = parsed
            current_graph_json = json.dumps(parsed, indent=2)

        intermediate_states.append(
            json.loads(json.dumps(current_graph)) if current_graph else None
        )

        step_metadata.append({
            "step": step,
            "expected_event": expected_event,
            "status": status,
            "duration_s": round(step_time, 2),
            "n_events": len(current_graph["events"]) if current_graph else 0,
            "n_edges": len(current_graph["edges"]) if current_graph else 0,
        })

        if verbose:
            meta = step_metadata[-1]
            print(f"\n  Step {step}: segment for {expected_event} | "
                  f"status={meta['status']} | "
                  f"events={meta['n_events']} edges={meta['n_edges']} | "
                  f"{meta['duration_s']}s")

    # Save pre-revision graph
    incremental_graph = json.loads(json.dumps(current_graph)) if current_graph else None

    # === REVISION PASS ===
    revision_metadata = {"status": "skipped", "duration_s": 0}
    revised_graph = None

    if current_graph is not None:
        if verbose:
            print(f"\n  --- Revision pass ---")

        revision_start = time.time()
        revision_prompt = build_revision_prompt(current_graph_json)

        revised_parsed, revision_status = _generate_with_retries(
            model_bundle, system_prompt, revision_prompt,
            max_retries=max_retries, verbose=verbose,
            label="Revision",
        )

        revision_time = time.time() - revision_start

        if revised_parsed is not None:
            revised_graph = revised_parsed
        else:
            # Fall back to incremental graph if revision fails
            revised_graph = incremental_graph

        revision_metadata = {
            "status": revision_status,
            "duration_s": round(revision_time, 2),
            "n_events": len(revised_graph["events"]) if revised_graph else 0,
            "n_edges": len(revised_graph["edges"]) if revised_graph else 0,
        }

        if verbose:
            print(f"  Revision: status={revision_status} | "
                  f"events={revision_metadata['n_events']} "
                  f"edges={revision_metadata['n_edges']} | "
                  f"{revision_metadata['duration_s']}s")

    return {
        "incremental_graph": incremental_graph,
        "revised_graph": revised_graph,
        "intermediate_states": intermediate_states,
        "step_metadata": step_metadata,
        "revision_metadata": revision_metadata,
        "story_id": story_id,
        "model_id": model_bundle.get("model_id", "unknown"),
        "timestamp": datetime.now().isoformat(),
    }


def run_and_evaluate(
    model_bundle: dict,
    story_id: str,
    gold_standard: dict,
    output_dir: Path,
    verbose: bool = False,
) -> dict:
    """
    Run construction + revision + evaluation, save to trial folder.

    Output folder: {output_dir}/{story_id}_trial_{N}/
    """
    domain = story_id.split("_")[0]
    gold_graph = gold_standard[domain]

    # Determine trial number
    trial_num = _next_trial_number(output_dir, story_id)
    trial_dir = output_dir / f"{story_id}_trial_{trial_num}"
    trial_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'─' * 60}")
    print(f"  Story:  {story_id}")
    print(f"  Trial:  {trial_num}")
    print(f"  Output: {trial_dir}")
    print(f"{'─' * 60}")

    result = run_incremental_construction(model_bundle, story_id, verbose=verbose)

    # Evaluate both graphs against gold standard
    evaluations = {}

    for graph_name in ["incremental_graph", "revised_graph"]:
        graph = result[graph_name]
        if graph:
            ev = full_evaluation(graph, gold_graph)
            print_evaluation(ev, label=f"{story_id} — {graph_name}")
            evaluations[graph_name] = ev
        else:
            print(f"  ERROR: No valid {graph_name} produced.")
            evaluations[graph_name] = None

    # === Save to trial folder ===

    # 1. Incremental graph (pre-revision)
    with open(trial_dir / "incremental_graph.json", "w") as f:
        json.dump(result["incremental_graph"], f, indent=2)

    # 2. Revised graph (post-revision)
    with open(trial_dir / "revised_graph.json", "w") as f:
        json.dump(result["revised_graph"], f, indent=2)

    # 3. Step metadata (incremental steps + revision)
    with open(trial_dir / "step_metadata.json", "w") as f:
        json.dump({
            "story_id": result["story_id"],
            "model_id": result["model_id"],
            "timestamp": result["timestamp"],
            "trial": trial_num,
            "incremental_steps": result["step_metadata"],
            "revision": result["revision_metadata"],
        }, f, indent=2)

    # 4. Evaluation results (both graphs compared to gold)
    with open(trial_dir / "evaluation.json", "w") as f:
        json.dump(evaluations, f, indent=2)

    print(f"\n  Saved to: {trial_dir}/")

    result["evaluation"] = evaluations
    result["trial_num"] = trial_num
    result["trial_dir"] = str(trial_dir)
    return result


def main():
    parser = argparse.ArgumentParser(description="Incremental event graph construction")
    parser.add_argument("--story", type=str, default="medical_short_linear",
                        help=f"Story variant. Options: {list_stories()}")
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-7B-Instruct",
                        help="Model ID from Hugging Face Hub")
    parser.add_argument("--all-stories", action="store_true",
                        help="Run all story variants")
    parser.add_argument("--verbose", action="store_true",
                        help="Print prompts and responses")
    parser.add_argument("--output-dir", type=str, default="outputs",
                        help="Directory to save results")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load model
    print(f"Loading model: {args.model}")
    model_bundle = load_model(args.model)
    print(f"Model loaded ({model_bundle['backend']} backend)\n")

    # Load gold standard
    gold_standard = load_gold_standard()

    # Run stories
    stories = list_stories() if args.all_stories else [args.story]
    all_results = {}

    for story_id in stories:
        result = run_and_evaluate(
            model_bundle, story_id, gold_standard, output_dir, args.verbose
        )
        all_results[story_id] = result

    # Summary
    if len(stories) > 1:
        print(f"\n{'=' * 60}")
        print(f"  SUMMARY: {len(stories)} stories processed")
        print(f"{'=' * 60}")
        for sid, res in all_results.items():
            ev = res.get("evaluation", {})
            for graph_name in ["incremental_graph", "revised_graph"]:
                if ev.get(graph_name):
                    e = ev[graph_name]
                    c_f1 = e["causal_edges"]["strict"]["f1"]
                    order = e["ordering"]["pairwise_accuracy"]
                    t_acc = e["temporal_labels"]["accuracy"]
                    tag = "inc" if graph_name == "incremental_graph" else "rev"
                    print(f"  {sid:35s} [{tag}]  causal_F1={c_f1:.3f}  order={order:.1%}  temporal={t_acc:.1%}")


if __name__ == "__main__":
    main()
