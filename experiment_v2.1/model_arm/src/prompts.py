"""
Prompt templates for the four behavioural tasks.

Pair-scaling has multiple variants used as a within-model manipulation:
a 2x2 design over scale-labelling (4-point anchoring vs 7-point full-scale)
crossed with question wording ("cause or contribute" vs strict "cause"). See
PAIR_SCALING_VARIANTS for the variant ID -> function mapping.

Design constraints (apply to all variants):
- Neutral framing: no chain-of-thought primer, no examples, no causal hints.
- No priming about the expected output distribution. Variants describe the
  scale, not what fraction of pairs should fall on each value. Anything like
  "most pairs of events have no causal relationship" is leading the witness
  and is excluded.
- Output formats are deliberately minimal so parsing is robust.

The runner builds a multi-turn conversation:
    [system] participant framing
    [user]   "Read this story." + full text + "Reply 'Ready' when done."
    [asst]   (model's ack)
    [user]   <task 1 prompt>
    [asst]   <task 1 response>
    ...
"""

from __future__ import annotations

from typing import Callable
from .stimuli_loader import Story, ComprehensionItem, Event, CFProbe


SYSTEM_PROMPT = (
    "You are a participant in a narrative comprehension study. "
    "You will read a short story, then answer a series of short questions about it. "
    "Read carefully and respond exactly in the format requested for each question. "
    "Do not add explanations unless asked."
)


# ---------------------------------------------------------------------------
# Story reading (turn 1)
# ---------------------------------------------------------------------------

def reading_prompt(story: Story) -> str:
    return (
        "Please read the following story carefully. "
        "Reply with only the word 'Ready' when you have finished reading.\n\n"
        f"{story.full_text}"
    )


# ---------------------------------------------------------------------------
# Task 1 — Comprehension
# ---------------------------------------------------------------------------

def comprehension_prompt(item: ComprehensionItem) -> str:
    return (
        f"{item.text}\n\n"
        "Answer with one word only: Yes, No, or Unsure."
    )


# ---------------------------------------------------------------------------
# Task 2 — Chronological ordering
# ---------------------------------------------------------------------------

def ordering_prompt(scrambled: list[Event]) -> str:
    cards = "\n".join(f"  ({i+1}) {ev.card}" for i, ev in enumerate(scrambled))
    return (
        "Below are the eight events of the story you just read, presented in random order. "
        "The numbers in parentheses are arbitrary labels that do NOT reflect the order in "
        "which the events occurred or were presented. Please put the events in the order in "
        "which they actually happened, from first to last.\n\n"
        f"{cards}\n\n"
        "Reply with only a comma-separated list of the labels (without parentheses) in "
        "chronological order, for example: 3, 7, 1, 5, 2, 6, 4, 8"
    )


# ---------------------------------------------------------------------------
# Task 3 — Directed pair scaling (variants for prompt manipulation)
# ---------------------------------------------------------------------------
#
# 2x2 design:
#                        permissive wording        strict wording
#                        ("cause or contribute")   ("cause")
#   4-point anchoring:   v1_original               v3_strict
#   7-point labelling:   v2_full_scale             v4_full_strict
#
# Each variant differs from v1 along ONE axis (or both, in v4), so per-variant
# differences in the model's output are attributable to that axis.

# Another prompt test that mirrors the human task and uses 1, 3, 6 labels

def _pair_scaling_v1_original(source: Event, target: Event) -> str:
    """Production baseline: 4-point anchoring + permissive wording.

    This is the prompt that produced the {0, 2, 4, 6} output compression and
    over-attribution to non-causal pairs. Kept as the reference cell of the 2x2.
    """
    return (
        f'How much did this event:\n  "{source.card}"\n'
        f'cause or contribute to this event:\n  "{target.card}"\n\n'
        "Use the following 0–6 scale:\n"
        "  0 = no causal link\n"
        "  2–4 = enables / contributes\n"
        "  6 = direct cause\n\n"
        "Reply with only a single integer between 0 and 6."
    )


