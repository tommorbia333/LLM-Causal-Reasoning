"""
Resolve sweep CONFIG dict fields: which behavioural tasks to run and which
pair-scaling prompt variants to use.
"""

from __future__ import annotations

from .prompts import PAIR_SCALING_VARIANTS

ALL_TASKS = ("comprehension", "ordering", "pair_scaling", "counterfactual")


def resolve_tasks(config: dict) -> dict[str, bool]:
    """Return {task_name: enabled} from config['tasks'] or all enabled if omitted."""
    raw = config.get("tasks")
    if raw is None:
        return {name: True for name in ALL_TASKS}

    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError(
            "config['tasks'] must be a non-empty list, e.g. ['pair_scaling']. "
            f"Valid tasks: {list(ALL_TASKS)}"
        )

    unknown = set(raw) - set(ALL_TASKS)
    if unknown:
        raise ValueError(
            f"Unknown task(s) in config['tasks']: {sorted(unknown)}. "
            f"Valid tasks: {list(ALL_TASKS)}"
        )

    enabled = set(raw)
    return {name: (name in enabled) for name in ALL_TASKS}


def resolve_prompt_variants(config: dict, *, pair_scaling_enabled: bool) -> list[str]:
    """Return variant ids for sweep cells; validates against PAIR_SCALING_VARIANTS."""
    raw = config.get("prompt_variants")

    if not pair_scaling_enabled:
        return []

    if raw is None:
        raise ValueError(
            "config['prompt_variants'] is required when 'pair_scaling' is in tasks. "
            f"Available: {sorted(PAIR_SCALING_VARIANTS)}"
        )

    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError(
            "config['prompt_variants'] must be a non-empty list, "
            f"e.g. ['v5_human_like']. Available: {sorted(PAIR_SCALING_VARIANTS)}"
        )

    unknown = set(raw) - set(PAIR_SCALING_VARIANTS)
    if unknown:
        raise ValueError(
            f"Unknown prompt variant(s): {sorted(unknown)}. "
            f"Available: {sorted(PAIR_SCALING_VARIANTS)}"
        )

    return list(raw)


def resolve_sweep_settings(config: dict) -> tuple[dict[str, bool], list[str]]:
    """Return (task_flags, prompt_variants) from a CONFIG dict."""
    tasks = resolve_tasks(config)
    variants = resolve_prompt_variants(config, pair_scaling_enabled=tasks["pair_scaling"])
    return tasks, variants
