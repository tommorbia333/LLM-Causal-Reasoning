"""
Evaluation: compare model-generated graphs against gold standard.

Schema v0.2: Temporal info on nodes, causal-only edges.

IMPORTANT: Event IDs are NOT assumed to match between model and gold.
Events are matched by description similarity, then all metrics are
computed through the resulting mapping.

Metrics:
- Event matching quality (how well descriptions align)
- Causal edge precision / recall / F1 (strict and relaxed)
- Canonical ordering accuracy (exact match, pairwise)
- Temporal label accuracy (time_to_next per node)
"""

import json
import re
from typing import Any
from pathlib import Path


def load_gold_standard(path: str = "data/gold_standard_graphs.json") -> dict:
    """Load the gold standard graphs."""
    with open(path) as f:
        data = json.load(f)
    return data["domains"]


# --- Description matching ---

def _tokenize(text: str) -> set[str]:
    """Simple whitespace + punctuation tokenizer, lowercased."""
    return set(re.findall(r'[a-z0-9]+', text.lower()))


def _jaccard(a: set, b: set) -> float:
    """Jaccard similarity between two token sets."""
    if not a and not b:
        return 1.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union) if union else 0.0


def match_events(model_graph: dict, gold_graph: dict) -> dict:
    """
    Match model events to gold events by description similarity.

    Uses greedy best-match: for each model event, find the most similar
    unmatched gold event. Events with Jaccard similarity < 0.2 are
    left unmatched.

    Returns:
        {
            "mapping": {model_id: gold_id, ...},
            "unmatched_model": [model_ids not matched to any gold],
            "unmatched_gold": [gold_ids not matched to any model],
            "match_scores": {model_id: {"gold_id": ..., "similarity": ...}, ...},
        }
    """
    model_events = model_graph.get("events", [])
    gold_events = gold_graph.get("events", [])

    # Precompute token sets
    model_tokens = {ev["id"]: _tokenize(ev.get("description", "")) for ev in model_events}
    gold_tokens = {ev["id"]: _tokenize(ev.get("description", "")) for ev in gold_events}

    # Compute all pairwise similarities
    similarities = []
    for m_id, m_tok in model_tokens.items():
        for g_id, g_tok in gold_tokens.items():
            sim = _jaccard(m_tok, g_tok)
            similarities.append((sim, m_id, g_id))

    # Greedy best-match (highest similarity first)
    similarities.sort(reverse=True)
    mapping = {}
    match_scores = {}
    used_gold = set()
    used_model = set()

    for sim, m_id, g_id in similarities:
        if m_id in used_model or g_id in used_gold:
            continue
        if sim < 0.2:
            continue
        mapping[m_id] = g_id
        match_scores[m_id] = {"gold_id": g_id, "similarity": round(sim, 3)}
        used_model.add(m_id)
        used_gold.add(g_id)

    unmatched_model = [ev["id"] for ev in model_events if ev["id"] not in used_model]
    unmatched_gold = [ev["id"] for ev in gold_events if ev["id"] not in used_gold]

    return {
        "mapping": mapping,
        "unmatched_model": unmatched_model,
        "unmatched_gold": unmatched_gold,
        "match_scores": match_scores,
    }


# --- Causal edge agreement ---

def causal_edge_agreement(model_graph: dict, gold_graph: dict, mapping: dict) -> dict:
    """
    Compute causal edge agreement after remapping model IDs to gold IDs.

    Strict: source, target, and subtype must all match.
    Relaxed: source and target match (ignores causes vs enables).
    """
    model_edges = [e for e in model_graph.get("edges", []) if e.get("type") == "causal"]
    gold_edges = [e for e in gold_graph.get("edges", []) if e.get("type") == "causal"]

    # Remap model edges to gold ID space
    def remap_strict(edge):
        src = mapping.get(edge["source"])
        tgt = mapping.get(edge["target"])
        if src is None or tgt is None:
            return None
        return (src, tgt, edge.get("subtype"))

    def remap_relaxed(edge):
        src = mapping.get(edge["source"])
        tgt = mapping.get(edge["target"])
        if src is None or tgt is None:
            return None
        return (src, tgt)

    def gold_strict(edge):
        return (edge["source"], edge["target"], edge.get("subtype"))

    def gold_relaxed(edge):
        return (edge["source"], edge["target"])

    # Build key sets, dropping edges that couldn't be remapped
    model_strict = {k for k in (remap_strict(e) for e in model_edges) if k is not None}
    model_relaxed = {k for k in (remap_relaxed(e) for e in model_edges) if k is not None}
    gold_strict_set = {gold_strict(e) for e in gold_edges}
    gold_relaxed_set = {gold_relaxed(e) for e in gold_edges}

    # Count model edges that couldn't be remapped
    n_unmappable = sum(1 for e in model_edges if remap_strict(e) is None)

    return {
        "strict": _compute_agreement(model_strict, gold_strict_set),
        "relaxed": _compute_agreement(model_relaxed, gold_relaxed_set),
        "unmappable_model_edges": n_unmappable,
    }


def _compute_agreement(model_keys: set, gold_keys: set) -> dict:
    """Precision, recall, F1 from two sets of keys."""
    tp = model_keys & gold_keys
    fp = model_keys - gold_keys
    fn = gold_keys - model_keys

    precision = len(tp) / len(model_keys) if model_keys else 0
    recall = len(tp) / len(gold_keys) if gold_keys else 0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "true_positives": len(tp),
        "false_positives": len(fp),
        "false_negatives": len(fn),
        "tp_edges": sorted(tp),
        "fp_edges": sorted(fp),
        "fn_edges": sorted(fn),
    }


# --- Canonical ordering ---

