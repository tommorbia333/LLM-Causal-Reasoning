# Temporal Scaffolding and Causal World-Models in Narrative Comprehension

**Research question.** How does the temporal *presentation order* of a narrative — chronological, anachronological, or temporally-unmarked — shape the causal world-model a comprehender constructs? We address this with two parallel arms that share stimuli and tasks: a behavioural arm with human participants and a model arm with language models. A planned third stage adds hidden-state probing of the same models.

The same eight purpose-built short narratives drive both arms. Each story is presented in one of three linguistic conditions (linear / nonlinear / atemporal), and each comprehender — human or model — works through a fixed task battery aimed at exposing their internal model of *what caused what*.

## Repository layout

```
Dissertation/
├── README.md                                # this file
├── experiment_v2.1/                         # canonical implementation
│   ├── README.md                            # experiment_v2.1 entry point
│   ├── DATA_SCHEMA.md                       # human-side data export schema
│   ├── index.html                           # local browser test harness for the human arm
│   ├── src/, stimuli/, assets/              # human (jsPsych) experiment
│   ├── scripts/build_assignments.py         # 4-of-6 BIBD allocator + balance verifier
│   ├── smoke_test.js, synthetic_run.js      # JS-side build verifiers
│   ├── author_intended_graphs.json          # design-blueprint causal graphs (8 stories)
│   ├── implementation_documentation.{docx,pdf}
│   └── model_arm/                           # Python module — model behavioural arm
│       ├── README.md                        # model_arm entry point
│       ├── run_pilot.py                     # generic sweep launcher
│       ├── configs/                         # named sweep configurations
│       ├── src/                             # task runners, prompts, parsers, RSA helpers
│       ├── stimuli/stimuli.json             # ported stimuli (single JSON for all 8 domains)
│       └── outputs/                         # one timestamped folder per sweep
│
├── Old files/                               # archived legacy (pre-v2.1) experiments
├── Stories with questions/                  # early story-design PDFs
├── Licensing/                               # third-party licence notices
└── PUSH_TO_GITHUB.md
```

The legacy `Project_Files/` tree is preserved under `Old files/` for provenance only; **all current development lives under `experiment_v2.1/`**.

## Stimuli

Eight short narratives, written in-house, each around 250–350 words and segmented into eight causally-ordered events (`E1`–`E8`). Hand-authored gold-standard causal graphs live in `experiment_v2.1/author_intended_graphs.json`.

| Domain                | Topology              | Pool          |
|-----------------------|-----------------------|---------------|
| `hospital_incident`   | convergent            | human + model |
| `community_fair`      | convergent            | human + model |
| `restaurant_fire`     | convergent            | human + model |
| `school_trip`         | convergent            | human + model |
| `power_cut`           | convergent            | human + model |
| `missed_flight`       | convergent            | human + model |
| `care_home_incident`  | convergent (replicate) | model only   |
| `family_conflict`     | convergent            | model only   |

Each story exists in three condition variants:

- **linear** — events presented in their chronological order (E1 → E8);
- **nonlinear** — anachronological presentation (the fixed C-B-A-D block permutation: E5, E6, E3, E4, E1, E2, E7, E8);
- **atemporal** — same surface ordering as `nonlinear` but with grammatical tense neutralised, suppressing tense-based ordering cues.

The two "model only" domains stay in every source stimulus file (`stories.js`, `comprehension.js`, `event_cards.js`, `cf_probes.js`, `stimuli.json`) but are filtered out of the participant pool at allocation time, so they only ever reach the model arm and any future probing work.

## Task battery

Tasks are identical in design across arms; only the surface presentation differs (drag-and-drop UI for humans, structured-text prompts for models).

| Task                 | What it measures                                                              | Output                      | Human arm | Model arm |
|----------------------|-------------------------------------------------------------------------------|-----------------------------|-----------|-----------|
| Story reading        | Minimum dwell, scroll/focus tracking                                          | reading-time + activity log | yes       | yes (turn-1 ack) |
| Comprehension        | 6 yes/no/unsure items per story (compound, single, negative-recall, distractor) | accuracy + per-item RTs | yes       | yes       |
| Ordering             | Reconstruct the chronological order of 8 event cards + confidence rating       | permutation + Kendall τ     | yes       | yes       |
| Pair scaling         | 56 directed event-pair ratings (0–6) — the primary RSA matrix                  | 8×8 directed matrix         | yes       | yes       |
| Counterfactual probes | 6 anchor + 1 sibling-null + 1 reverse-null probe per story                    | anchor vector + discrimination index | **no** (excised from the human timeline) | yes |

The counterfactual probes were dropped from the participant-facing battery to keep the session under 60 minutes; the task code (`src/tasks/counterfactual.js`) and stimuli (`stimuli/cf_probes.js`) remain in the build for the model arm and any future re-instatement.

## Counterbalancing (human arm)

