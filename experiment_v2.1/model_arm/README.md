# `model_arm` — model behavioural arm (Python)

Python module that runs the **same task battery** as the jsPsych human experiment, but on language models. Lives alongside the JS experiment in `experiment_v2.1/`. This folder currently covers the **behavioural mirror** of the human arm; the planned **hidden-state probing** stage (Stage 3) will live in a sibling folder, `probing/`, sharing the stimulus loader, sweep convention, and second-order RSA helpers documented here.

For the cross-arm overview see [`../../README.md`](../../README.md); for the human arm see [`../README.md`](../README.md).

## Layout

```
model_arm/
├── README.md
├── requirements.txt
├── run_pilot.py            # entry: run the Qwen pilot
├── smoke_test.py           # entry: end-to-end synthetic test (no Qwen)
├── stimuli/
│   └── stimuli.json        # all stimuli, ported from src/stimuli/*.js
├── src/                    # python package
│   ├── __init__.py
│   ├── stimuli_loader.py   # typed accessors over stimuli.json
│   ├── prompts.py          # prompt templates (neutral, no CoT)
│   ├── parsers.py          # robust response parsers
│   ├── tasks.py            # comprehension / ordering / pair_scaling logic
│   ├── model.py            # HFConversation (Qwen) + MockConversation
│   ├── runner.py           # trial orchestration + structured output
│   └── visualise.py        # heatmaps, ordering plots, summary figures
└── outputs/                # one timestamped folder per trial (runtime)
```

## Setup

```bash
cd experiment_v2.1/model_arm
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Smoke test (no model required)

```bash
python smoke_test.py
```

Runs the full pipeline against `MockConversation`, which returns synthetic responses derived from the author-intended graph plus condition-dependent noise (linear cleanest, atemporal noisiest). Use this to confirm the plumbing and figures work before burning Qwen time.

## Pilot trial (Qwen 2.5 7B Instruct)

```bash
python run_pilot.py
```

Defaults:
- Stories: `hospital_incident`, `school_trip`
- Conditions: `linear`, `nonlinear`, `atemporal`
- Seeds: `0, 1, 2`
- Tasks: comprehension, ordering, per-pair pair scaling, counterfactual probes

Quick run with one seed and no pair-scaling (~2 minutes on Qwen 7B/MPS):
```bash
python run_pilot.py --seeds 0 --skip-pair-scaling
```

Full pilot (long; expect ~30–60 min on M5 24GB for the pair-scaling task alone):
```bash
python run_pilot.py
```

## What gets saved

```
outputs/trial_<YYYYMMDD_HHMMSS>_<run_id>/
├── manifest.json
├── raw/                                      # one .jsonl per (story, condition, seed)
├── parsed/
│   ├── comprehension.json                    # per-item correct/incorrect
│   ├── ordering.json                         # predicted permutation per run
│   ├── pair_scaling_matrices.json            # 8×8 matrices + vs-gold metrics (Pearson, Spearman, edge F1, …)
│   └── counterfactual.json                   # anchor vector + null controls + discrimination index
├── figures/
│   ├── pair_scaling_<story>__<cond>__seed<n>.png
│   ├── author_intended_<story>.png           # reference
│   ├── diagnostics/pair_scaling_vs_gold_metrics.png  # Pearson, Spearman, edge F1, directional accuracy
│   ├── orderings.png                         # per-condition Kendall τ panel
│   ├── comprehension_accuracy.png
│   ├── cf_anchor_vectors.png                 # length-6 anchor vector per story
│   ├── cf_discrimination.png                 # CF discrimination index per (story, condition)
│   └── summary.png                           # one-page landing
└── logs/run.log
```

## Design choices

- **Multi-turn conversation per story.** The model reads the story once, then answers all tasks within the same chat history (mirroring how a participant works through one story without re-reading it for every question). Re-seeded per (story, condition, seed).
- **Per-pair pair scaling.** 56 separate prompts per story, mirroring the human task. Slower than asking for the full matrix in one shot, but produces cleaner per-pair behaviour and matches the human comparator.
- **Neutral prompts.** No chain-of-thought primer, no examples, no causal hints. Output formats are minimal so parsing is robust. A CoT variant can be added later as a separate condition.
- **Heatmap rows/columns are sorted by canonical chronological position** (E1..E8), not presentation order. This means the same author-intended graph appears in the same place across all three conditions — condition differences in the model's responses pop visually rather than being confounded with reading order.

## Notes on stimulus alignment

- **Stimuli source of truth.** Right now `stimuli/stimuli.json` is a JSON port of the JS files (`stories.js`, `event_cards.js`, `comprehension.js`, `cf_probes.js`, plus `author_intended_graphs.json`). If you change stimuli on the JS side, re-run the port script. A future cleanup could promote the JSON to be the single source of truth and have both sides read from it.
- **Domain coverage.** The model arm runs on all eight source domains. The human arm only uses six of them (`care_home_incident` and `family_conflict` are filtered out at allocation time on the JS side), but every source file retains all eight so the model arm and the planned probing stage have the full set.
- **CF discrimination index.** `parsed/counterfactual.json` records `mean(|anchor − 3|) − mean(|null − 3|)` per (story, condition, seed). A clean causal model gives a large positive index (anchors swing away from "no change", null controls genuinely centred). This is the secondary CF output described in `task_design_1` §7.5.

## Stage 3 (planned) — hidden-state probing

The behavioural mirror tells us *what* the model's outputs do across conditions. Stage 3 targets *where in the model* the temporal/causal structure is represented, by capturing residual-stream activations as the model works through the same battery.

Working plan (lives in a future sibling folder, `probing/`):

1. **Activation capture.** Forward-hook the residual stream of each open-weights model in the registry (Qwen 2.5 7B, Qwen 3 8B, Llama 3.1 8B, Mistral 7B; potentially Qwen 14B/32B via MLX) at every transformer layer. Capture hidden states at fixed anchor positions — the final token of each event sentence during reading, the final token of each task prompt, and the model's first generated token per task. Save per (model, story, condition, seed, layer).
2. **Event-level RDMs.** For each (model, condition, seed, layer), build an 8×8 RDM from cosine distances between captured hidden-state vectors. This is the hidden-state analogue of the behavioural arm's 8×8 pair-scaling matrix.
3. **Reuse `src/meta_rsa.py`.** The same *1 − Spearman ρ over the 56 off-diagonal cells* RSA distance applies. The headline contrasts are layer-wise correlations between hidden-state RDMs and (a) the model's own pair-scaling RDM, (b) the human pair-scaling RDM where available, (c) an RDM derived from the gold-standard graph in `author_intended_graphs.json`.
4. **Condition contrasts.** Same linear → atemporal contrast as in the behavioural arm, layer by layer; each story acts as its own paired baseline.
5. **Linear probes (secondary).** Lightweight linear classifiers over the captured states for (i) canonical chronological position of the anchor event, (ii) presence of a causal edge between two named events. The layer-wise accuracy curve complements the RSA picture.

The probing folder will reuse the same stimulus loader, sweep folder convention, and RDM utilities as this folder, so the analysis stack stays the same across all three stages of the project.
