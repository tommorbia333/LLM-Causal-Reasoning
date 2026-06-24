"""
Visualise the model's inferred causal graph per (story, condition).

Combines two task outputs into a single picture:
  - x-positions of nodes  ← model's predicted chronological order (ordering task)
  - directed edges        ← pair-scaling matrix above a strength threshold

Comparing across conditions reveals how the model's "world model" of the same
underlying story changes when the language is manipulated. Atemporal panels
will tend to show wonky x-positions (ordering errors) and possibly altered
edge structure; linear panels should look closest to the gold.

Author-intended (gold) edges are coloured green; model-only edges red. This
makes structural agreement vs disagreement immediately visible.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


# -----------------------------------------------------------------------------
# Aggregation helpers
# -----------------------------------------------------------------------------

def aggregate_ordering(orderings: list[dict], story_id: str, condition: str) -> dict[str, float] | None:
    """Mean rank (1-indexed) of each event across seeds. None if no parsed orderings."""
    rel = [o for o in orderings
           if o["story_id"] == story_id and o["condition"] == condition and o.get("parsed")]
    if not rel:
        return None
    ranks: dict[str, list[int]] = {}
    for o in rel:
        for rank, eid in enumerate(o["parsed"], start=1):
            ranks.setdefault(eid, []).append(rank)
    return {eid: float(np.mean(rs)) for eid, rs in ranks.items()}


def aggregate_matrix(matrices: list[dict], story_id: str, condition: str) -> tuple[np.ndarray, list[str]] | None:
    """Mean pair-scaling matrix across seeds. Returns (matrix, event_ids) or None."""
    rel = [m for m in matrices if m["story_id"] == story_id and m["condition"] == condition]
    if not rel:
        return None
    arrs = []
    for m in rel:
        a = np.array(m["matrix"], dtype=object)
        a = np.where(a == None, np.nan, a).astype(float)  # noqa: E711
        arrs.append(a)
    return np.nanmean(np.stack(arrs), axis=0), rel[0]["event_ids_chronological"]


# -----------------------------------------------------------------------------
# Plotting one panel
# -----------------------------------------------------------------------------

def plot_inferred_graph(
    ax,
    mean_ranks: dict[str, float],
    matrix: np.ndarray,
    event_ids_chrono: list[str],
    event_cards: dict[str, str],
    threshold: float = 4.0,
    gold_edges: set[tuple[str, str]] | None = None,
    title: str = "",
    compact: bool = False,
):
    """
    Render a single condition's inferred-graph panel.

    mean_ranks: {event_id: predicted_rank} where rank=1 is "happened first"
    matrix: 8x8 matrix indexed by event_ids_chrono (rows=source, cols=target)
    event_cards: {event_id: short label}
    threshold: edges with rating < threshold are not drawn
    gold_edges: edges to highlight green (matches author-intended graph)
    compact: if True, omit card text and chronological-position annotations,
             use smaller nodes — for use in dense multi-panel grids.
    """
    n = len(event_ids_chrono)
    gold_edges = gold_edges or set()

    # x-positions from predicted ordering (sort events by mean rank)
    sorted_events = sorted(event_ids_chrono, key=lambda e: mean_ranks.get(e, n + 1))
    xpos = {eid: i + 1 for i, eid in enumerate(sorted_events)}

    node_size = 280 if compact else 520
    node_fontsize = 7.5 if compact else 9

    # Nodes
    for eid in event_ids_chrono:
        x = xpos[eid]
        canon_pos = int(eid[1:])  # E1..E8 → 1..8
        is_misplaced = canon_pos != x
        face = "#fff4d4" if is_misplaced else "#dfe9ff"
        edge = "#a07b00" if is_misplaced else "#1e3a8a"
        ax.scatter([x], [0], s=node_size, color=face, edgecolors=edge,
                   linewidths=1.3, zorder=4)
        ax.text(x, 0, eid, ha="center", va="center", fontsize=node_fontsize,
                fontweight="bold", zorder=5)

        if not compact:
            card = event_cards.get(eid, "")
            if len(card) > 32:
                card = card[:30] + "…"
            ax.text(x, -0.55, card, ha="right", va="top", fontsize=6.5,
                    rotation=22, color="#333", zorder=3)
            if is_misplaced:
                ax.text(x, 0.55, f"chron #{canon_pos}", ha="center", va="bottom",
                        fontsize=6.5, color="#a07b00", style="italic", zorder=3)

    # Edges
    eid_idx = {eid: i for i, eid in enumerate(event_ids_chrono)}
    max_excess = 6 - threshold
    edge_lw_scale = 1.2 if compact else 1.6
    for src in event_ids_chrono:
        for tgt in event_ids_chrono:
            if src == tgt:
                continue
            r = matrix[eid_idx[src], eid_idx[tgt]]
            if np.isnan(r) or r < threshold:
                continue
            x0, x1 = xpos[src], xpos[tgt]
            is_gold = (src, tgt) in gold_edges
            color = "#15803d" if is_gold else "#b91c1c"
            alpha = 0.35 + 0.6 * (r - threshold) / max(max_excess, 0.01)
            lw = 0.6 + edge_lw_scale * (r - threshold) / max(max_excess, 0.01)

            sign = 1 if x1 > x0 else -1
            rad = sign * (0.18 + 0.04 * abs(x1 - x0))
            shrink = 8 if compact else 12
            ax.annotate("",
                        xy=(x1, 0), xytext=(x0, 0),
                        arrowprops=dict(arrowstyle="-|>", color=color,
                                        alpha=alpha, lw=lw,
                                        connectionstyle=f"arc3,rad={rad}",
                                        shrinkA=shrink, shrinkB=shrink),
                        zorder=2)

    ax.set_xlim(0.3, n + 0.7)
    if compact:
        ax.set_ylim(-0.9, 0.9)
    else:
        ax.set_ylim(-1.7, 1.7)
    ax.set_yticks([])
    ax.set_xticks([] if compact else range(1, n + 1))
    if not compact:
        ax.set_xlabel("model's predicted chronological order  →", fontsize=9)
    if title:
        ax.set_title(title, fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    if compact:
        ax.spines["bottom"].set_visible(False)
    ax.axhline(0, color="#cbd5e1", linewidth=0.5, zorder=1)


# -----------------------------------------------------------------------------
# 4-panel comparison per story
# -----------------------------------------------------------------------------

def plot_world_models_for_story(
    story_id: str,
    orderings: list[dict],
    matrices: list[dict],
    gold_graph: dict,
    event_cards_by_id: dict[str, str],
    fig_dir: Path,
    threshold: float = 4.0,
):
    """4-panel comparison: linear, nonlinear, atemporal, gold reference."""
    conditions = ["linear", "nonlinear", "atemporal"]
    gold_edges = {(e["source"], e["target"]) for e in gold_graph.get("causal_edges", [])}

    fig, axes = plt.subplots(4, 1, figsize=(11, 11), constrained_layout=True)

    # First three panels: model conditions
    chrono_ids = None
    for ax, cond in zip(axes[:3], conditions):
        ranks = aggregate_ordering(orderings, story_id, cond)
        mat = aggregate_matrix(matrices, story_id, cond)
        if ranks is None or mat is None:
            ax.set_axis_off()
            ax.set_title(f"{cond} — no data", fontsize=11)
            continue
        matrix, chrono_ids = mat
        plot_inferred_graph(
            ax, ranks, matrix, chrono_ids, event_cards_by_id,
            threshold=threshold, gold_edges=gold_edges,
            title=f"{cond.upper()} — Qwen's inferred world model",
        )

    # Fourth panel: gold reference (canonical ordering, gold edges only)
    ax = axes[3]
    if chrono_ids is None:
        # Fall back to gold's own ordering — events sorted by id
        chrono_ids = sorted({e["source"] for e in gold_graph["causal_edges"]} |
                            {e["target"] for e in gold_graph["causal_edges"]},
                            key=lambda x: int(x[1:]))
    canonical_ranks = {eid: i + 1 for i, eid in enumerate(chrono_ids)}
    # Synthesise a "gold matrix": 6 for direct cause, 4.5 for enables, 0 elsewhere
    gold_matrix = np.zeros((len(chrono_ids), len(chrono_ids)))
    eid_idx = {eid: i for i, eid in enumerate(chrono_ids)}
    for e in gold_graph.get("causal_edges", []):
        if e["source"] in eid_idx and e["target"] in eid_idx:
            val = 6.0 if e.get("type", "causes") == "causes" else 4.5
            gold_matrix[eid_idx[e["source"]], eid_idx[e["target"]]] = val
    plot_inferred_graph(
        ax, canonical_ranks, gold_matrix, chrono_ids, event_cards_by_id,
        threshold=threshold, gold_edges=gold_edges,
        title="GOLD — author-intended graph (canonical ordering)",
    )

    fig.suptitle(f"World models — {story_id}  (green = matches author; red = model-only; "
                 "yellow node = position error)",
                 fontsize=13)
    fig.savefig(fig_dir / f"world_model_{story_id}.png", dpi=150,
                bbox_inches="tight")
    plt.close(fig)


# -----------------------------------------------------------------------------
# Top-level driver
# -----------------------------------------------------------------------------

def render_world_models(trial_dir: Path, stimuli, fig_subdir: str = "", threshold: float = 4.0):
    """Build a world-model comparison figure for every story present in the trial.

    fig_subdir: if non-empty, figures land in trial_dir/figures/<fig_subdir>/.
    """
    import json as _json
    parsed = trial_dir / "parsed"
    fig_dir = trial_dir / "figures" / fig_subdir if fig_subdir else trial_dir / "figures"
    fig_dir.mkdir(exist_ok=True, parents=True)
    orderings = _json.loads((parsed / "ordering.json").read_text())
    matrices = _json.loads((parsed / "pair_scaling_matrices.json").read_text())

    story_ids = sorted({m["story_id"] for m in matrices})
    for sid in story_ids:
        story = stimuli.get_story(sid, "linear")  # any condition has the same event cards
        cards = {ev.id: ev.card for ev in story.events_chronological}
        gold = stimuli.get_author_intended_graph(sid)
        plot_world_models_for_story(
            sid, orderings, matrices, gold, cards, fig_dir, threshold=threshold
        )