Each participant reads four of the six pool stories, in a position assigned by a preregistered table. The allocator (`experiment_v2.1/scripts/build_assignments.py`) is a 4-of-6 balanced incomplete block design crossed with Williams' 4-square orderings, giving 15 splits × 4 orderings = **60-row cycle**. Properties per 60-participant cycle (verified by the build script):

- each story is read in 40 of 60 sessions (exact);
- each unordered pair of stories co-occurs in 24 of 60 sessions (exact — no systematic pair co-occurrence);
- each story occupies each of the four positions exactly 10 times (exact, via the Williams squares);
- story × condition cells contain 13 or 14 reads (the tightest achievable balance: 40/3 is not integer).

Between-subjects condition assignment cycles in stratified blocks of 3 (`src/condition.js`); pair-presentation order and pair direction are randomised per participant within each story.

## Human arm — quick start

```bash
cd experiment_v2.1
python3 -m http.server 8000          # any static server
open http://localhost:8000/index.html
```

To verify the build without a browser:

```bash
cd experiment_v2.1
node smoke_test.js                   # sanity-check every global + builder
node synthetic_run.js                # end-to-end simulated participant
python3 scripts/build_assignments.py --check-only    # verify counterbalancing
```

The data schema produced by the participant-facing study is documented in `experiment_v2.1/DATA_SCHEMA.md`. Full design rationale and operational notes are in `experiment_v2.1/implementation_documentation.{docx,pdf}`. Deployment runs on [Cognition.run](https://www.cognition.run/) with recruitment via Prolific.

## Model arm — quick start

```bash
cd experiment_v2.1/model_arm
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# end-to-end synthetic test (no model weights loaded)
python smoke_test.py

# named sweep — see configs/ for available configurations
python run_pilot.py smoke_all_models
python run_pilot.py pilot_prompt_manipulation
```

A *sweep* is a (model × prompt-variant × story × condition × seed) grid. Each cell is a self-contained trial folder under `outputs/sweep_<...>/`, so individual cells can be re-run without disturbing the rest. The current model registry covers Qwen 2.5 (7B, 14B 4-bit, 32B 4-bit), Qwen 3 (8B, 14B 4-bit), Llama 3.1 8B, Mistral 7B (Hugging Face transformers and MLX 4-bit backends) plus GPT-4o and Claude Sonnet via API; full list in `model_arm/src/models.py`.

The second-order analysis (`model_arm/src/meta_rsa.py`) computes inter-story, inter-condition and meta RDMs from each cell's 8×8 pair-scaling matrix using a *1 − Spearman ρ over the 56 off-diagonal cells* distance. The same interface is the target for the hidden-state probing stage below.

## Planned: hidden-state probing (Stage 3)

The behavioural mirror already tells us *what* the model outputs differ on across conditions. The probing stage targets *where in the model the temporal/causal structure is encoded*, by reading internal activations as the model works through the same battery.

Working plan:

1. **Activation capture.** Forward-hook the residual stream of each open-weights model (Qwen 2.5 7B, Qwen 3 8B, Llama 3.1 8B, Mistral 7B; possibly Qwen 14B/32B via MLX) at every transformer layer. Capture the hidden state at fixed anchor positions: (a) the final token of each event sentence during story reading, (b) the final token of each task prompt, (c) the model's first generated token for each task. Save to disk per (model, story, condition, seed, layer).
2. **Event-level RDMs.** For each (model, condition, seed, layer), build an 8×8 event-by-event RDM from the cosine distance between the captured hidden-state vectors. This is the hidden-state analogue of the human/model 8×8 pair-scaling matrix.
3. **RSA against behaviour and ground truth.** Reuse the existing second-order RSA machinery in `meta_rsa.py` to compute three Spearman correlations per layer: hidden-state RDM vs (a) the model's own pair-scaling RDM, (b) the human pair-scaling RDM (where available), (c) an RDM derived from the gold-standard causal graph. The layer-by-layer correlation curve isolates *which depth* of the network represents which level of structure.
4. **Condition contrasts.** The headline contrast is the same as in the behavioural arm: does the linear → atemporal manipulation reshape internal representations, and at which layer is the shift largest? Each story acts as its own paired baseline.
5. **Linear probes (secondary).** For each model and layer, train a lightweight linear classifier on the captured states to predict (i) the canonical chronological position of the event, (ii) the existence of a causal edge between two named events. Probe accuracy by layer complements the RSA picture.

This stage will live in a new sibling folder, `experiment_v2.1/model_arm/probing/`, with its own `README.md`, configs, and outputs schema. It will reuse the same stimulus loader, sweep-folder convention, and RDM/RSA utilities as the behavioural arm, so analyses can stay in one place across the three stages.

## Licence

The participant experiment is built on [jsPsych](https://github.com/jspsych/jsPsych) (MIT). Third-party licences are reproduced in `Licensing/`.
