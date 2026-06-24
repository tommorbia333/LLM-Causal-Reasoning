# LLM Causal Reasoning — Computational Experiment

Incremental event-graph construction pipeline that tests whether large language models can build causal event graphs from narrative text, one segment at a time.

## Requirements

- **Python 3.9+**
- **PyTorch** with GPU support (MPS on Apple Silicon, CUDA on NVIDIA, or CPU fallback)
- ~14 GB free memory for Qwen 2.5 7B in float16

## Setup

```bash
cd "Project_Files/Computational Experiment"
pip install -r requirements.txt
```

This installs `transformers`, `torch`, `accelerate`, and `tqdm`. The first run downloads model weights from Hugging Face (~14 GB for Qwen 2.5 7B).

## Running the experiment

All commands are run from the `Project_Files/Computational Experiment/` directory.

**Single story (default model: Qwen 2.5 7B Instruct):**

```bash
python -m src.pipeline --story medical_short_linear --verbose
```

**All story variants:**

```bash
python -m src.pipeline --all-stories --verbose
```

**Specify a different model:**

```bash
python -m src.pipeline --story medical_short_linear --model meta-llama/Llama-3.1-8B-Instruct --verbose
```

**Custom output directory:**

```bash
python -m src.pipeline --story coastal_heavy_linear --output-dir my_results --verbose
```

### Available stories

| Story ID | Domain | Length | Presentation |
|---|---|---|---|
| `medical_short_linear` | Medical | Short | Chronological |
| `medical_short_nonlinear` | Medical | Short | Anachronological |
| `workplace_short_linear` | Workplace | Short | Chronological |
| `workplace_short_nonlinear` | Workplace | Short | Anachronological |
| `coastal_heavy_linear` | Coastal | Long + filler | Chronological |
| `coastal_heavy_nonlinear` | Coastal | Long + filler | Anachronological |

## Output structure

Each run creates a trial folder under `Outputs/`:

```
Outputs/{story_id}_trial_{N}/
├── incremental_graph.json   # Graph after last segment (pre-revision)
├── revised_graph.json       # Graph after model reviews and revises
├── step_metadata.json       # Timing and validation info per step
└── evaluation.json          # Comparison against gold standard
```

## Project structure

```
Data/
  Stories/                   Story PDFs used in the experiment
  gold_standard_graphs.json  Gold-standard event graphs per domain
src/
  segmenter.py               Story text segmented into per-event chunks
  prompt_templates.py         System and user prompts for the model
  inference.py                HF transformers model loading and generation
  graph_validator.py          Schema validation and repair
  pipeline.py                 Incremental construction loop + revision pass
  evaluate.py                 Evaluation against gold standard
Outputs/                     Model-generated graphs and metrics
```

## Graph schema

Each graph contains **events** (nodes) and **edges** (causal relations):

- **Events** have an ID, description, canonical position, and `time_to_next` label (one of: `minutes`, `hours`, `days`, `weeks`, `months`)
- **Edges** connect a cause event to an effect event with a causal subtype (`direct`, `enabling`, `preventive`, `temporal-only`)

See `Data/gold_standard_graphs.json` for the full schema definition.
