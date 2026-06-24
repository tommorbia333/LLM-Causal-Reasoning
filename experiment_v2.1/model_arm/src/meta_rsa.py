"""
Second-order RSA / dissimilarity analyses across pair-scaling matrices.

Each story-run produces an 8x8 asymmetric pair-scaling matrix (directed causal
ratings between event pairs). This module computes pairwise dissimilarities
between matrices to answer:

  - How different is the geometry across stories within a condition?
    (inter_story_rdms)
  - How much does temporal presentation distort the geometry within a story?
    (inter_condition_rdms)
  - Where do all (story, condition, seed) runs sit relative to each other?
    (compute_meta_rdm)
  - How reliable is the model across seeds for the same (story, condition)?
    (reliability_summary)

Distance metric: 1 - Spearman ρ between the 56 off-diagonal cells of the two
matrices. Robust to scale differences across runs; standard second-order RSA
distance. Same interface will work later on hidden-state RDMs (Stage 3).
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr


# -----------------------------------------------------------------------------
# Core: matrix → vector → distance
# -----------------------------------------------------------------------------

def _matrix_to_vec(matrix) -> np.ndarray:
    """Flatten an 8x8 asymmetric matrix to its 56 off-diagonal cells as a vector."""
    arr = np.array(matrix, dtype=object)  # object so we can detect None
    arr = np.where(arr == None, np.nan, arr).astype(float)  # noqa: E711
    n = arr.shape[0]
    mask = ~np.eye(n, dtype=bool)
    return arr[mask]


def _spearman_distance(v1: np.ndarray, v2: np.ndarray) -> float:
    """1 - Spearman ρ, NaN-safe. Returns nan if too few valid pairs."""
    valid = ~(np.isnan(v1) | np.isnan(v2))
    if valid.sum() < 5:
        return float("nan")
    rho, _ = spearmanr(v1[valid], v2[valid])
    if np.isnan(rho):
        return float("nan")
    return 1.0 - float(rho)


def _aggregate_vecs(matrices, predicate) -> np.ndarray | None:
    """Mean of matrix vectors satisfying predicate(matrix_dict). None if empty."""
    sel = [m for m in matrices if predicate(m)]
    if not sel:
        return None
    arr = np.stack([_matrix_to_vec(m["matrix"]) for m in sel])
    return np.nanmean(arr, axis=0)


# -----------------------------------------------------------------------------
# Three views
# -----------------------------------------------------------------------------

def compute_meta_rdm(matrices: list[dict]) -> tuple[np.ndarray, list[tuple]]:
    """Full (n_runs × n_runs) meta-RDM. labels = list of (story, condition, seed)."""
    n = len(matrices)
    vecs = [_matrix_to_vec(m["matrix"]) for m in matrices]
    labels = [(m["story_id"], m["condition"], m["seed"]) for m in matrices]

    rdm = np.full((n, n), np.nan)
    for i in range(n):
        rdm[i, i] = 0.0
        for j in range(i + 1, n):
            d = _spearman_distance(vecs[i], vecs[j])
            rdm[i, j] = d
            rdm[j, i] = d
    return rdm, labels


def inter_story_rdms(matrices: list[dict]) -> dict[str, tuple[np.ndarray, list[str]]]:
    """Per condition: aggregate matrices across seeds, then story × story RDM."""
    conditions = sorted({m["condition"] for m in matrices})
    story_ids = sorted({m["story_id"] for m in matrices})
    out = {}
    for cond in conditions:
        story_vecs = {}
        for sid in story_ids:
            v = _aggregate_vecs(matrices,
                                lambda m, s=sid, c=cond: m["story_id"] == s and m["condition"] == c)
            if v is not None:
                story_vecs[sid] = v
        keep = [s for s in story_ids if s in story_vecs]
        n = len(keep)
        rdm = np.full((n, n), np.nan)
        for i, si in enumerate(keep):
            rdm[i, i] = 0.0
            for j, sj in enumerate(keep):
                if j <= i:
                    continue
                d = _spearman_distance(story_vecs[si], story_vecs[sj])
                rdm[i, j] = d
                rdm[j, i] = d
        out[cond] = (rdm, keep)
    return out


def inter_condition_rdms(matrices: list[dict]) -> dict[str, tuple[np.ndarray, list[str]]]:
    """Per story: aggregate matrices across seeds, then condition × condition RDM."""
    conditions = sorted({m["condition"] for m in matrices})
    story_ids = sorted({m["story_id"] for m in matrices})
    out = {}
    for sid in story_ids:
        cond_vecs = {}
        for cond in conditions:
            v = _aggregate_vecs(matrices,
                                lambda m, s=sid, c=cond: m["story_id"] == s and m["condition"] == c)
            if v is not None:
                cond_vecs[cond] = v
        keep = [c for c in conditions if c in cond_vecs]
        n = len(keep)
        rdm = np.full((n, n), np.nan)
        for i, ci in enumerate(keep):
            rdm[i, i] = 0.0
            for j, cj in enumerate(keep):
                if j <= i:
                    continue
                d = _spearman_distance(cond_vecs[ci], cond_vecs[cj])
                rdm[i, j] = d
                rdm[j, i] = d
        out[sid] = (rdm, keep)
    return out


def reliability_summary(matrices: list[dict]) -> dict[tuple[str, str], float]:
    """Mean within-(story, condition) cross-seed dissimilarity. Lower = more reliable."""
    out = {}
    keys = sorted({(m["story_id"], m["condition"]) for m in matrices})
    for sid, cond in keys:
        sel = [m for m in matrices if m["story_id"] == sid and m["condition"] == cond]
        if len(sel) < 2:
            out[(sid, cond)] = float("nan")
            continue
        vecs = [_matrix_to_vec(m["matrix"]) for m in sel]
        ds = []
        for i in range(len(vecs)):
            for j in range(i + 1, len(vecs)):
                ds.append(_spearman_distance(vecs[i], vecs[j]))
        valid = [d for d in ds if not np.isnan(d)]
        out[(sid, cond)] = float(np.mean(valid)) if valid else float("nan")
    return out


# -----------------------------------------------------------------------------
# Plotting
# -----------------------------------------------------------------------------

def _heatmap(ax, M, xlabels, ylabels, title, vmin=0, vmax=2, annot=True, cmap="viridis"):
    im = ax.imshow(M, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(xlabels)))
    ax.set_yticks(range(len(ylabels)))
    ax.set_xticklabels(xlabels, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(ylabels, fontsize=8)
    ax.set_title(title, fontsize=10)
    if annot:
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                v = M[i, j]
                if not np.isnan(v):
                    color = "white" if v < (vmin + vmax) / 2 else "black"
                    ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                            fontsize=7, color=color)
    return im


def plot_meta_rdm(rdm: np.ndarray, labels: list[tuple], fig_dir: Path):
    order = sorted(range(len(labels)), key=lambda i: labels[i])
    sorted_rdm = rdm[np.ix_(order, order)]
    sorted_labels = [labels[i] for i in order]
    tick = [f"{l[0][:10]}/{l[1][:3]}/s{l[2]}" for l in sorted_labels]

    fig, ax = plt.subplots(figsize=(0.45 * len(labels) + 3, 0.45 * len(labels) + 2))
    im = _heatmap(ax, sorted_rdm, tick, tick,
                  "Meta-RDM: pairwise distance across all pair-scaling matrices\n"
                  "(1 − Spearman ρ; lower = more similar geometry)",
                  annot=len(labels) <= 24)
    fig.colorbar(im, ax=ax, label="1 − Spearman ρ")

    # Faint white separators between story blocks
    prev = None
    for i, l in enumerate(sorted_labels):
        if l[0] != prev and i > 0:
            ax.axhline(i - 0.5, color="white", linewidth=1.2)
            ax.axvline(i - 0.5, color="white", linewidth=1.2)
        prev = l[0]

    fig.tight_layout()
    fig.savefig(fig_dir / "meta_rdm.png", dpi=150)
    plt.close(fig)


def plot_inter_story_rdms(inter_story: dict, fig_dir: Path):
    conds = ["linear", "nonlinear", "atemporal"]
    conds = [c for c in conds if c in inter_story]
    if not conds:
        return
    fig, axes = plt.subplots(1, len(conds), figsize=(4 * len(conds) + 1.5, 3.8),
                             squeeze=False, constrained_layout=True)
    last_im = None
    for k, cond in enumerate(conds):
        rdm, sids = inter_story[cond]
        last_im = _heatmap(axes[0][k], rdm,
                           [s[:12] for s in sids], [s[:12] for s in sids],
                           f"{cond}: story × story", annot=True)
    if last_im is not None:
        fig.colorbar(last_im, ax=axes.ravel().tolist(), shrink=0.85,
                     label="1 − Spearman ρ", pad=0.02)
    fig.suptitle("Inter-story dissimilarity per condition  (does the model build story-specific geometry?)",
                 fontsize=11)
    fig.savefig(fig_dir / "inter_story_rdms.png", dpi=150)
    plt.close(fig)


def plot_inter_condition_rdms(inter_cond: dict, fig_dir: Path):
    stories = sorted(inter_cond.keys())
    if not stories:
        return
    n = len(stories)
    fig, axes = plt.subplots(1, n, figsize=(3 * n + 1.5, 3.4),
                             squeeze=False, constrained_layout=True)
    last_im = None
    for k, sid in enumerate(stories):
        rdm, conds = inter_cond[sid]
        last_im = _heatmap(axes[0][k], rdm, conds, conds, sid, annot=True)
    if last_im is not None:
        fig.colorbar(last_im, ax=axes.ravel().tolist(), shrink=0.85,
                     label="1 − Spearman ρ", pad=0.02)
    fig.suptitle("Inter-condition dissimilarity per story  (does temporal presentation distort the geometry?)",
                 fontsize=11)
    fig.savefig(fig_dir / "inter_condition_rdms.png", dpi=150)
    plt.close(fig)


def plot_reliability(reliability: dict, fig_dir: Path):
    if not reliability:
        return
    stories = sorted({k[0] for k in reliability})
    conds = ["linear", "nonlinear", "atemporal"]
    conds = [c for c in conds if any(k[1] == c for k in reliability)]
    M = np.array([[reliability.get((s, c), np.nan) for c in conds] for s in stories])

    fig, ax = plt.subplots(figsize=(2 + 1.4 * len(conds), 1.2 + 0.5 * len(stories)))
    im = _heatmap(ax, M, conds, [s[:18] for s in stories],
                  "Across-seed reliability  (mean pairwise 1 − ρ within story×condition)\n"
                  "lower = more consistent across seeds",
                  vmin=0, vmax=1, annot=True, cmap="viridis_r")
    fig.colorbar(im, ax=ax, label="1 − Spearman ρ")
    fig.tight_layout()
    fig.savefig(fig_dir / "reliability.png", dpi=150)
    plt.close(fig)


# -----------------------------------------------------------------------------
# Top-level driver
# -----------------------------------------------------------------------------

def render_meta_rsa(trial_dir: Path, fig_subdir: str = ""):
    """Compute all RDM views, save figures + JSON, return summary dict.

    fig_subdir: if non-empty, figures land in trial_dir/figures/<fig_subdir>/.
    """
    parsed = trial_dir / "parsed"
    fig_dir = trial_dir / "figures" / fig_subdir if fig_subdir else trial_dir / "figures"
    fig_dir.mkdir(exist_ok=True, parents=True)
    matrices = json.loads((parsed / "pair_scaling_matrices.json").read_text())

    meta, labels = compute_meta_rdm(matrices)
    inter_story = inter_story_rdms(matrices)
    inter_cond = inter_condition_rdms(matrices)
    rel = reliability_summary(matrices)

    plot_meta_rdm(meta, labels, fig_dir)
    plot_inter_story_rdms(inter_story, fig_dir)
    plot_inter_condition_rdms(inter_cond, fig_dir)
    plot_reliability(rel, fig_dir)

    # Persist numerical results so downstream analysis isn't recompute-bound
    out = {
        "metric": "1 - Spearman rho on 56 off-diagonal cells",
        "meta_rdm": {
            "labels": [list(l) for l in labels],
            "matrix": _nan_to_none(meta).tolist(),
        },
        "inter_story_rdms": {
            cond: {"story_ids": sids, "matrix": _nan_to_none(rdm).tolist()}
            for cond, (rdm, sids) in inter_story.items()
        },
        "inter_condition_rdms": {
            sid: {"conditions": conds, "matrix": _nan_to_none(rdm).tolist()}
            for sid, (rdm, conds) in inter_cond.items()
        },
        "reliability": {
            f"{sid}__{cond}": (None if np.isnan(v) else v)
            for (sid, cond), v in rel.items()
        },
    }
    (parsed / "meta_rdms.json").write_text(json.dumps(out, indent=2))
    return out


def _nan_to_none(arr: np.ndarray):
    """Replace NaN with None for JSON serialisation."""
    return np.where(np.isnan(arr), None, arr)
