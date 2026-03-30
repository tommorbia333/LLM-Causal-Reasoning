# LLM Causal Reasoning

**Research question:** How does the temporal structure of a narrative (chronological vs anachronological) affect causal reasoning in humans and large language models?

This repository contains two parallel experiments — one computational and one behavioural — that probe causal understanding using the same set of short narratives. Each narrative describes a chain of causally related events (e.g. a medical incident, a workplace outage, a coastal flood). Participants (human or LLM) receive the story one segment at a time and must reconstruct the underlying causal event graph.

## Project structure

```
Project_Files/
├── Computational Experiment/   LLM-based incremental event graph construction
│   ├── src/                    Pipeline source code
│   ├── Data/                   Story PDFs and gold-standard graphs
│   └── Outputs/                Model-generated graphs and evaluation metrics
├── Human Experiment/           jsPsych behavioural experiment
│   ├── experiment.js           Trial logic and timeline
│   ├── plugin-card-board.js    Card-sort task (event ordering)
│   ├── plugin-causal-pair-scale.js  Causal strength ratings
│   └── plugin-responsibility-allocation.js  Responsibility judgements
└── Licensing/                  Third-party licence (jsPsych, MIT)
```

## Narratives

Three scenario domains, each written in two presentation orders:

| Domain | Setting | Events |
|---|---|---|
| **Medical** | Ventilator failure on an understaffed hospital ward | 8 |
| **Workplace** | Server outage after a failed configuration change | 8 |
| **Coastal** | Flood damage during a floodgate construction project | 8 |

Each domain has a **linear** (chronological) and **nonlinear** (anachronological) variant. The coastal domain also includes a **heavy-fluff** condition with additional filler text designed to test robustness to irrelevant detail.

## Computational experiment

An LLM receives story segments one at a time and incrementally builds a causal event graph. After all segments, a revision pass lets the model review and correct its graph. Both the incremental and revised graphs are evaluated against hand-authored gold standards.

### Quick start

```bash
cd "Project_Files/Computational Experiment"
pip install -r requirements.txt

# Run a single story (default model: Qwen 2.5 7B Instruct)
python -m src.pipeline --story medical_short_linear --verbose

# Run all story variants
python -m src.pipeline --all-stories --verbose

# Use a different model
python -m src.pipeline --story medical_short_linear \
    --model meta-llama/Llama-3.1-8B-Instruct --verbose
```

**Requirements:** Python 3.9+, PyTorch with GPU support (MPS on Apple Silicon, CUDA on NVIDIA, or CPU fallback), and ~14 GB free memory for Qwen 2.5 7B in float16. The first run downloads model weights from Hugging Face.

### Evaluation metrics

| Metric | What it measures |
|---|---|
| Causal edge F1 (strict) | Precision and recall of cause-effect pairs, matched by event description |
| Causal edge F1 (relaxed) | Same, but allowing partial description matches |
| Pairwise ordering accuracy | Fraction of event pairs placed in the correct chronological order |
| Temporal label accuracy | Accuracy of `time_to_next` labels (immediate / short / medium / long) |

### Graph schema

Each graph is a JSON object with `events` and `edges`:

- **Events** carry an ID, natural-language description, `canonical_position` (chronological rank), and `time_to_next` (temporal gap to the next event).
- **Edges** represent causal relations with subtype `causes` (direct trigger) or `enables` (background condition).

See `Data/gold_standard_graphs.json` for the full schema and gold-standard graphs for all three domains.

## Human experiment

A browser-based behavioural experiment built with [jsPsych](https://www.jspsych.org/). Participants read the same narratives used in the computational experiment, then complete three tasks:

1. **Card sort** — drag-and-drop events into chronological order
2. **Causal pair ratings** — rate the causal strength between event pairs on a continuous scale
3. **Responsibility allocation** — distribute responsibility across contributing causes

The experiment is designed for deployment on [Cognition.run](https://www.cognition.run/) or any static hosting platform.

## Licence

The human experiment uses [jsPsych](https://github.com/jspsych/jsPsych) (MIT licence). See `Project_Files/Licensing/` for details.
