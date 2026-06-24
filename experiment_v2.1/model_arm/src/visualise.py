"""
Per-trial visualisations.

Produces:
- pair_scaling_<story>__<cond>__seed<seed>.png     asymmetric 8x8 heatmap
- pair_scaling_overlay_gold_<story>.png            8x8 author-intended graph (reference)
- ordering_<story>.png                             one panel per condition × seed
- comprehension_summary.png                        accuracy bars per (story, condition)
- pair_scaling_vs_gold_metrics.png          Pearson / Spearman / edge F1 / directional accuracy
- pair_scaling_rating_histogram.png         marginal + joint model vs gold ratings
- summary.png                                      one cross-trial landing page

The heatmap chronological ordering is a key reading aid: rows/cols are sorted
by canonical_position (E1..E8), which makes the same gold structure appear in
the same place across all three conditions, so condition differences pop.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from .stimuli_loader import StimulusBundle
from . import pair_scaling_metrics


CMAP = LinearSegmentedColormap.from_list("rdm", ["#ffffff", "#3b82f6", "#1e3a8a"])

CONDITION_COLORS = {"linear": "#2563eb", "nonlinear": "#7c3aed", "atemporal": "#dc2626"}


def render_all(trial_dir: Path, stimuli: StimulusBundle, clean: bool = True):
    """
    Render every figure for a trial. Layout:

        figures/
          headline.png                       <- the single primary figure
          pair_scaling_matrices/             <- per-run heatmaps + author-intended refs
          world_models/                      <- one inferred-graph figure per story
          diagnostics/                       <- everything else (meta-RDMs, task panels, etc.)
    """
    fig_dir = trial_dir / "figures"
    fig_dir.mkdir(exist_ok=True)

    if clean:
        # Wipe stale figures from prior renders so the new layout is clean
        for child in fig_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    ps_dir = fig_dir / "pair_scaling_matrices"; ps_dir.mkdir()
    wm_dir = fig_dir / "world_models"; wm_dir.mkdir()
    diag_dir = fig_dir / "diagnostics"; diag_dir.mkdir()

    matrices = json.loads((trial_dir / "parsed" / "pair_scaling_matrices.json").read_text())
    orderings = json.loads((trial_dir / "parsed" / "ordering.json").read_text())
    comp = json.loads((trial_dir / "parsed" / "comprehension.json").read_text())
    cf_path = trial_dir / "parsed" / "counterfactual.json"
    cf = json.loads(cf_path.read_text()) if cf_path.exists() else []

    # 1. Pair-scaling matrices → subfolder
    for entry in matrices:
        _plot_heatmap(entry, ps_dir, gold_graph=stimuli.get_author_intended_graph(entry["story_id"]))
    seen = set()
    for entry in matrices:
        if entry["story_id"] in seen:
            continue
        seen.add(entry["story_id"])
        _plot_gold_matrix(entry["story_id"], entry["event_ids_chronological"],
                          stimuli.get_author_intended_graph(entry["story_id"]), ps_dir)

    # 2. World-model graphs → subfolder
    from . import inferred_graph
    inferred_graph.render_world_models(trial_dir, stimuli, fig_subdir="world_models")

    # 3. Diagnostics (everything else) → subfolder
    _plot_pair_scaling_vs_gold(matrices, stimuli, diag_dir)
    _plot_pair_scaling_rating_histograms(matrices, stimuli, diag_dir)
    _plot_orderings(orderings, stimuli, diag_dir)
    if comp:
        _plot_comprehension(comp, diag_dir)
    if cf:
        _plot_cf_anchor_vectors(cf, diag_dir)
        _plot_cf_discrimination(cf, diag_dir)
    _plot_cross_task_heatmap(matrices, orderings, comp, cf, stimuli, diag_dir)
    _plot_condition_contrasts(matrices, orderings, comp, cf, stimuli, diag_dir)

    # 4. Meta-RSA → subfolder (figures); parsed/meta_rdms.json keeps the numerical results
    from . import meta_rsa
    meta_rsa.render_meta_rsa(trial_dir, fig_subdir="diagnostics")

    # 5. The single headline figure → top level
    _plot_headline(matrices, orderings, comp, cf, stimuli, fig_dir)

    # 6. Interactive HTML companions (world-model slider, condition diff, meta map).
    # Skipped quietly if plotly is not installed.
    from . import interactive_graph
    interactive_graph.render_all_interactive(trial_dir, stimuli)


# -----------------------------------------------------------------------------
# Per-figure plotting
# -----------------------------------------------------------------------------

def _plot_heatmap(entry: dict, fig_dir: Path, gold_graph: dict | None):
    M = np.array(entry["matrix"], dtype=float)
    ids = entry["event_ids_chronological"]
    fig, ax = plt.subplots(figsize=(5.5, 5))
    im = ax.imshow(M, cmap=CMAP, vmin=0, vmax=6)
    ax.set_xticks(range(len(ids)))
    ax.set_yticks(range(len(ids)))
    ax.set_xticklabels(ids); ax.set_yticklabels(ids)
    ax.set_xlabel("target event (effect)")
    ax.set_ylabel("source event (cause)")
    ax.set_title(
        f"{entry['story_id']} | {entry['condition']} | seed={entry['seed']}\n"
        f"directed pair scaling (rows cause cols)"
    )
    # Cell labels
    for i in range(len(ids)):
        for j in range(len(ids)):
            v = M[i, j]
            if not np.isnan(v):
                ax.text(j, i, int(v), ha="center", va="center",
                        color="white" if v >= 3 else "black", fontsize=9)
    # Overlay author-intended edges as red rings
    if gold_graph is not None:
        idx = {eid: i for i, eid in enumerate(ids)}
        for edge in gold_graph.get("causal_edges", []):
            if edge["source"] in idx and edge["target"] in idx:
                i, j = idx[edge["source"]], idx[edge["target"]]
                marker = "o" if edge["type"] == "causes" else "s"
                ax.scatter(j, i, s=120, facecolors="none", edgecolors="red",
                           linewidths=1.6, marker=marker)
    plt.colorbar(im, ax=ax, fraction=0.046, label="rating (0–6)")
    fig.tight_layout()
    fname = f"pair_scaling_{entry['story_id']}__{entry['condition']}__seed{entry['seed']}.png"
    fig.savefig(fig_dir / fname, dpi=150)
    plt.close(fig)


def _plot_gold_matrix(story_id: str, chrono_ids: list[str], gold: dict | None, fig_dir: Path):
    if gold is None:
        return
    n = len(chrono_ids)
    M = np.zeros((n, n))
    idx = {eid: i for i, eid in enumerate(chrono_ids)}
    for edge in gold.get("causal_edges", []):
        if edge["source"] in idx and edge["target"] in idx:
            i, j = idx[edge["source"]], idx[edge["target"]]
            M[i, j] = 6 if edge["type"] == "causes" else pair_scaling_metrics.ENABLES_WEIGHT
    fig, ax = plt.subplots(figsize=(5.5, 5))
    im = ax.imshow(M, cmap=CMAP, vmin=0, vmax=6)
    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    ax.set_xticklabels(chrono_ids); ax.set_yticklabels(chrono_ids)
    ax.set_xlabel("target event (effect)")
    ax.set_ylabel("source event (cause)")
    ax.set_title(f"{story_id} | author-intended graph (reference)\n"
                 f"6 = causes, {pair_scaling_metrics.ENABLES_WEIGHT:g} = enables, 0 = no edge")
    for i in range(n):
        for j in range(n):
            if M[i, j] > 0:
                lbl = f"{M[i, j]:g}"
                ax.text(j, i, lbl, ha="center", va="center",
                        color="white" if M[i, j] >= 3 else "black", fontsize=9)
    plt.colorbar(im, ax=ax, fraction=0.046, label="rating (0–6)")
    fig.tight_layout()
    fig.savefig(fig_dir / f"author_intended_{story_id}.png", dpi=150)
    plt.close(fig)


def _plot_pair_scaling_vs_gold(matrices: list[dict], stimuli: StimulusBundle, fig_dir: Path):
    """2×2 panel bar chart: Pearson, Spearman, edge F1 (threshold), directional accuracy."""
    if not matrices:
        return
    specs = [
        ("pearson_r_vs_gold", "Pearson r\n(vs gold weights)"),
        ("spearman_r_vs_gold", "Spearman ρ\n(vs gold weights)"),
        ("edge_f1", f"Edge F1\n(pred ≥ {pair_scaling_metrics.DEFAULT_EDGE_THRESHOLD})"),
        ("directional_accuracy", "Directional accuracy\n(single-edge pairs)"),
    ]
    rows = []
    for entry in matrices:
        gold = stimuli.get_author_intended_graph(entry["story_id"])
        if gold is None:
            continue
        m = pair_scaling_metrics.compute_all(entry, gold)
        rows.append({
            "story_id": entry["story_id"],
            "condition": entry["condition"],
            "seed": entry["seed"],
            **m,
        })
    if not rows:
        return
    stories = sorted({r["story_id"] for r in rows})
    conds = ["linear", "nonlinear", "atemporal"]
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.2))
    axes_flat = axes.flatten()
    width = 0.25
    x_base = np.arange(len(stories))
    for ax, (key, title) in zip(axes_flat, specs):
        for k, cond in enumerate(conds):
            means, errs = [], []
            for sid in stories:
                vals = []
                for r in rows:
                    if r["story_id"] != sid or r["condition"] != cond:
                        continue
                    v = r.get(key)
                    if v is None:
                        continue
                    try:
                        fv = float(v)
                    except (TypeError, ValueError):
                        continue
                    if np.isfinite(fv):
                        vals.append(fv)
                means.append(np.mean(vals) if vals else np.nan)
                errs.append(np.std(vals, ddof=1) if len(vals) > 1 else 0.0)
            ax.bar(x_base + (k - 1) * width, means, width, yerr=errs,
                   label=cond, capsize=3, color=CONDITION_COLORS[cond], alpha=0.75,
                   ecolor="black")
        ax.set_xticks(x_base)
        ax.set_xticklabels(stories, rotation=20, ha="right", fontsize=9)
        ax.set_title(title, fontsize=10)
        ax.axhline(0, color="grey", linewidth=0.5)
        if key in ("pearson_r_vs_gold", "spearman_r_vs_gold"):
            ax.set_ylim(-0.25, 1.05)
        elif key == "edge_f1":
            ax.set_ylim(-0.05, 1.05)
        elif key == "directional_accuracy":
            ax.set_ylim(-0.05, 1.05)
        ax.grid(axis="y", linestyle=":", alpha=0.35)
    axes_flat[0].legend(title="condition", fontsize=8, title_fontsize=8, loc="lower right")
    fig.suptitle(
        "Pair-scaling vs author-intended graph\n(error bars = SD across seeds)",
        fontsize=11,
        y=1.02,
    )
    fig.tight_layout()
    fig.savefig(fig_dir / "pair_scaling_vs_gold_metrics.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_pair_scaling_rating_histograms(matrices: list[dict], stimuli: StimulusBundle, fig_dir: Path):
    """Overlaid density histograms + hexbin of aligned (gold, model) pairs for all runs."""
    if not matrices:
        return
    vm_parts, vg_parts = [], []
    for entry in matrices:
        gold = stimuli.get_author_intended_graph(entry["story_id"])
        vm, vg = pair_scaling_metrics.offdiag_vectors(entry, gold)
        if vm.size:
            vm_parts.append(vm)
            vg_parts.append(vg)
    if not vm_parts:
        return
    vm_all = np.concatenate(vm_parts)
    vg_all = np.concatenate(vg_parts)

    frac_2_4 = float(np.mean((vm_all >= 2) & (vm_all <= 4)))
    frac_extreme = float(np.mean((vm_all <= 1) | (vm_all >= 5)))

    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(12.5, 4.8))
    bins = np.linspace(-0.25, 6.75, 29)
    ax0.hist(
        vm_all, bins=bins, alpha=0.55, density=True, color="#2563eb",
        label=f"model ratings (n={len(vm_all)})",
    )
    ax0.hist(
        vg_all, bins=bins, alpha=0.45, density=True, color="#dc2626",
        label="author weights (same cells)",
    )
    ax0.axvspan(2, 4, alpha=0.12, color="#64748b", label="mid band [2, 4]")
    ax0.set_xlim(-0.5, 7)
    ax0.set_xlabel("Rating / weight (0–6 scale)")
    ax0.set_ylabel("density")
    ax0.set_title("Marginal distributions\n(off-diagonal pairs, all story-runs)")
    ax0.legend(fontsize=8, loc="upper right")
    stats = (
        f"P(model ∈ [2, 4]) = {frac_2_4:.2f}\n"
        f"P(model ≤1 or ≥5) = {frac_extreme:.2f}"
    )
    ax0.text(
        0.02, 0.98, stats, transform=ax0.transAxes, fontsize=9,
        verticalalignment="top", family="monospace",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
    )

    hb = ax1.hexbin(
        vg_all, vm_all, gridsize=22, mincnt=1, cmap="Blues",
        extent=(0, 6.5, 0, 6.5),
    )
    plt.colorbar(hb, ax=ax1, label="count")
    ax1.plot([0, 6], [0, 6], "--", color="grey", lw=0.8, label="y = x")
    ax1.axhspan(2, 4, alpha=0.12, color="#64748b")
    ax1.set_xlabel("Author weight (gold)")
    ax1.set_ylabel("Model rating")
    ax1.set_title(
        "Joint distribution (aligned pairs)\n"
        "mass between y=2–4 when x=0 ⇒ compression"
    )
    ax1.set_xlim(-0.2, 6.6)
    ax1.set_ylim(-0.2, 6.6)
    ax1.set_aspect("equal")
    ax1.legend(fontsize=8, loc="lower right")

    fig.suptitle(
        "Pair-scaling ratings vs author-intended weights",
        fontsize=12, y=1.02,
    )
    fig.tight_layout()
    fig.savefig(fig_dir / "pair_scaling_rating_histogram.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_orderings(orderings: list[dict], stimuli: StimulusBundle, fig_dir: Path):
    if not orderings:
        return
    stories = sorted({o["story_id"] for o in orderings})
    conds = ["linear", "nonlinear", "atemporal"]
    fig, axes = plt.subplots(len(stories), len(conds),
                             figsize=(3.5 * len(conds), 2.6 * len(stories)),
                             squeeze=False)
    for i, sid in enumerate(stories):
        for j, cond in enumerate(conds):
            ax = axes[i][j]
            entries = [o for o in orderings if o["story_id"] == sid and o["condition"] == cond]
            if not entries:
                ax.set_axis_off(); continue
            taus = []
            for e in entries:
                pred = e["parsed"]
                if pred is None:
                    continue
                tau = _kendall_tau_distance(pred)
                taus.append(tau)
                # Plot predicted position vs canonical
                pos = [int(eid[1:]) for eid in pred]
                ax.plot(range(1, 9), pos, "o-", alpha=0.6, label=f"seed{e['seed']}")
            ax.plot([1, 8], [1, 8], "--", color="grey", linewidth=0.7)
            ax.set_xlim(0.5, 8.5); ax.set_ylim(0.5, 8.5)
            ax.set_xticks(range(1, 9)); ax.set_yticks(range(1, 9))
            mean_tau = np.mean(taus) if taus else float("nan")
            ax.set_title(f"{sid} | {cond}\nmean τ-distance = {mean_tau:.1f}",
                         fontsize=9)
            if i == len(stories) - 1:
                ax.set_xlabel("position in model's order")
            if j == 0:
                ax.set_ylabel("canonical event index")
    fig.suptitle("Chronological ordering: predicted position vs canonical")
    fig.tight_layout()
    fig.savefig(fig_dir / "orderings.png", dpi=150)
    plt.close(fig)


def _plot_comprehension(comp: list[dict], fig_dir: Path):
    stories = sorted({c["story_id"] for c in comp})
    conds = ["linear", "nonlinear", "atemporal"]
    fig, ax = plt.subplots(figsize=(7, 4))
    width = 0.25
    x_base = np.arange(len(stories))
    for k, cond in enumerate(conds):
        accs = []
        for sid in stories:
            vals = [c["correct"] for c in comp
                    if c["story_id"] == sid and c["condition"] == cond
                    and c["correct"] is not None]
            accs.append(np.mean(vals) if vals else np.nan)
        ax.bar(x_base + (k - 1) * width, accs, width, label=cond)
    ax.set_xticks(x_base); ax.set_xticklabels(stories, rotation=20, ha="right")
    ax.set_ylabel("comprehension accuracy")
    ax.set_title("Comprehension accuracy by story × condition")
    ax.set_ylim(0, 1.05)
    ax.legend(title="condition")
    fig.tight_layout()
    fig.savefig(fig_dir / "comprehension_accuracy.png", dpi=150)
    plt.close(fig)


# -----------------------------------------------------------------------------
# Counterfactual figures
# -----------------------------------------------------------------------------

def _plot_cf_anchor_vectors(cf: list[dict], fig_dir: Path):
    """One panel per story: anchor vector E1..E6 → E7, one line per condition (avg over seeds)."""
    stories = sorted({r["story_id"] for r in cf})
    conds = ["linear", "nonlinear", "atemporal"]
    colors = {"linear": "#2563eb", "nonlinear": "#7c3aed", "atemporal": "#dc2626"}
    fig, axes = plt.subplots(1, len(stories), figsize=(4.5 * len(stories), 3.6), squeeze=False)
    for i, sid in enumerate(stories):
        ax = axes[0][i]
        for cond in conds:
            rows = [r for r in cf if r["story_id"] == sid and r["condition"] == cond]
            if not rows:
                continue
            arr = np.array([
                [v if v is not None else np.nan for v in r["anchor_vector"]]
                for r in rows
            ], dtype=float)
            mean = np.nanmean(arr, axis=0)
            sd = np.nanstd(arr, axis=0)
            ax.errorbar(range(1, 7), mean, yerr=sd, marker="o",
                        label=cond, color=colors[cond], capsize=2)

            # Plot null controls as horizontal dashed lines (averaged across seeds)
            sib = [r["sibling_null"] for r in rows if r["sibling_null"] is not None]
            rev = [r["reverse_null"] for r in rows if r["reverse_null"] is not None]
            if sib:
                ax.axhline(np.mean(sib), color=colors[cond], linestyle=":", alpha=0.4, linewidth=0.8)
        ax.axhline(3, color="grey", linewidth=0.6)
        ax.text(6.05, 3, "no change", color="grey", fontsize=8, va="center")
        ax.set_xticks(range(1, 7))
        ax.set_xticklabels([f"E{i}" for i in range(1, 7)])
        ax.set_xlabel("antecedent event (counterfactually removed)")
        ax.set_ylabel("rating: 1=much less likely … 5=much more likely")
        ax.set_title(f"{sid}\nCF anchor vector → E7")
        ax.set_ylim(0.5, 5.5)
        if i == 0:
            ax.legend(title="condition", fontsize=8)
    fig.suptitle("Counterfactual anchor vectors (mean ± SD across seeds)")
    fig.tight_layout()
    fig.savefig(fig_dir / "cf_anchor_vectors.png", dpi=150)
    plt.close(fig)


def _plot_cf_discrimination(cf: list[dict], fig_dir: Path):
    stories = sorted({r["story_id"] for r in cf})
    conds = ["linear", "nonlinear", "atemporal"]
    fig, ax = plt.subplots(figsize=(7, 4))
    width = 0.25
    x_base = np.arange(len(stories))
    for k, cond in enumerate(conds):
        means, errs = [], []
        for sid in stories:
            vals = [r["discrimination_index"] for r in cf
                    if r["story_id"] == sid and r["condition"] == cond]
            means.append(np.mean(vals) if vals else np.nan)
            errs.append(np.std(vals, ddof=1) if len(vals) > 1 else 0)
        ax.bar(x_base + (k - 1) * width, means, width, yerr=errs,
               label=cond, capsize=3)
    ax.set_xticks(x_base); ax.set_xticklabels(stories, rotation=20, ha="right")
    ax.set_ylabel("CF discrimination index\nanchor magnitude − null magnitude")
    ax.set_title("CF discrimination index by story × condition\n(higher = cleaner causal model; null controls genuinely centred)")
    ax.axhline(0, color="grey", linewidth=0.5)
    ax.legend(title="condition")
    fig.tight_layout()
    fig.savefig(fig_dir / "cf_discrimination.png", dpi=150)
    plt.close(fig)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _kendall_tau_distance(predicted_ids: list[str]) -> int:
    """Bubble-sort distance from canonical E1..E8 order."""
    pos = [int(e[1:]) for e in predicted_ids]
    d = 0
    for i in range(len(pos)):
        for j in range(i + 1, len(pos)):
            if pos[i] > pos[j]:
                d += 1
    return d


# -----------------------------------------------------------------------------
# Cross-task summary views
# -----------------------------------------------------------------------------

def _build_metrics_table(matrices, orderings, comp, cf, stimuli):
    """One row per (story, condition, seed). Returns list of dicts."""
    rows = []
    keys = sorted({(m["story_id"], m["condition"], m["seed"]) for m in matrices})
    comp_by_key: dict[tuple, list] = {}
    for c in comp:
        comp_by_key.setdefault((c["story_id"], c["condition"], c["seed"]), []).append(c)
    ord_by_key = {(o["story_id"], o["condition"], o["seed"]): o for o in orderings}
    mat_by_key = {(m["story_id"], m["condition"], m["seed"]): m for m in matrices}
    cf_by_key = {(r["story_id"], r["condition"], r["seed"]): r for r in cf}

    for sid, cond, seed in keys:
        items = comp_by_key.get((sid, cond, seed), [])
        # Use boolean `correct` from parsed/comprehension.json (do not compare parsed str to it).
        scored = [it for it in items if it.get("parsed") is not None]
        graded = [it for it in scored if it.get("correct") is not None]
        comp_acc = float(np.mean([bool(it["correct"]) for it in graded])) if graded else float("nan")

        o = ord_by_key.get((sid, cond, seed))
        ord_dist = _kendall_tau_distance(o["parsed"]) if (o and o.get("parsed")) else float("nan")

        m = mat_by_key.get((sid, cond, seed))
        ps_corr = float("nan")
        ps_spearman = float("nan")
        ps_f1 = float("nan")
        ps_dir = float("nan")
        if m is not None:
            gold = stimuli.get_author_intended_graph(sid)
            psm = pair_scaling_metrics.compute_all(m, gold)
            ps_corr = psm["pearson_r_vs_gold"]
            ps_spearman = psm["spearman_r_vs_gold"]
            ps_f1 = psm["edge_f1"]
            ps_dir = psm["directional_accuracy"]

        cf_row = cf_by_key.get((sid, cond, seed))
        cf_d = cf_row["discrimination_index"] if cf_row else float("nan")

        rows.append({
            "story_id": sid, "condition": cond, "seed": seed,
            "comprehension_acc": comp_acc,
            "ordering_distance": ord_dist,
            "pair_scaling_corr_to_gold": ps_corr,
            "pair_scaling_spearman_r": ps_spearman,
            "pair_scaling_edge_f1": ps_f1,
            "pair_scaling_directional_accuracy": ps_dir,
            "cf_discrimination_index": cf_d,
        })
    return rows


def _plot_cross_task_heatmap(matrices, orderings, comp, cf, stimuli: StimulusBundle, fig_dir: Path):
    """One row per (story, condition, seed); columns are normalised task metrics.

    Each column is independently rescaled to [0, 1] with the convention
    "1 = better". Lets you see at a glance which runs were strong on which task.
    """
    rows = _build_metrics_table(matrices, orderings, comp, cf, stimuli)
    if not rows:
        return

    # Order rows: story → condition → seed
    cond_rank = {"linear": 0, "nonlinear": 1, "atemporal": 2}
    rows.sort(key=lambda r: (r["story_id"], cond_rank.get(r["condition"], 9), r["seed"]))

    metric_specs = [
        ("comprehension_acc",         "comprehension acc",          False),  # higher better
        ("ordering_distance",         "ordering Kτ distance",       True),   # lower better → invert
        ("pair_scaling_corr_to_gold", "pair-scaling r vs gold",     False),
        ("cf_discrimination_index",   "CF discrimination index",    False),
    ]

    raw = np.array([[r[k] for k, _, _ in metric_specs] for r in rows], dtype=float)
    norm = np.full_like(raw, np.nan)
    for j, (_, _, invert) in enumerate(metric_specs):
        col = raw[:, j]
        valid = ~np.isnan(col)
        if valid.sum() < 2:
            continue
        lo, hi = np.nanmin(col), np.nanmax(col)
        if hi - lo < 1e-9:
            norm[valid, j] = 0.5
            continue
        scaled = (col - lo) / (hi - lo)
        norm[:, j] = (1 - scaled) if invert else scaled

    fig_h = max(3.0, 0.32 * len(rows) + 1.5)
    fig, ax = plt.subplots(figsize=(7.5, fig_h))
    im = ax.imshow(norm, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)
    fig.colorbar(im, ax=ax, label="task-normalised score (1 = best in trial)")

    ax.set_xticks(range(len(metric_specs)))
    ax.set_xticklabels([m[1] for m in metric_specs], rotation=20, ha="right")
    ylabels = [f"{r['story_id'][:14]} | {r['condition'][:4]} | s{r['seed']}" for r in rows]
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(ylabels, fontsize=7.5)

    # Annotate raw values
    for i, r in enumerate(rows):
        for j, (k, _, _) in enumerate(metric_specs):
            v = r[k]
            if np.isnan(v):
                continue
            txt = f"{v:.2f}"
            ax.text(j, i, txt, ha="center", va="center", fontsize=7,
                    color="black")

    # Faint white separators between stories
    prev = None
    for i, r in enumerate(rows):
        if r["story_id"] != prev and i > 0:
            ax.axhline(i - 0.5, color="white", linewidth=1.2)
        prev = r["story_id"]

    ax.set_title("Cross-task summary  (rows: each story-run; columns: per-task metric;\n"
                 "colour: rank within trial — green = best, red = worst)",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(fig_dir / "cross_task_summary.png", dpi=150)
    plt.close(fig)


def _plot_condition_contrasts(matrices, orderings, comp, cf, stimuli: StimulusBundle, fig_dir: Path):
    """4 panels (one per task), x=condition, y=metric, one line per story.

    Makes condition effects visible per-story (rather than averaged), which
    is the right granularity for a small-N pilot.
    """
    rows = _build_metrics_table(matrices, orderings, comp, cf, stimuli)
    if not rows:
        return
    conds = ["linear", "nonlinear", "atemporal"]
    stories = sorted({r["story_id"] for r in rows})

    metric_specs = [
        ("comprehension_acc",         "comprehension acc",          "higher = better"),
        ("ordering_distance",         "ordering Kτ distance",       "lower = better"),
        ("pair_scaling_corr_to_gold", "pair-scaling r vs gold",     "higher = better"),
        ("cf_discrimination_index",   "CF discrimination index",    "higher = better"),
    ]

    fig, axes = plt.subplots(1, 4, figsize=(15, 3.6))
    palette = plt.cm.tab10.colors
    for j, (key, label, hint) in enumerate(metric_specs):
        ax = axes[j]
        for k, sid in enumerate(stories):
            ys, errs = [], []
            for cond in conds:
                vals = [r[key] for r in rows
                        if r["story_id"] == sid and r["condition"] == cond
                        and not np.isnan(r[key])]
                ys.append(np.mean(vals) if vals else np.nan)
                errs.append(np.std(vals) if len(vals) > 1 else 0.0)
            ax.errorbar(conds, ys, yerr=errs, marker="o", capsize=3,
                        label=sid[:14], color=palette[k % len(palette)],
                        linewidth=1.5, markersize=6)
        ax.set_title(label, fontsize=10)
        ax.set_xlabel(hint, fontsize=8)
        ax.tick_params(axis="x", rotation=15)
        if j == 0:
            ax.legend(fontsize=7, title="story", title_fontsize=7,
                      loc="best", frameon=False)
    fig.suptitle("Per-story condition contrasts  (mean ± SD across seeds)",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(fig_dir / "condition_contrasts.png", dpi=150)
    plt.close(fig)


# -----------------------------------------------------------------------------
# Headline figure (the single primary cross-condition figure)
# -----------------------------------------------------------------------------

def _plot_headline(matrices, orderings, comp, cf, stimuli: StimulusBundle, fig_dir: Path):
    """The single primary figure: 4-panel cross-condition effects with run-level scatter.

    All four metrics oriented so higher = better (ordering distance is converted
    to ordering accuracy, 1 - dist / max_dist), giving a uniform "down = worse"
    reading across panels.
    """
    rows = _build_metrics_table(matrices, orderings, comp, cf, stimuli)
    if not rows:
        return

    # Convert ordering distance → accuracy (consistent direction with the other panels)
    n_events = 8
    max_dist = n_events * (n_events - 1) / 2  # = 28 for 8 events
    for r in rows:
        d = r.get("ordering_distance", float("nan"))
        r["ordering_accuracy"] = (1.0 - d / max_dist) if not np.isnan(d) else float("nan")

    metric_specs = [
        # (data key, panel title, ylim, y-axis label)
        ("comprehension_acc",         "Comprehension\naccuracy",         (0.0, 1.05),
         "Proportion correct"),
        ("ordering_accuracy",         "Ordering\naccuracy",              (0.0, 1.05),
         "1 − (inversion distance / 28)"),
        ("pair_scaling_corr_to_gold", "Pair-scaling\ncorr. to gold",     None,
         "Pearson r (model vs. author matrix)"),
        ("cf_discrimination_index",   "CF discrimination\nindex",        None,
         "mean |r−3| (anchors) −\nmean |r−3| (nulls)"),
    ]
    conditions = ["linear", "nonlinear", "atemporal"]

    # Wide/tall canvas + margins so suptitle / subtitle / panel titles clear the axes.
    fig, axes = plt.subplots(1, 4, figsize=(14.5, 5.65))
    fig.subplots_adjust(left=0.10, right=0.995, top=0.68, bottom=0.14, wspace=0.48)

    rng = np.random.default_rng(42)

    for j, (key, label, ylim, ylabel) in enumerate(metric_specs):
        ax = axes[j]
        for k, cond in enumerate(conditions):
            vals = [r[key] for r in rows
                    if r["condition"] == cond and not np.isnan(r.get(key, float("nan")))]
            if not vals:
                continue
            mean = float(np.mean(vals))
            sem = float(np.std(vals, ddof=1) / np.sqrt(len(vals))) if len(vals) > 1 else 0.0
            color = CONDITION_COLORS[cond]

            ax.bar(k, mean, color=color, alpha=0.45, width=0.7,
                   edgecolor=color, linewidth=1.6, zorder=2)
            ax.errorbar(k, mean, yerr=sem, color="black", capsize=4, lw=1.2, zorder=3)

            # Jittered run-level dots
            jitter = rng.uniform(-0.18, 0.18, len(vals))
            ax.scatter(np.full(len(vals), k) + jitter, vals,
                       color="black", s=26, alpha=0.55, zorder=4,
                       edgecolors="white", linewidths=0.6)

        ax.set_xticks(range(len(conditions)))
        ax.set_xticklabels(conditions, fontsize=10, rotation=10, ha="right")
        ax.set_title(label, fontsize=10.5, pad=14, linespacing=1.35)
        ax.set_ylabel(ylabel, fontsize=9, labelpad=6)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        if ylim is not None:
            ax.set_ylim(*ylim)
        ax.grid(axis="y", linestyle=":", alpha=0.4)
        ax.set_axisbelow(True)

    fig.suptitle(
        "Cross-condition effects on narrative-causal reasoning",
        fontsize=13.5,
        y=0.985,
        weight="bold",
    )
    fig.text(
        0.5,
        0.898,
        "bars = mean across (story × seed) · error bars = SEM · dots = individual runs\n"
        "higher = better in every panel",
        ha="center",
        fontsize=9,
        color="#444",
        style="italic",
        linespacing=1.45,
    )

    fig.savefig(fig_dir / "headline.png", dpi=180, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)
