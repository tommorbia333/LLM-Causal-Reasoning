"""
Smoke test: exercise the full behavioural pipeline using MockConversation
(no real model), so the plumbing and figures can be validated cheaply.

Outputs go to outputs/trial_*_smoke/.

The mock model produces plausible answers and is condition-aware (linear
cleanest, atemporal noisiest), so the figures show the *kind* of structure
real Qwen output will have — not the actual results.
"""

from __future__ import annotations

from src import stimuli_loader
from src.runner import TrialSpec, run_trial
from src.model import MockConversation


def main():
    stimuli = stimuli_loader.load()

    spec = TrialSpec(
        model_id="MockModel/smoke",
        story_ids=["hospital_incident", "school_trip"],
        conditions=["linear", "nonlinear", "atemporal"],
        seeds=[0, 1, 2],
        run_id="smoke",
    )

    def factory(story, seed):
        gold = stimuli.get_author_intended_graph(story.story_id)
        return MockConversation(story=story, gold_graph=gold, seed=seed)

    trial_dir = run_trial(spec, stimuli, factory)
    print(f"\nSmoke-test trial: {trial_dir}")


if __name__ == "__main__":
    main()
