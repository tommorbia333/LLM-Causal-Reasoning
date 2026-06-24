"""
Run a custom subset of tasks and/or pair-scaling prompt variants.

Edit ``tasks`` and ``prompt_variants`` below, then:

    python run_pilot.py custom_task

Example — only pair scaling with the human-mirrored prompt (no comprehension,
ordering, or counterfactual):

    "tasks": ["pair_scaling"],
    "prompt_variants": ["v5_human_like"],

Available tasks: comprehension, ordering, pair_scaling, counterfactual
Available prompt variants: v1_original, v2_full_scale, v3_strict,
                           v4_full_strict, v5_human_like
"""

DESCRIPTION = "Custom task / prompt selection — edit tasks and prompt_variants below"

CONFIG = {
    "sweep_id": "custom_task",
    "models": ["Qwen/Qwen2.5-7B-Instruct"],
    # --- edit these two lists to match what you want to run ---
    "tasks": ["pair_scaling"],
    "prompt_variants": ["v5_human_like"],
    # ----------------------------------------------------------
    "story_ids": ["hospital_incident"],
    "conditions": ["linear", "nonlinear", "atemporal"],
    "seeds": [0, 1, 2, 3, 4],
    "temperature": 0.7,
    "max_new_tokens": 80,
    "skip_existing": False,
}