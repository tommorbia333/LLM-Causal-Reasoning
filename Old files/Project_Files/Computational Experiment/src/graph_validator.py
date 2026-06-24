"""
Graph validator: ensures model-generated graphs conform to the v0.2 schema.

Schema v0.2: Temporal info on nodes (canonical_position, time_to_next).
Edges are causal only (causes / enables).
"""

from typing import Any


VALID_DISTANCES = {"immediate", "short", "medium", "long"}
VALID_SUBTYPES = {"causes", "enables"}


def validate_graph(graph: dict[str, Any]) -> list[str]:
    """
    Validate a graph against the v0.2 schema.

    Returns a list of issue strings. Empty list = valid graph.
    """
    issues = []

    if not isinstance(graph, dict):
        return ["Root object is not a dict."]

    # --- Events ---
    if "events" not in graph:
        issues.append("Missing 'events' array.")
    elif not isinstance(graph["events"], list):
        issues.append("'events' is not an array.")
    else:
        event_ids = set()
        for i, ev in enumerate(graph["events"]):
            prefix = f"events[{i}]"
            if not isinstance(ev, dict):
                issues.append(f"{prefix}: not a dict.")
                continue

            # Required fields
            for field in ["id", "description", "canonical_position"]:
                if field not in ev:
                    issues.append(f"{prefix}: missing '{field}'.")

            if "id" in ev:
                if not isinstance(ev["id"], str):
                    issues.append(f"{prefix}: 'id' must be a string.")
                elif ev["id"] in event_ids:
                    issues.append(f"{prefix}: duplicate id '{ev['id']}'.")
                else:
                    event_ids.add(ev["id"])

            if "canonical_position" in ev:
                if not isinstance(ev["canonical_position"], (int, float)):
                    issues.append(f"{prefix}: 'canonical_position' must be a number.")

            if "description" in ev:
                if not isinstance(ev["description"], str):
                    issues.append(f"{prefix}: 'description' must be a string.")

            # time_to_next: must be a valid distance or null/missing (for last event)
            if "time_to_next" in ev and ev["time_to_next"] is not None:
                if ev["time_to_next"] not in VALID_DISTANCES:
                    issues.append(f"{prefix}: invalid 'time_to_next' (got '{ev['time_to_next']}').")

    # --- Edges (causal only) ---
    if "edges" not in graph:
        issues.append("Missing 'edges' array.")
    elif not isinstance(graph["edges"], list):
        issues.append("'edges' is not an array.")
    else:
        event_ids = {ev["id"] for ev in graph.get("events", []) if "id" in ev}

        for i, edge in enumerate(graph["edges"]):
            prefix = f"edges[{i}]"
            if not isinstance(edge, dict):
                issues.append(f"{prefix}: not a dict.")
                continue

            # Required fields
            for field in ["source", "target", "type"]:
                if field not in edge:
                    issues.append(f"{prefix}: missing '{field}'.")

            # Validate source/target reference existing events
            if "source" in edge and edge["source"] not in event_ids:
                issues.append(f"{prefix}: source '{edge['source']}' not in events.")
            if "target" in edge and edge["target"] not in event_ids:
                issues.append(f"{prefix}: target '{edge['target']}' not in events.")

            # Self-loops
            if edge.get("source") == edge.get("target"):
                issues.append(f"{prefix}: self-loop ({edge.get('source')}).")

            # Type validation — only causal edges expected
            etype = edge.get("type")
            if etype == "causal":
                sub = edge.get("subtype")
                if sub not in VALID_SUBTYPES:
                    issues.append(f"{prefix}: causal edge missing/invalid 'subtype' (got '{sub}').")
            elif etype == "temporal":
                # Model included a temporal edge — flag but don't reject the whole graph
                issues.append(f"{prefix}: unexpected temporal edge (temporal info should be on nodes).")
            else:
                issues.append(f"{prefix}: invalid type '{etype}'.")

    return issues


def is_valid(graph: dict[str, Any]) -> bool:
    """Quick check: is the graph schema-valid?"""
    return len(validate_graph(graph)) == 0


def repair_common_issues(graph: dict[str, Any]) -> dict[str, Any]:
    """
    Attempt to fix common model output issues:
    - Convert canonical_position strings to ints
    - Normalize time_to_next / subtype casing
    - Remove edges referencing nonexistent events
    - Strip temporal edges (model should not produce them, but might)

    Returns a new (possibly repaired) graph dict.
    """
    import copy
    g = copy.deepcopy(graph)

    repairs_log = []

    # Fix event fields
    event_ids = set()
    for ev in g.get("events", []):
        if "canonical_position" in ev:
            try:
                ev["canonical_position"] = int(ev["canonical_position"])
            except (ValueError, TypeError):
                pass
        if "time_to_next" in ev and ev["time_to_next"] is not None:
            ev["time_to_next"] = str(ev["time_to_next"]).lower().strip()
        if "id" in ev:
            event_ids.add(ev["id"])

    # Fix edge fields
    valid_edges = []
    for i, edge in enumerate(g.get("edges", [])):
        # Skip edges referencing missing events
        if edge.get("source") not in event_ids or edge.get("target") not in event_ids:
            repairs_log.append(f"edges[{i}]: removed (references nonexistent event)")
            continue
        # Normalize casing
        if "subtype" in edge:
            edge["subtype"] = str(edge["subtype"]).lower().strip()
        if "type" in edge:
            edge["type"] = str(edge["type"]).lower().strip()

        # Strip temporal edges — model shouldn't produce them in v0.2
        if edge.get("type") == "temporal":
            repairs_log.append(f"edges[{i}]: removed temporal edge {edge.get('source')} -> {edge.get('target')}")
            continue

        valid_edges.append(edge)

    g["edges"] = valid_edges
    g["_repairs"] = repairs_log
    return g
