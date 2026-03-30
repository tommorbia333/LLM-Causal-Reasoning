"""
Prompt templates for incremental event graph construction.

Schema v0.2: Temporal information lives on event nodes (canonical_position
and time_to_next). Edges are causal only (causes / enables).
"""

GRAPH_SCHEMA_DESCRIPTION = """You are building an event graph from a narrative. The narrative may present events OUT OF chronological order. Your task is to reconstruct the TRUE CHRONOLOGICAL structure.

## Schema

The graph is a JSON object with two arrays: "events" and "edges".

Each event has:
- "id": string like "E1", "E2", etc. Assigned in the order you encounter them in the text.
- "description": a single sentence describing the core event (strip away filler detail).
- "canonical_position": the event's position in TRUE CHRONOLOGICAL order (integer, 1 = earliest in real time). This is NOT the order you read the events. You MUST renumber ALL events whenever a new event changes the chronological ordering.
- "time_to_next": the approximate time gap between this event and the next chronological event. One of "immediate" (minutes/same scene), "short" (hours/same day), "medium" (days), "long" (weeks or more), or null for the last event.

Each edge represents a CAUSAL relationship and has:
- "source": event id (the cause)
- "target": event id (the effect)
- "type": always "causal"
- "subtype": either "causes" (proximate trigger that directly produces the outcome) or "enables" (background condition that makes the outcome possible but doesn't directly trigger it)

## Example

Here is a small valid graph showing the exact format expected:

{"events": [{"id": "E1", "description": "A manager approved a new policy.", "canonical_position": 1, "time_to_next": "long"}, {"id": "E2", "description": "A technician changed a setting.", "canonical_position": 2, "time_to_next": null}], "edges": [{"source": "E1", "target": "E2", "type": "causal", "subtype": "enables"}]}

Note: there are NO temporal edges. Temporal information is encoded entirely on event nodes via canonical_position and time_to_next.

## Rules
- Only add causal edges you are confident about from the text so far.
- Do not add transitive causal links — only direct causal relationships.
- When placing a new event chronologically, renumber canonical_position for ALL events and update time_to_next values accordingly.
- Respond with ONLY the updated JSON graph. No commentary, no markdown fences."""


INITIALIZATION_PROMPT = """You are beginning to read a narrative. Here is the first segment:

---
{segment}
---

Create the initial event graph containing this first event. Assign canonical_position = 1 and time_to_next = null (since there is only one event so far). Respond with only the JSON graph."""


UPDATE_PROMPT = """Here is the current event graph built from the story so far:

{current_graph}

Here is the next segment of the narrative:

---
{segment}
---

Determine whether this segment introduces a new event. If it does, determine where it falls in the TRUE CHRONOLOGICAL order relative to all existing events. Pay close attention to temporal cues (e.g., "several weeks before," "later that night," "in the months that followed").

Then update the graph:
1. Add the new event with a new ID and the correct canonical_position.
2. Renumber canonical_position for ALL events to reflect the correct chronological sequence (1 = earliest).
3. Update time_to_next for ALL events — each event's time_to_next should reflect the gap to the next event in chronological order. The last chronological event gets time_to_next = null.
4. Add any causal edges you can identify.

Respond with only the updated JSON graph."""


RETRY_MISSING_EVENT_PROMPT = """Here is the current event graph:

{current_graph}

You just read the following segment, but the graph was not updated with a new event:

---
{segment}
---

Look again at this segment carefully. Does it describe an action or occurrence that is distinct from every event already in the graph? If so, add it as a new event node with a new ID. If you are certain it does not describe a new event, return the graph unchanged. Respond with only the JSON graph."""


REVISION_PROMPT = """You have finished reading the entire narrative. Here is the event graph you constructed incrementally:

{final_graph}

Review this graph carefully. Consider:
- Are the canonical_position values correct? Do they reflect the true chronological order?
- Are the time_to_next values accurate for each event?
- Are any causal edges missing? Should any existing causal edges be "causes" instead of "enables", or vice versa?
- Are there any spurious edges that should be removed?

If changes are needed, output the revised graph. If no changes are needed, output the graph unchanged. Respond with only the JSON graph."""


def build_system_prompt():
    """Returns the system prompt that defines the graph schema."""
    return GRAPH_SCHEMA_DESCRIPTION


def build_init_prompt(segment: str) -> str:
    """Build the prompt for the first segment."""
    return INITIALIZATION_PROMPT.format(segment=segment)


def build_update_prompt(current_graph: str, segment: str) -> str:
    """Build the prompt for subsequent segments."""
    return UPDATE_PROMPT.format(current_graph=current_graph, segment=segment)


def build_retry_prompt(current_graph: str, segment: str) -> str:
    """Build the retry prompt when the model didn't add a new event."""
    return RETRY_MISSING_EVENT_PROMPT.format(current_graph=current_graph, segment=segment)


def build_revision_prompt(final_graph: str) -> str:
    """Build the prompt for the post-construction revision step."""
    return REVISION_PROMPT.format(final_graph=final_graph)
