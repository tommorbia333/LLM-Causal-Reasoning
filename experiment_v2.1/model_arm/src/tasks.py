"""
Task definitions: each task wraps a prompt template, a parser, and the
loop logic for producing a structured per-story output.

Tasks operate on a Conversation object (defined in model.py) so they can
keep the story in context across the full battery for one (story × condition × seed).
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any

from tqdm.auto import tqdm

from . import prompts
from .parsers import parse_comprehension, parse_ordering, parse_rating
from .stimuli_loader import Story, ComprehensionItem, CFProbe



# -----------------------------------------------------------------------------
# Result containers
# -----------------------------------------------------------------------------

@dataclass
class TaskCall:
    """One model call (prompt → response → parsed value)."""
    task: str
    sub_id: str            # e.g. comprehension item id, "ordering", or "Ei->Ej" for pair scaling
    prompt: str
    raw_response: str
    parsed: Any            # type depends on task
    n_retries: int = 0
    elapsed_seconds: float = 0.0


@dataclass
class StoryRunResult:
    story_id: str
    condition: str
    seed: int
    comprehension: list[TaskCall] = field(default_factory=list)
    ordering: TaskCall | None = None
    pair_scaling: list[TaskCall] = field(default_factory=list)
    counterfactual: list[TaskCall] = field(default_factory=list)


# -----------------------------------------------------------------------------
# Task 1: Comprehension
# -----------------------------------------------------------------------------

def run_comprehension(conv, items: list[ComprehensionItem], max_retries: int = 2) -> list[TaskCall]:
    calls = []
    pbar = tqdm(items, desc=f"  {'comprehension':14s}", leave=True,
                dynamic_ncols=True, unit="item")
    for item in pbar:
        t0 = time.time()
        conv.restore_snapshot()  # fresh story-primed state per item
        prompt = prompts.comprehension_prompt(item)
        raw, parsed, n_retries = _ask_with_retry(
            conv, prompt, parser=parse_comprehension, max_retries=max_retries
        )
        elapsed = time.time() - t0
        calls.append(TaskCall(
            task="comprehension", sub_id=item.id,
            prompt=prompt, raw_response=raw, parsed=parsed,
            n_retries=n_retries, elapsed_seconds=round(elapsed, 2),
        ))
        n_fails = sum(1 for c in calls if c.parsed is None)
        pbar.set_postfix_str(f"fails={n_fails}, last={elapsed:.1f}s")
    return calls


# -----------------------------------------------------------------------------
# Task 2: Chronological ordering
# -----------------------------------------------------------------------------

def run_ordering(conv, story: Story, seed: int, max_retries: int = 2) -> TaskCall:
    rng = random.Random(seed)
    scrambled = list(story.events_chronological)
    rng.shuffle(scrambled)

    # Local labels "1".."8" assigned to scrambled events. The model NEVER sees
    # canonical event IDs (E1..E8) — those would leak chronological order
    # because E1..E8 are the canonical chronological IDs.
    local_labels = [str(i + 1) for i in range(len(scrambled))]
    local_to_canonical = dict(zip(local_labels, [ev.id for ev in scrambled]))

    print(f"  {'ordering':14s} ", end="", flush=True)
    t0 = time.time()
    conv.restore_snapshot()
    prompt = prompts.ordering_prompt(scrambled)
    raw, parsed_local, n_retries = _ask_with_retry(
        conv, prompt,
        parser=lambda r: parse_ordering(r, local_labels),
        max_retries=max_retries,
    )
    elapsed = time.time() - t0

    # Map model's local-label permutation back to canonical event IDs
    if parsed_local is not None:
        parsed = [local_to_canonical[lbl] for lbl in parsed_local]
    else:
        parsed = None

    status = "✓" if parsed is not None else "✗ (parse failed)"
    print(f"{status} {elapsed:.1f}s")
    return TaskCall(
        task="ordering", sub_id="ordering",
        prompt=prompt, raw_response=raw, parsed=parsed,
        n_retries=n_retries, elapsed_seconds=round(elapsed, 2),
    )


# -----------------------------------------------------------------------------
# Task 3: Directed pair scaling (56 calls per story)
# -----------------------------------------------------------------------------

def run_pair_scaling(conv, story: Story, seed: int, max_retries: int = 2,
                     variant: str = "v1_original") -> list[TaskCall]:    # ← add kwarg
    events_chrono = story.events_chronological
    pairs = [
        (s, t) for s in events_chrono for t in events_chrono if s.id != t.id
    ]
    assert len(pairs) == 56, f"expected 56 ordered pairs, got {len(pairs)}"

    rng = random.Random(seed + 1)
    rng.shuffle(pairs)

    calls = []
    pbar = tqdm(pairs, desc=f"  {'pair scaling':14s}", leave=True,
                dynamic_ncols=True, unit="pair")
    for src, tgt in pbar:
        t0 = time.time()
        conv.restore_snapshot()
        prompt = prompts.pair_scaling_prompt(src, tgt, variant=variant) 
        raw, parsed, n_retries = _ask_with_retry(
            conv, prompt, parser=parse_rating, max_retries=max_retries,
        )
        elapsed = time.time() - t0
        calls.append(TaskCall(
            task="pair_scaling", sub_id=f"{src.id}->{tgt.id}",
            prompt=prompt, raw_response=raw, parsed=parsed,
            n_retries=n_retries, elapsed_seconds=round(elapsed, 2),
        ))
        n_fails = sum(1 for c in calls if c.parsed is None)
        pbar.set_postfix_str(f"fails={n_fails}, last={elapsed:.1f}s")
    return calls


# -----------------------------------------------------------------------------
# Task 4: Counterfactual probes (8 calls per story: 6 anchor + 2 null controls)
# -----------------------------------------------------------------------------

def run_counterfactual(conv, probes: list[CFProbe], seed: int, max_retries: int = 2) -> list[TaskCall]:
    rng = random.Random(seed + 2)
    order = list(probes)
    rng.shuffle(order)

    calls = []
    pbar = tqdm(order, desc=f"  {'counterfactual':14s}", leave=True,
                dynamic_ncols=True, unit="probe")
    for probe in pbar:
        t0 = time.time()
        conv.restore_snapshot()  # fresh story-primed state per probe
        prompt = prompts.counterfactual_prompt(probe)
        raw, parsed, n_retries = _ask_with_retry(
            conv, prompt,
            parser=lambda r: parse_rating(r, lo=1, hi=5),
            max_retries=max_retries,
        )
        elapsed = time.time() - t0
        calls.append(TaskCall(
            task="counterfactual", sub_id=probe.id,
            prompt=prompt, raw_response=raw, parsed=parsed,
            n_retries=n_retries, elapsed_seconds=round(elapsed, 2),
        ))
        n_fails = sum(1 for c in calls if c.parsed is None)
        pbar.set_postfix_str(f"fails={n_fails}, last={elapsed:.1f}s")
    return calls


# -----------------------------------------------------------------------------
# Shared retry helper
# -----------------------------------------------------------------------------

def _ask_with_retry(conv, prompt: str, parser, max_retries: int = 2):
    """
    Ask the model, parse, retry with a clarification appendix on parse failure.
    On final failure returns (last_raw, None, n_retries).
    """
    n_retries = 0
    raw = conv.ask(prompt)
    parsed = parser(raw)
    while parsed is None and n_retries < max_retries:
        n_retries += 1
        # Re-ask with a clarification, but DON'T persist the bad turn into the
        # conversation history — pop it before re-asking.
        conv.pop_last_turn()
        clarif = (
            prompt
            + "\n\nReminder: respond ONLY in the exact format requested. Do not add "
            "any other text, punctuation, or explanation."
        )
        raw = conv.ask(clarif)
        parsed = parser(raw)
    return raw, parsed, n_retries


# -----------------------------------------------------------------------------
# Building blocks the runner uses
# -----------------------------------------------------------------------------

def pair_scaling_to_matrix(calls: list[TaskCall], event_ids: list[str]) -> list[list[float | None]]:
    """Convert pair-scaling calls into an 8×8 asymmetric matrix indexed by chronological order."""
    idx = {eid: i for i, eid in enumerate(event_ids)}
    n = len(event_ids)
    M = [[None] * n for _ in range(n)]
    for c in calls:
        src, tgt = c.sub_id.split("->")
        if src in idx and tgt in idx:
            M[idx[src]][idx[tgt]] = c.parsed
    return M


def cf_calls_to_summary(calls: list[TaskCall], probes: list[CFProbe]) -> dict:
    """
    Structure CF responses into:
      - anchor_vector: length-6 list indexed by antecedent event (E1..E6)
      - sibling_null:  scalar
      - reverse_null:  scalar
      - discrimination_index: mean(|anchor − 3|) − mean(|null − 3|)
        (positive = clean causal model; null controls genuinely centred,
        anchors away from centre)
    """
    by_id = {c.sub_id: c for c in calls}
    role_lookup = {p.id: p for p in probes}

    anchor_vector: list[int | None] = [None] * 6  # indexed by E1..E6 → idx 0..5
    sibling_null: int | None = None
    reverse_null: int | None = None

    for c in calls:
        probe = role_lookup.get(c.sub_id)
        if probe is None:
            continue
        if probe.role == "anchor":
            ant_idx = int(probe.antecedent[1:]) - 1  # E1 → 0, E6 → 5
            if 0 <= ant_idx < 6:
                anchor_vector[ant_idx] = c.parsed
        elif probe.role == "sibling_null":
            sibling_null = c.parsed
        elif probe.role == "reverse_null":
            reverse_null = c.parsed

    def _abs_diff_from_3(x):
        return abs(x - 3) if x is not None else None

    anchor_mags = [_abs_diff_from_3(v) for v in anchor_vector if v is not None]
    null_mags = [_abs_diff_from_3(v) for v in (sibling_null, reverse_null) if v is not None]
    discrimination_index = (
        (sum(anchor_mags) / len(anchor_mags) if anchor_mags else 0)
        - (sum(null_mags) / len(null_mags) if null_mags else 0)
    )

    return {
        "anchor_vector": anchor_vector,
        "sibling_null": sibling_null,
        "reverse_null": reverse_null,
        "discrimination_index": round(discrimination_index, 3),
        "n_parse_failures": sum(1 for c in calls if c.parsed is None),
    }
