"""
Main sweep template — fill in after pilot results.

This is a PLACEHOLDER. After running pilot_prompt_manipulation, edit:
  - prompt_variants: keep only the 1-2 variants that performed best
  - models: add Qwen3-8B (and potentially Qwen3.5-9B) once pipeline is verified
  - story_ids: expand to all 8 stories
  - seeds: increase to 10-20 if statistical power requires it

Approximate budget at full design (5 models × 2 variants × 8 stories × 3
conditions × 10 seeds): ~150,000 calls. Estimate compute time before launch.

Run: python run_pilot.py main_sweep
"""

DESCRIPTION = "TEMPLATE — edit after pilot results inform the design"

# All eight story domains (matches author_intended_graphs.json keys).
ALL_STORIES = [
    "hospital_incident",
    "care_home_incident",
    "community_fair",
    "restaurant_fire",
    "school_trip",
    "family_conflict",
    "power_cut",
    "missed_flight",
]

CONFIG = {
    "sweep_id":         "main_sweep",
    "models": [
        "Qwen/Qwen2.5-7B-Instruct",
        "Qwen/Qwen2.5-14B-Instruct",
        # "Qwen/Qwen3-8B",                # add once thinking-mode parsing exists
        "Qwen/Qwen3.5-9B",
    ],
    "prompt_variants":  ["v1_original"],   # ← replace after pilot
    "story_ids":        ALL_STORIES,
    "conditions":       ["linear", "nonlinear", "atemporal"],
    "seeds":            list(range(10)),    # 10 seeds; bump to 20 if CIs too wide
    "temperature":      0.7,
    "max_new_tokens":   80,
    "skip_existing":    True,               # safe to re-run if a cell crashes
}
