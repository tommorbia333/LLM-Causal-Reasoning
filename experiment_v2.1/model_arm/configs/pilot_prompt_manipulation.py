"""
Prompt-manipulation pilot.

Cell design: 1 model x 4 prompt variants x 1 story (hospital_incident) x 3
conditions x 5 seeds = 4 cells, 60 story-runs total.

Purpose
-------
Diagnose whether the {0, 2, 4, 6} output compression and over-attribution
to non-causal pairs (observed under v1_original) are due to:
  - scale labelling (4-anchor vs 7-point) — tested by v1 vs v2
  - question wording ("cause or contribute" vs "cause") — tested by v1 vs v3
  - both manipulations combined — tested by v1 vs v4

The diagonal of the 2x2 (v1 vs v4) is the cleanest contrast; v2 and v3
decompose which axis matters.

Expected outcomes
-----------------
- If v2 ≈ v4 > v1 in Pearson r: labelling matters more than wording.
- If v3 ≈ v4 > v1: wording matters more than labelling.
- If v4 > both v2 and v3 > v1: both manipulations contribute independently.
- If v1 ≈ v2 ≈ v3 ≈ v4: model's calibration is robust to prompt form
  (and the original framing wasn't the issue after all).

Approximate budget: ~4200 calls, ~2.5-3.5 hours on M5 with Qwen2.5-7B.

Run: python run_pilot.py pilot_prompt_manipulation
"""

DESCRIPTION = "2x2 prompt manipulation on hospital_incident across all 3 conditions"

""" List of all models, stories, seeds, prompt variants, tasks, and conditions.

``all_models`` must use exact ``model_id`` strings from ``src/models.py`` MODEL_REGISTRY
(see ``registry_key_for_hf_model_id`` in run_pilot.py).
"""

all_models = [
    "Qwen/Qwen2.5-7B-Instruct",                          # qwen7b (hf)
    "Qwen/Qwen3-8B",                                     # qwen3-8b (hf)
    "meta-llama/Meta-Llama-3.1-8B-Instruct",             # llama8b (hf)
    "mistralai/Mistral-7B-Instruct-v0.3",                # mistral7b (hf)
    "mlx-community/Qwen2.5-14B-Instruct-4bit",           # qwen14b (mlx) — fp16 14B won't fit on M5
    "mlx-community/Qwen3-14B-4bit",                      # qwen3-14b (mlx)
    "mlx-community/Qwen2.5-32B-Instruct-4bit",           # qwen32b (mlx)
    "gpt-4o",                                            # gpt4o (openai, needs OPENAI_API_KEY)
    "gpt-4o-mini",                                       # gpt4o-mini (openai)
    "claude-sonnet-4-5-20250929",                        # claude-sonnet (anthropic, needs ANTHROPIC_API_KEY)
]
# Not addable without further work:
#   "Qwen/Qwen3.5-9B"                       — only -Base released; no Instruct variant.
#   "Qwen/Qwen3.5-14B"                      — does not exist (Qwen3.5 sizes: 0.8/2/4/9/27/35/122/397).
#   "meta-llama/Meta-Llama-3.1-14B-Instruct"— does not exist (3.1 sizes: 8B/70B/405B).
#   "meta-llama/Meta-Llama-3.1-32B-Instruct"— does not exist.
#   "meta-llama/Meta-Llama-3.1-70B-Instruct"— exists, but won't fit on M5 24 GB even at 4-bit;
#                                              needs a hosted-API backend or remote GPU.
all_stories = ["hospital_incident", 
              # "care_home_incident", 
              "community_fair", 
              "restaurant_fire", 
              "school_trip", 
              # "family_conflict", 
              "power_cut", 
              "missed_flight"]
all_seeds = [0, 1, 2, 3, 4]
all_prompt_variants = ["v1_original", "v2_full_scale", "v3_strict", "v4_full_strict", "v5_human_like"]
all_tasks = ["comprehension", "ordering", "pair_scaling", "counterfactual"]
all_conditions = ["linear", "nonlinear", "atemporal"]

CONFIG = {
    "sweep_id":         "main_run_v5_prompt",
    "models":           [
      "Qwen/Qwen2.5-7B-Instruct",
      "mlx-community/Qwen2.5-14B-Instruct-4bit",   # fp16 14B won't fit on M5; use MLX 4-bit
      "Qwen/Qwen3-8B",
      "meta-llama/Meta-Llama-3.1-8B-Instruct",     # gated; run `huggingface-cli login` first
      ],
    "prompt_variants":  ["v5_human_like"],
    "tasks":            all_tasks, # omit to run full battery, keep to run only certain tasks
    "story_ids":        all_stories,
    "conditions":       ["linear", "nonlinear", "atemporal"],
    "seeds":            all_seeds, # list(range(10)),
    "temperature":      0.7,
    "max_new_tokens":   80,
    "skip_existing":    True,
}



# Plan for future tests:
# - Add more models
# - Add more stories
# - Tweak temperature
# - Try non-instruct models (i.e., reasoning)
