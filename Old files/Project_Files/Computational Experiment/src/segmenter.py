"""
Story segmenter: splits narratives into segments for incremental processing.

Each segment should contain exactly one core event plus any surrounding
filler text (for fluff variants). The segmentation is defined manually
per story variant to ensure consistency.
"""

import json
from pathlib import Path
from typing import Optional


# Manual segmentation boundaries for each story variant.
# Each entry maps a story_id to a list of segments (strings).
# For the prototype, we define these explicitly rather than trying
# to auto-segment, because the boundaries matter for the experiment.

STORY_SEGMENTS: dict[str, list[str]] = {

    # === MEDICAL SHORT LINEAR ===
    "medical_short_linear": [
        "Several weeks before the incident, a hospital administrator approved a policy to reduce overnight staffing levels on the ward.",
        "On a later day, a maintenance contractor disabled a ventilator alarm while performing a routine test.",
        "After completing the test, the contractor left the room without re-enabling the alarm.",
        "On the night of the incident, a nurse was assigned more patients than usual.",
        "Later that night, a brief interruption in power occurred on the ward.",
        "Following the power interruption, the ventilator stopped operating without sounding an alarm.",
        "Some time later, the nurse entered the room and found a patient experiencing respiratory distress.",
        "In the months that followed, an inquest reviewed the sequence of events.",
    ],

    # === MEDICAL SHORT NONLINEAR ===
    "medical_short_nonlinear": [
        "In the months that followed, an inquest reviewed the sequence of events.",
        "Some time earlier, the nurse entered the room and found a patient experiencing respiratory distress.",
        "Later that night, the ventilator stopped operating without sounding an alarm.",
        "Several weeks before the incident, a hospital administrator approved a policy to reduce overnight staffing levels on the ward.",
        "On the night of the incident, a nurse was assigned more patients than usual.",
        "On a later day, a maintenance contractor disabled a ventilator alarm while performing a routine test.",
        "After completing the test, the contractor left the room without re-enabling the alarm.",
        "Earlier that same night, a brief interruption in power occurred on the ward.",
    ],

    # === WORKPLACE SHORT LINEAR ===
    "workplace_short_linear": [
        "Several months before the outage, a manager approved a plan to consolidate server resources.",
        "On a later date, a technician updated configuration settings on a backup system.",
        "After finishing the update, the technician did not restart one of the services.",
        "On the morning of the incident, an analyst began processing a large dataset.",
        "Shortly afterward, system load increased across the network.",
        "As load increased, a critical service stopped responding.",
        "Later that morning, users reported being unable to access shared files.",
        "In the weeks that followed, an internal review examined the incident.",
    ],

    # === WORKPLACE SHORT NONLINEAR ===
    "workplace_short_nonlinear": [
        "Later that morning, users reported being unable to access shared files.",
        "Several months before the outage, a manager approved a plan to consolidate server resources.",
        "In the weeks that followed, an internal review examined the incident.",
        "As load increased, a critical service stopped responding.",
        "On a later date, a technician updated configuration settings on a backup system.",
        "On the morning of the incident, an analyst began processing a large dataset.",
        "After finishing the update, the technician did not restart one of the services.",
        "Shortly afterward, system load increased across the network.",
    ],

    # === COASTAL HEAVY FLUFF LINEAR ===
    "coastal_heavy_linear": [
        "The coastal road ran alongside a low seawall, with a pedestrian path on the inland side and a line of salt-tolerant shrubs planted at regular intervals. A small electronic signboard near the bus stop displayed service changes when construction work was active.\nThe city council approved a pilot floodgate project for the coastal road. In the weeks after the approval, a short project bulletin appeared on the city website and was reposted on a community noticeboard near a cafe. People who used the road daily often noticed the same set of blue directional arrows on temporary signs when routes changed.",
        "Contractors installed temporary barriers and signage near the road. The barriers created a narrower corridor for vehicles, and pedestrians were guided to a marked crossing point that remained in the same place throughout the works. At different times of day, the area alternated between quiet stretches and brief clusters of activity around the crossing.",
        "A utilities team scheduled a routine inspection of a pump station. The pump station sat behind a locked metal gate, and the access path to it was usually empty except for maintenance visits. The inspection date was listed on an internal work calendar, separate from the construction timetable.",
        "The inspection required a temporary shutdown of the pump station. A short entry noting the shutdown window was added to a maintenance log, and the pump station status indicator was set to 'offline' during that period. The nearby electronic signboard continued to cycle through the same rotating messages.",
        "A weather service issued a coastal surge warning. The warning appeared as a standard alert format on multiple apps, and local radio repeated the same headline at set intervals. People who checked the tide chart often looked first at the same reference point: the predicted peak time.",
        "The floodgate was activated during the warning period. A work crew followed a checklist, and the activation was recorded with a timestamp in a routine operations form. The temporary barriers and the blue-arrow signs remained in place, unchanged from earlier in the week.",
        "Water entered the road area and traffic was halted. Drivers were redirected to an inland route, and buses skipped the coastal stop while the closure remained active. After the detour, some pedestrians returned to the same cafe noticeboard, where the latest printed update had been taped over an older sheet.",
        "A municipal review later examined the sequence of events. The review compiled logs from multiple teams and summarized them as a timeline, using the surge warning time as a reference point. In follow-up meetings, the same map of the coastal road was projected repeatedly, with the floodgate location marked in a single highlighted box.",
    ],

    # === COASTAL HEAVY FLUFF NONLINEAR ===
    "coastal_heavy_nonlinear": [
        "The coastal road ran alongside a low seawall, with a pedestrian path on the inland side and a line of salt-tolerant shrubs planted at regular intervals. A small electronic signboard near the bus stop displayed service changes when construction work was active.\nA municipal review later examined the sequence of events. The review compiled logs from multiple teams and summarized them as a timeline, using the surge warning time as a reference point. In follow-up meetings, the same map of the coastal road was projected repeatedly, with the floodgate location marked in a single highlighted box.",
        "Water entered the road area and traffic was halted. Drivers were redirected to an inland route, and buses skipped the coastal stop while the closure remained active. After the detour, some pedestrians returned to the same cafe noticeboard, where the latest printed update had been taped over an older sheet.",
        "The city council approved a pilot floodgate project for the coastal road. In the weeks after the approval, a short project bulletin appeared on the city website and was reposted on a community noticeboard near a cafe. People who used the road daily often noticed the same set of blue directional arrows on temporary signs when routes changed.",
        "A weather service issued a coastal surge warning. The warning appeared as a standard alert format on multiple apps, and local radio repeated the same headline at set intervals. People who checked the tide chart often looked first at the same reference point: the predicted peak time.",
        "Contractors installed temporary barriers and signage near the road. The barriers created a narrower corridor for vehicles, and pedestrians were guided to a marked crossing point that remained in the same place throughout the works. At different times of day, the area alternated between quiet stretches and brief clusters of activity around the crossing.",
        "The inspection required a temporary shutdown of the pump station. A short entry noting the shutdown window was added to a maintenance log, and the pump station status indicator was set to 'offline' during that period. The nearby electronic signboard continued to cycle through the same rotating messages.",
        "A utilities team scheduled a routine inspection of a pump station. The pump station sat behind a locked metal gate, and the access path to it was usually empty except for maintenance visits. The inspection date was listed on an internal work calendar, separate from the construction timetable.",
        "The floodgate was activated during the warning period. A work crew followed a checklist, and the activation was recorded with a timestamp in a routine operations form. The temporary barriers and the blue-arrow signs remained in place, unchanged from earlier in the week.",
    ],
}

