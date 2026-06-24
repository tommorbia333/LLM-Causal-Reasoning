"""
Smoke test: smallest possible configuration that exercises the full pipeline.

Use this to verify that:
  - model loads correctly
  - prompts render without error
  - parsers handle the model's actual outputs
  - figures get rendered
  - output directory structure is correct

Total: 1 cell × 1 story × 1 condition × 1 seed = ~70 calls. Should complete
in 3-5 minutes on M5 with Qwen2.5-7B.

Run: python run_pilot.py smoke_test
"""

DESCRIPTION = "Minimal pipeline sanity check (1 model x 1 variant x 1 story x 1 condition x 1 seed)"

CONFIG = {
    "sweep_id":         "smoke_test",
    "models":           ["Qwen/Qwen2.5-7B-Instruct"],
    "prompt_variants":  ["v1_original"],
    "story_ids":        ["hospital_incident"],
    "conditions":       ["linear"],
    "seeds":            [0],
    "temperature":      0.7,
    "max_new_tokens":   80,
}
