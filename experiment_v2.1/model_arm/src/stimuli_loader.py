"""
Stimuli loader for the model behavioural arm.

Reads `stimuli.json` (the JSON port of the jsPsych .js stimulus files)
and exposes typed accessors. Single source of truth for the model side;
keep in sync with the JS side via the port script when stimuli change.

Story IDs in this dataset (8 domains):
    hospital_incident, care_home_incident, community_fair, restaurant_fire,
    school_trip, family_conflict, power_cut, missed_flight

Conditions: linear, nonlinear, atemporal
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class Event:
    id: str          # "E1" ... "E8"
    text: str        # full paragraph as presented
    card: str        # short label for ordering task
    canonical_position: int  # 1..8, the chronological order


@dataclass(frozen=True)
class Story:
    story_id: str            # e.g. "hospital_incident"
    condition: str           # "linear" | "nonlinear" | "atemporal"
    title: str
    topology: str
    events: list[Event]      # in PRESENTATION order (matches what the participant reads)
    full_text: str           # concatenation of event texts with double newlines

    @property
    def events_chronological(self) -> list[Event]:
        return sorted(self.events, key=lambda e: e.canonical_position)


@dataclass(frozen=True)
class ComprehensionItem:
    id: str
    text: str
    correct: str             # "Yes" | "No" | "Unsure"
    role: str                # "compound" | "single" | "negative_recall" | "distractor"
    events: list[str]        # event IDs the item references


@dataclass(frozen=True)
class CFProbe:
    id: str                  # probe_id, e.g. "hospital_incident_anchor_E1"
    role: str                # "anchor" | "sibling_null" | "reverse_null"
    antecedent: str          # event id (the "if X had not occurred" event)
    consequent: str          # event id (the "would Y still have happened" event)
    text: str                # full probe prompt as presented


class StimulusBundle:
    """Holds the full stimulus set; query by (story_id, condition)."""

    def __init__(self, stimuli_path: Path):
        with open(stimuli_path, "r") as f:
            self._raw = json.load(f)
        self._stories = self._raw["stories"]
        self._cards = self._raw["event_cards"]
        self._comp = self._raw["comprehension"]["stories"]
        self._cf = self._raw.get("cf_probes", {}).get("stories", {})
        self._graphs = self._raw["author_intended_graphs"]
        self.response_options_comp = self._raw["comprehension"]["response_options"]

    @property
    def story_ids(self) -> list[str]:
        return list(self._stories.keys())

    @property
    def conditions(self) -> list[str]:
        return ["linear", "nonlinear", "atemporal"]

    def get_story(self, story_id: str, condition: str) -> Story:
        s = self._stories[story_id]
        v = s["versions"][condition]
        cards = self._cards[story_id]
        # Canonical positions come from the gold graph if available; otherwise
        # parse the event id "E<n>" as the chronological position.
        graph_events = (
            self._graphs.get(story_id, {}).get("events") if story_id in self._graphs else None
        )
        canonical = (
            {e["id"]: e["canonical_position"] for e in graph_events}
            if graph_events
            else {f"E{i}": i for i in range(1, 9)}
        )
        events = [
            Event(
                id=ev["id"],
                text=ev["text"],
                card=cards[ev["id"]],
                canonical_position=canonical[ev["id"]],
            )
            for ev in v["events"]
        ]
        full_text = "\n\n".join(ev.text for ev in events)
        return Story(
            story_id=story_id,
            condition=condition,
            title=s["title"],
            topology=s["topology"],
            events=events,
            full_text=full_text,
        )

    def get_comprehension_items(self, story_id: str) -> list[ComprehensionItem]:
        items = self._comp[story_id]["items"]
        return [
            ComprehensionItem(
                id=it["id"],
                text=it["text"],
                correct=it["correct"],
                role=it["role"],
                events=it["events"],
            )
            for it in items
        ]

    def get_cf_probes(self, story_id: str) -> list[CFProbe]:
        if story_id not in self._cf:
            return []
        probes = self._cf[story_id]["probes"]
        return [
            CFProbe(
                id=p["probe_id"],
                role=p["role"],
                antecedent=p["antecedent_event_id"],
                consequent=p["consequent_event_id"],
                text=p["prompt"],
            )
            for p in probes
        ]

    def get_author_intended_graph(self, story_id: str) -> dict | None:
        return self._graphs.get(story_id)

    def iter_pilot(self, story_ids: list[str], conditions: list[str]) -> Iterator[Story]:
        for sid in story_ids:
            for cond in conditions:
                yield self.get_story(sid, cond)


def load(path: Path | str = None) -> StimulusBundle:
    if path is None:
        # stimuli_loader.py lives in src/, stimuli.json lives in ../stimuli/
        path = Path(__file__).resolve().parent.parent / "stimuli" / "stimuli.json"
    return StimulusBundle(Path(path))