# Narrative position mappings: which canonical event does each segment contain?
# This is needed to track what the model *should* extract at each step.
SEGMENT_EVENT_MAP: dict[str, list[str]] = {
    "medical_short_linear":     ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8"],
    "medical_short_nonlinear":  ["E8", "E7", "E6", "E1", "E4", "E2", "E3", "E5"],
    "workplace_short_linear":   ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8"],
    "workplace_short_nonlinear":["E7", "E1", "E8", "E6", "E2", "E4", "E3", "E5"],
    "coastal_heavy_linear":     ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8"],
    "coastal_heavy_nonlinear":  ["E8", "E7", "E1", "E5", "E2", "E4", "E3", "E6"],
}


def get_segments(story_id: str) -> list[str]:
    """Return the ordered list of text segments for a story variant."""
    if story_id not in STORY_SEGMENTS:
        available = ", ".join(sorted(STORY_SEGMENTS.keys()))
        raise ValueError(f"Unknown story_id '{story_id}'. Available: {available}")
    return STORY_SEGMENTS[story_id]


def get_event_map(story_id: str) -> list[str]:
    """Return the expected canonical event id for each segment position."""
    if story_id not in SEGMENT_EVENT_MAP:
        raise ValueError(f"No event map for story_id '{story_id}'.")
    return SEGMENT_EVENT_MAP[story_id]


def list_stories() -> list[str]:
    """Return all available story variant ids."""
    return sorted(STORY_SEGMENTS.keys())