def canonical_order_accuracy(model_graph: dict, gold_graph: dict, mapping: dict) -> dict:
    """
    Compare canonical_position assignments after remapping.
    """
    gold_positions = {
        ev["id"]: ev["canonical_position"]
        for ev in gold_graph.get("events", [])
    }
    model_positions = {}
    for ev in model_graph.get("events", []):
        gold_id = mapping.get(ev["id"])
        if gold_id is not None:
            model_positions[gold_id] = ev["canonical_position"]

    common_ids = set(gold_positions.keys()) & set(model_positions.keys())
    if not common_ids:
        return {"exact_match": 0, "pairwise_accuracy": 0, "n_events": 0}

    # Exact match
    exact = sum(
        1 for eid in common_ids
        if gold_positions[eid] == model_positions[eid]
    )

    # Pairwise ordering accuracy
    ids = sorted(common_ids)
    correct_pairs = 0
    total_pairs = 0
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            gold_order = gold_positions[a] < gold_positions[b]
            model_order = model_positions[a] < model_positions[b]
            if gold_order == model_order:
                correct_pairs += 1
            total_pairs += 1

    return {
        "exact_match": round(exact / len(common_ids), 3),
        "pairwise_accuracy": round(correct_pairs / total_pairs, 3) if total_pairs > 0 else 0,
        "n_events": len(common_ids),
        "n_exact": exact,
    }


# --- Temporal label accuracy ---

def temporal_label_accuracy(model_graph: dict, gold_graph: dict, mapping: dict) -> dict:
    """
    Compare time_to_next labels after remapping model events to gold IDs.
    """
    gold_labels = {
        ev["id"]: ev.get("time_to_next")
        for ev in gold_graph.get("events", [])
    }
    model_labels = {}
    for ev in model_graph.get("events", []):
        gold_id = mapping.get(ev["id"])
        if gold_id is not None:
            model_labels[gold_id] = ev.get("time_to_next")

    common_ids = set(gold_labels.keys()) & set(model_labels.keys())
    if not common_ids:
        return {"accuracy": 0, "n_events": 0, "details": {}}

    correct = 0
    details = {}
    for eid in sorted(common_ids):
        gold_val = gold_labels[eid]
        model_val = model_labels[eid]
        match = gold_val == model_val
        if match:
            correct += 1
        details[eid] = {
            "gold": gold_val,
            "model": model_val,
            "match": match,
        }

    return {
        "accuracy": round(correct / len(common_ids), 3),
        "n_correct": correct,
        "n_events": len(common_ids),
        "details": details,
    }


# --- Full evaluation ---

def full_evaluation(model_graph: dict, gold_graph: dict) -> dict:
    """Run all evaluation metrics and return a summary."""
    # First: match events by description
    event_match = match_events(model_graph, gold_graph)
    mapping = event_match["mapping"]

    return {
        "event_matching": event_match,
        "causal_edges": causal_edge_agreement(model_graph, gold_graph, mapping),
        "ordering": canonical_order_accuracy(model_graph, gold_graph, mapping),
        "temporal_labels": temporal_label_accuracy(model_graph, gold_graph, mapping),
        "model_event_count": len(model_graph.get("events", [])),
        "gold_event_count": len(gold_graph.get("events", [])),
        "model_edge_count": len(model_graph.get("edges", [])),
        "gold_edge_count": len(gold_graph.get("edges", [])),
    }


def print_evaluation(results: dict, label: str = "") -> None:
    """Pretty-print evaluation results."""
    if label:
        print(f"\n{'=' * 50}")
        print(f"  {label}")
        print(f"{'=' * 50}")

    print(f"\n  Events: {results['model_event_count']} model / {results['gold_event_count']} gold")
    print(f"  Causal edges: {results['model_edge_count']} model / {results['gold_edge_count']} gold")

    # Event matching
    em = results["event_matching"]
    print(f"\n  Event matching (by description):")
    for m_id, info in em["match_scores"].items():
        print(f"    model {m_id} → gold {info['gold_id']}  (similarity: {info['similarity']:.3f})")
    if em["unmatched_model"]:
        print(f"    Unmatched model events: {em['unmatched_model']}")
    if em["unmatched_gold"]:
        print(f"    Unmatched gold events:  {em['unmatched_gold']}")

    # Ordering
    ordering = results["ordering"]
    print(f"\n  Chronological ordering ({ordering['n_events']} matched events):")
    print(f"    Exact position match: {ordering['exact_match']:.1%} ({ordering['n_exact']}/{ordering['n_events']})")
    print(f"    Pairwise accuracy:    {ordering['pairwise_accuracy']:.1%}")

    # Temporal labels
    temporal = results["temporal_labels"]
    print(f"\n  Temporal labels (time_to_next):")
    print(f"    Accuracy: {temporal['accuracy']:.1%} ({temporal['n_correct']}/{temporal['n_events']})")
    for eid, detail in temporal["details"].items():
        marker = "✓" if detail["match"] else "✗"
        print(f"    {marker} gold {eid}: gold={detail['gold']}, model={detail['model']}")

    # Causal edges
    ce = results["causal_edges"]
    if ce["unmappable_model_edges"] > 0:
        print(f"\n  Note: {ce['unmappable_model_edges']} model edge(s) could not be evaluated (referenced unmatched events)")
    for mode in ["relaxed", "strict"]:
        data = ce[mode]
        print(f"\n  Causal edges ({mode}):")
        print(f"    Precision: {data['precision']:.3f}  Recall: {data['recall']:.3f}  F1: {data['f1']:.3f}")
        if data["fp_edges"]:
            print(f"    False positives: {data['fp_edges']}")
        if data["fn_edges"]:
            print(f"    False negatives: {data['fn_edges']}")
