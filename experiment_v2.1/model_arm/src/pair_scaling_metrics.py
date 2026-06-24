"""
Compare model pair-scaling matrices to the author-intended causal graph.

Gold matrix encoding matches the headline / meta-analysis convention:
  - directed edge \"causes\"  → 6.0
  - other directed edge type → 4.5 (enables / contributes in stimuli)
  - no edge                  → 0

Metrics (off-diagonal ordered pairs only; diagonal ignored):
  - Pearson r, Spearman ρ  : association between model ratings and gold weights
  - Edge F1 at threshold k : binarize model as edge if rating >= k; gold edge if G > 0
  - Directional accuracy   : among unordered event pairs with exactly one gold edge,
      fraction where the model assigns the higher rating to that edge's direction
"""

from __future__ import annotations

import numpy as np
from scipy.stats import spearmanr

# Binarize predicted \"edge present\" for F1 (0–6 Likert scale).
DEFAULT_EDGE_THRESHOLD = 2

CAUSES_WEIGHT = 6.0
ENABLES_WEIGHT = 4.5


def author_intended_matrix(chrono_ids: list[str], gold: dict | None) -> np.ndarray:
    """Dense gold matrix G aligned with chronological event ids."""
    n = len(chrono_ids)
    G = np.zeros((n, n))
    if not gold:
        return G
    idx = {eid: i for i, eid in enumerate(chrono_ids)}
    for e in gold.get("causal_edges", []):
        if e["source"] in idx and e["target"] in idx:
            i, j = idx[e["source"]], idx[e["target"]]
            G[i, j] = CAUSES_WEIGHT if e.get("type") == "causes" else ENABLES_WEIGHT
    return G


def _model_matrix_float(matrix_entry: dict) -> np.ndarray:
    M = np.array(matrix_entry["matrix"], dtype=object)
    return np.where(M == None, np.nan, M).astype(float)  # noqa: E711


def pearson_offdiag(M: np.ndarray, G: np.ndarray) -> float:
    mask = ~np.eye(M.shape[0], dtype=bool)
    vm, vg = M[mask], G[mask]
    valid = np.isfinite(vm)
    if valid.sum() < 5:
        return float("nan")
    a, b = vm[valid], vg[valid]
    if np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def spearman_offdiag(M: np.ndarray, G: np.ndarray) -> float:
    mask = ~np.eye(M.shape[0], dtype=bool)
    vm, vg = M[mask], G[mask]
    valid = np.isfinite(vm)
    if valid.sum() < 5:
        return float("nan")
    rho, _ = spearmanr(vm[valid], vg[valid])
    return float(rho) if not np.isnan(rho) else float("nan")


def edge_detection_f1(M: np.ndarray, G: np.ndarray, threshold: int = DEFAULT_EDGE_THRESHOLD) -> dict:
    """Binary edge detection on off-diagonals; gold positive iff G > 0."""
    mask = ~np.eye(M.shape[0], dtype=bool)
    vm, vg = M[mask], G[mask]
    valid = np.isfinite(vm)
    vm = vm[valid]
    vg = vg[valid]
    gold_pos = vg > 0
    pred_pos = vm >= threshold
    tp = int(np.sum(gold_pos & pred_pos))
    fp = int(np.sum(~gold_pos & pred_pos))
    fn = int(np.sum(gold_pos & ~pred_pos))
    precision = tp / (tp + fp) if (tp + fp) > 0 else float("nan")
    recall = tp / (tp + fn) if (tp + fn) > 0 else float("nan")
    if np.isnan(precision) or np.isnan(recall):
        f1 = float("nan")
    elif precision + recall == 0:
        f1 = 0.0
    else:
        f1 = float(2 * precision * recall / (precision + recall))
    return {
        "edge_f1": f1,
        "edge_precision": float(precision) if not np.isnan(precision) else float("nan"),
        "edge_recall": float(recall) if not np.isnan(recall) else float("nan"),
        "edge_threshold": threshold,
        "edge_tp": tp,
        "edge_fp": fp,
        "edge_fn": fn,
    }


def directional_accuracy(M: np.ndarray, G: np.ndarray) -> float:
    """
    For each unordered pair of distinct events {i,j}, if exactly one of G[i,j], G[j,i]
    is positive, check whether the model assigns a strictly higher rating to that
    directed pair than to the reverse. Ties count as incorrect.
    """
    n = M.shape[0]
    correct = 0
    total = 0
    for i in range(n):
        for j in range(i + 1, n):
            m_ij, m_ji = M[i, j], M[j, i]
            if not np.isfinite(m_ij) or not np.isfinite(m_ji):
                continue
            g_ij, g_ji = G[i, j], G[j, i]
            pos_ij = g_ij > 0
            pos_ji = g_ji > 0
            if pos_ij and pos_ji:
                continue
            if not pos_ij and not pos_ji:
                continue
            total += 1
            if pos_ij:
                correct += int(m_ij > m_ji)
            else:
                correct += int(m_ji > m_ij)
    return correct / total if total > 0 else float("nan")


def offdiag_vectors(matrix_entry: dict, gold: dict | None) -> tuple[np.ndarray, np.ndarray]:
    """Off-diagonal aligned pairs (model rating, gold weight); excludes NaN model cells."""
    ids = matrix_entry["event_ids_chronological"]
    M = _model_matrix_float(matrix_entry)
    G = author_intended_matrix(ids, gold or {})
    mask = ~np.eye(M.shape[0], dtype=bool)
    vm, vg = M[mask], G[mask]
    valid = np.isfinite(vm)
    return vm[valid], vg[valid]


def compute_all(matrix_entry: dict, gold: dict | None, *,
                edge_threshold: int = DEFAULT_EDGE_THRESHOLD) -> dict:
    """All pair-scaling-vs-gold metrics for one story-run (serializable floats)."""
    ids = matrix_entry["event_ids_chronological"]
    M = _model_matrix_float(matrix_entry)
    G = author_intended_matrix(ids, gold or {})

    out = {
        "pearson_r_vs_gold": pearson_offdiag(M, G),
        "spearman_r_vs_gold": spearman_offdiag(M, G),
        "directional_accuracy": directional_accuracy(M, G),
    }
    out.update(edge_detection_f1(M, G, threshold=edge_threshold))
    return out
