# Participant Task Battery — jsPsych Implementation

This folder contains the complete implementation of the participant task battery for the temporal-scaffolding-and-causal-world-models dissertation experiment, plus supporting documentation.

For full design rationale and operational details, see **implementation_documentation.docx** (or .pdf). For the data schema produced by the experiment, see **DATA_SCHEMA.md**.

## Folder layout

```
experiment/
├── src/                              # JavaScript modules (the experiment logic)
│   ├── config.js                     # versions, task params, preregistered constants, feature flags
│   ├── main.js                       # timeline entry point — glues intro + per-story blocks + outro
│   ├── condition.js                  # between-subjects condition assignment
│   ├── selection.js                  # story selection from the 32-row preregistered table
│   ├── data.js                       # participant metadata + Prolific redirect helpers
│   ├── utils.js                      # URL params, timestamps, scroll/focus tracker, shuffle
│   ├── intro.js                      # browser check, welcome, consent, demographics, IMC, instructions
│   ├── inter_story.js                # between-story break + progress indicator
│   ├── outro.js                      # final comments, debrief, Prolific redirect
│   └── tasks/
│       ├── story_reading.js          # min-time threshold, activity tracking
│       ├── comprehension.js          # 6 items + summary row per story
│       ├── ordering.js               # SortableJS drag + confidence slider, single row + detail events
│       ├── pair_scaling.js           # 56 directed pairs + 8x8 matrix summary row per story
│       └── counterfactual.js         # 8 probes + anchor vector + discrimination index per story
│
├── stimuli/                          # Content (loaded as JS files setting globals — required by Cognition)
│   ├── stories.js                    # 8 stories × 3 versions (linear / nonlinear / atemporal)
│   ├── comprehension.js              # 48 comprehension items (6 per story × 8 stories)
│   ├── event_cards.js                # 64 short event labels (8 per story × 8 stories)
│   ├── cf_probes.js                  # 64 counterfactual probes (8 per story × 8 stories)
│   └── assignments.js                # 32-row preregistered counterbalancing table
│
├── assets/
│   └── style.css                     # presentation styles for all tasks
│
├── index.html                        # local browser test harness — NOT used on Cognition
├── smoke_test.js                     # Node sandbox verification of all globals and builders
├── synthetic_run.js                  # end-to-end simulated participant runner
├── DATA_SCHEMA.md                    # operational reference for analysis code
├── author_intended_graphs.json       # design-blueprint causal graphs (8 domains, schema 0.4.0)
├── implementation_documentation.docx # full design + audit + deployment doc (26 pages, Times New Roman 12pt)
└── implementation_documentation.pdf  # PDF render of the same
```

## Running locally

To eyeball the UX in a browser before deploying:

```bash
# from the experiment/ folder, start any static HTTP server, e.g.:
python3 -m http.server 8000
# then open http://localhost:8000/index.html
```

The page will show the full 313-trial timeline; if you want to skip to specific tasks during testing, set `CONFIG.debug.enabled = true` in `src/config.js` (or use the existing `force_condition` / `force_assignment_id` debug overrides).

## Verification (no browser required)

Two Node.js scripts confirm the build is well-formed without needing a browser:

```bash
node smoke_test.js       # sandbox-loads all files, verifies every global and builder
node synthetic_run.js    # end-to-end simulated participant; writes synthetic_output.json
```

Both complete in under 2 seconds. Run them after any change to `src/` or `stimuli/`.

## Before deployment

A short checklist (full version in §3.3 of the implementation documentation):

1. Replace the consent-text placeholders in `src/intro.js`: `[INSTITUTION]`, `[ETHICS_REF]`, `[RESEARCHER]`, `[EMAIL]`, `[SUPERVISOR]`, `[SUPERVISOR_EMAIL]`
2. Set `CONFIG.prolific.completion_url` in `src/config.js` to the study-specific Prolific completion URL
3. Confirm `CONFIG.debug.enabled = false` (it is, by default)
4. Upload `src/*.js` and `stimuli/*.js` files to the Cognition code editor in the order given in `index.html`
5. Configure Prolific to pass `PROLIFIC_PID`, `STUDY_ID`, `SESSION_ID` as URL parameters (the experiment reads these automatically)
6. For strict preregistered cycle control across participants, also pass `?pIndex=N` from Prolific orchestration so participants map onto the canonical 0..31 assignment cycle in order