def _pair_scaling_v2_full_scale(source: Event, target: Event) -> str:
    """7-point labelling + permissive wording.

    Tests whether the {0, 2, 4, 6} compression is attributable to the
    incomplete labelling alone. Wording is held constant with v1.
    """
    return (
        f'How much did this event:\n  "{source.card}"\n'
        f'cause or contribute to this event:\n  "{target.card}"\n\n'
        "Use the following 0–6 scale:\n"
        "  0 = no causal connection\n"
        "  1 = very weak indirect link\n"
        "  2 = weak background condition\n"
        "  3 = moderate background condition\n"
        "  4 = substantial enabling factor\n"
        "  5 = strong cause\n"
        "  6 = direct, immediate cause\n\n"
        "Reply with only a single integer between 0 and 6."
    )


def _pair_scaling_v3_strict(source: Event, target: Event) -> str:
    """4-point anchoring + strict wording.

    Tests whether the over-attribution to non-causal pairs is attributable to
    the permissive 'or contribute to' wording. Labelling is held constant
    with v1.
    """
    return (
        f'How much did this event:\n  "{source.card}"\n'
        f'cause this event:\n  "{target.card}"\n\n'
        "Use the following 0–6 scale:\n"
        "  0 = no causal link\n"
        "  2–4 = partial or indirect cause\n"
        "  6 = direct cause\n\n"
        "Reply with only a single integer between 0 and 6."
    )


def _pair_scaling_v4_full_strict(source: Event, target: Event) -> str:
    """7-point labelling + strict wording (both manipulations applied).

    Cleanest reformulation. If only this variant produces good calibration,
    both axes mattered. If v2 or v3 individually match v4, only one axis
    mattered.
    """
    return (
        f'How much did this event:\n  "{source.card}"\n'
        f'cause this event:\n  "{target.card}"\n\n'
        "Use the following 0–6 scale:\n"
        "  0 = no causal connection\n"
        "  1 = very weak indirect link\n"
        "  2 = weak partial cause\n"
        "  3 = moderate partial cause\n"
        "  4 = substantial partial cause\n"
        "  5 = strong cause\n"
        "  6 = direct, immediate cause\n\n"
        "Reply with only a single integer between 0 and 6."
    )

def _pair_scaling_v5_human_like(source: Event, target: Event) -> str:
    """Mirrored after the human task interface."""
    return (
        f'First event: "{source.card}"\n'
        f'Second event: "{target.card}"\n\n'
        "How much did the first event cause or contribute to the second?\n\n"
        "  0 = no causal link\n"
        "  1\n"
        "  2\n"
        "  3 = enables / contributes\n"
        "  4\n"
        "  5\n"
        "  6 = direct cause\n\n"
        "Reply with only a single integer between 0 and 6."
    )

PAIR_SCALING_VARIANTS: dict[str, Callable[[Event, Event], str]] = {
    "v1_original":     _pair_scaling_v1_original,
    "v2_full_scale":   _pair_scaling_v2_full_scale,
    "v3_strict":       _pair_scaling_v3_strict,
    "v4_full_strict":  _pair_scaling_v4_full_strict,
    "v5_human_like":   _pair_scaling_v5_human_like,
}

DEFAULT_PAIR_SCALING_VARIANT = "v1_original"


def pair_scaling_prompt(
    source: Event,
    target: Event,
    variant: str = DEFAULT_PAIR_SCALING_VARIANT,
) -> str:
    """Render a pair-scaling prompt for the named variant.

    Raises ValueError if the variant is unknown — fail loudly rather than
    silently fall back, since variant identity matters for analysis.
    """
    if variant not in PAIR_SCALING_VARIANTS:
        raise ValueError(
            f"Unknown pair-scaling variant: {variant!r}. "
            f"Available: {sorted(PAIR_SCALING_VARIANTS)}"
        )
    return PAIR_SCALING_VARIANTS[variant](source, target)


# ---------------------------------------------------------------------------
# Task 4 — Counterfactual probes
# ---------------------------------------------------------------------------

def counterfactual_prompt(probe: CFProbe) -> str:
    return (
        f"{probe.text}\n\n"
        "Use this 5-point scale:\n"
        "  1 = Much less likely\n"
        "  2 = Less likely\n"
        "  3 = No change / unsure\n"
        "  4 = More likely\n"
        "  5 = Much more likely\n\n"
        "Reply with only a single integer between 1 and 5."
    )
