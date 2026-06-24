"""
All-models smoke test.

Purpose: after the run_pilot.py eviction fix, verify that every model in the
main_run roster can be loaded and produce real tokens, end-to-end. Run this
before kicking off another full sweep.

Each cell is the absolute minimum:
  - load the model
  - run the story-reading forward pass (1 generation call, unconditional)
  - run the `ordering` task (1 more generation call)
  - then evict before loading the next cell

Total: 4 cells × 2 calls = 8 generation calls. Wall-clock is dominated by
model loading and one-time weight downloads.

Expected behaviour with the fix:
  cell 1: Qwen2.5-7B loads → reads story → evicts
  cell 2: MLX 14B loads (previous freed) → reads story → evicts
  cell 3: Qwen3-8B loads (previous freed) → reads story → evicts
  cell 4: Llama 3.1-8B loads → reads story

Memory peak: ≤16 GB at any one moment, well under M5 24 GB unified ceiling.

Heads-up: if Llama-3.1-8B weights aren't yet in the HF cache, cell 4 will
download ~16 GB on first run. The sweep continues past per-cell failures,
so a Llama 401 (auth not yet approved) won't block cells 1-3.

Run: python run_pilot.py smoke_all_models
"""

DESCRIPTION = "Load + first-pass smoke test across all 4 main_run models"

CONFIG = {
    "sweep_id":         "smoke_all_models",
    "models":           [
        "Qwen/Qwen2.5-7B-Instruct",
        "mlx-community/Qwen2.5-14B-Instruct-4bit",
        "Qwen/Qwen3-8B",
        "meta-llama/Meta-Llama-3.1-8B-Instruct",
    ],
    "tasks":            ["ordering"],
    "story_ids":        ["hospital_incident"],
    "conditions":       ["linear"],
    "seeds":            [0],
    "temperature":      0.7,
    "max_new_tokens":   80,
}
