"""
Interactive HTML companions to the static world-model figures.

Three views are produced per trial (one HTML file each):

  - figures/world_models/world_model_<story>.html
        A3 (condition slider) + A1 (continuous time-stretched 2-D layout:
        x = mean predicted rank, y = canonical / true position) +
        A2 (per-seed dispersion as a legend-toggle overlay).

  - figures/world_models/condition_diff_<story>.html
        Cross-condition diff: all observed edges drawn at once, coloured by
        which condition(s) they appear in (robust across conditions,
        condition-specific, or gold-only / model-missed).

  - figures/diagnostics/meta_map.html
        Each (story x condition x seed) run plus a per-story gold reference is
        placed in a 2-D MDS embedding of the meta-RDM (1 - Spearman rho between
        56 off-diagonal pair-scaling cells). Lets you eyeball which runs cluster.

For a sweep, `render_sweep_meta_map` produces an equivalent map at the sweep
root that pools cells across all (model x prompt_variant) trials and adds a
shape / colour dimension for those factors.

Plotly is imported lazily; if it is not installed the renderer prints a notice
and exits without raising, so the existing matplotlib pipeline is unaffected.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .inferred_graph import aggregate_matrix, aggregate_ordering
from .meta_rsa import _matrix_to_vec, _spearman_distance
from .stimuli_loader import StimulusBundle


# -----------------------------------------------------------------------------
# Shared constants (kept consistent with visualise.py)
# -----------------------------------------------------------------------------

CONDITION_COLORS = {
    "linear":    "#60a5fa",   # lifted from #2563eb so it pops on dark bg
    "nonlinear": "#a78bfa",   # lifted from #7c3aed
    "atemporal": "#f87171",   # lifted from #dc2626
    "gold":      "#34d399",   # lifted from #15803d
}
ALL_CONDITIONS = ["linear", "nonlinear", "atemporal", "gold"]
MODEL_CONDITIONS = ["linear", "nonlinear", "atemporal"]
ENABLES_WEIGHT = 4.5  # used by `_synthesise_gold_matrix` (matches pair_scaling_metrics)


# -----------------------------------------------------------------------------
# Night-mode palette — applied to every Plotly figure produced by this module.
# Colours are chosen to keep markers/edges legible against a near-black canvas.
# -----------------------------------------------------------------------------

NIGHT_BG    = "#0b1020"   # paper background (page outside the plot area)
NIGHT_PANEL = "#111827"   # plot panel background
NIGHT_GRID  = "#1f2937"   # gridlines
NIGHT_AXIS  = "#475569"   # axis lines, zero lines, reference lines
NIGHT_TEXT  = "#e5e7eb"   # primary text
NIGHT_MUTED = "#94a3b8"   # secondary / subtitle text


def _apply_night_layout(fig, *, is_3d: bool = False) -> None:
    """Patch the figure layout with the shared night-mode palette.

    Caller is still responsible for figure-specific axis titles / ranges /
    annotations — this only sets backgrounds, fonts, and grid colours.
    """
    common = dict(
        paper_bgcolor=NIGHT_BG,
        plot_bgcolor=NIGHT_PANEL,
        font=dict(color=NIGHT_TEXT),
        legend=dict(bgcolor=NIGHT_BG, bordercolor=NIGHT_AXIS, borderwidth=0),
    )
    if is_3d:
        axis_style = dict(
            backgroundcolor=NIGHT_PANEL,
            gridcolor=NIGHT_GRID,
            zerolinecolor=NIGHT_AXIS,
            color=NIGHT_TEXT,
            showbackground=True,
        )
        fig.update_layout(
            scene=dict(
                xaxis=axis_style,
                yaxis=axis_style,
                zaxis=axis_style,
                bgcolor=NIGHT_PANEL,
            ),
            **common,
        )
    else:
        axis_style = dict(
            gridcolor=NIGHT_GRID,
            zerolinecolor=NIGHT_AXIS,
            linecolor=NIGHT_AXIS,
            color=NIGHT_TEXT,
        )
        fig.update_layout(
            xaxis=axis_style,
            yaxis=axis_style,
            **common,
        )


# -----------------------------------------------------------------------------
# Edge thresholds: two anchors per variant.
#   cause    = "this is a direct cause" — mean rating >= cause_threshold
#   enables  = "this contributes / enables" — enables_threshold <= rating < cause_threshold
#   none     = drawn only on request (the "missed" category in the world model)
#
# Cuts are placed at the midpoints between the variant's named scale anchors,
# which is the principled cut when responses cluster near the anchors.
# Override per-trial via a `thresholds=` kwarg or via PAIR_SCALING_VARIANTS_THRESHOLDS.
# -----------------------------------------------------------------------------

DEFAULT_EDGE_THRESHOLDS: dict[str, float] = {"enables": 2.5, "cause": 4.5}

EDGE_THRESHOLDS_BY_VARIANT: dict[str, dict[str, float]] = {
    # 4-point anchoring variants (anchors at 0, 2-4, 6): catch 2+ as enables
    "v1_original":     {"enables": 1.5, "cause": 4.5},
    "v3_strict":       {"enables": 1.5, "cause": 4.5},
    # 7-point granular variants (anchors at every integer): catch 2+ as enables
    "v2_full_scale":   {"enables": 1.5, "cause": 4.5},
    "v4_full_strict":  {"enables": 1.5, "cause": 4.5},
    # Human-like (anchors at 0, 3, 6): catch 3+ as enables
    "v5_human_like":   {"enables": 2.5, "cause": 4.5},
}


def get_thresholds(variant: str | None) -> dict[str, float]:
    """Look up edge thresholds for a prompt variant, with safe fallback."""
    if variant and variant in EDGE_THRESHOLDS_BY_VARIANT:
        return dict(EDGE_THRESHOLDS_BY_VARIANT[variant])
    return dict(DEFAULT_EDGE_THRESHOLDS)


def _trial_variant(trial_dir: Path) -> str | None:
    """Read the prompt variant from a trial's manifest.json, if present."""
    manifest_path = trial_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text()).get("pair_scaling_variant")
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Plotly: lazy import with graceful degradation
# -----------------------------------------------------------------------------

def _plotly_or_none():
    """Return the plotly.graph_objects module, or None if plotly is not installed."""
    try:
        import plotly.graph_objects as go
        return go
    except ImportError:
        return None


# -----------------------------------------------------------------------------
# Small numerical helpers
# -----------------------------------------------------------------------------

def _synthesise_gold_matrix(gold_graph: dict | None, chrono_ids: list[str]) -> np.ndarray:
    """Reproduce the same 6 / 4.5 weighting used by the static gold-overlay panel."""
    n = len(chrono_ids)
    M = np.zeros((n, n))
    if gold_graph is None:
        return M
    idx = {eid: i for i, eid in enumerate(chrono_ids)}
    for edge in gold_graph.get("causal_edges", []):
        s, t = edge.get("source"), edge.get("target")
        if s in idx and t in idx:
            M[idx[s], idx[t]] = 6.0 if edge.get("type", "causes") == "causes" else ENABLES_WEIGHT
    return M


def _matrix_from_entry(entry: dict) -> np.ndarray:
    """Pair-scaling matrix as a NaN-aware float array, taken from one parsed-row entry."""
    a = np.array(entry["matrix"], dtype=object)
    return np.where(a == None, np.nan, a).astype(float)  # noqa: E711


def _classical_mds(D: np.ndarray, n_dims: int = 2) -> np.ndarray:
    """Classical (Torgerson) MDS. Replaces NaNs in D with mean off-diagonal distance."""
    D = np.asarray(D, dtype=np.float64).copy()
    if D.size == 0:
        return np.zeros((0, n_dims))
    n = D.shape[0]
    off = D[~np.eye(n, dtype=bool)]
    finite = off[np.isfinite(off)]
    fill = float(np.mean(finite)) if finite.size else 1.0
    D[~np.isfinite(D)] = fill
    D[np.eye(n, dtype=bool)] = 0.0

    # Suppress spurious BLAS-internal warnings on certain platforms; inputs
    # are validated above so any actual non-finite output would still bubble
    # up via np.linalg.eigh below.
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        D2 = D ** 2
        J = np.eye(n) - np.ones((n, n)) / n
        B = -0.5 * (J @ D2 @ J)
    B = (B + B.T) / 2  # numerical symmetry

    eigvals, eigvecs = np.linalg.eigh(B)
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]
    top = np.clip(eigvals[:n_dims], 0.0, None)
    return eigvecs[:, :n_dims] * np.sqrt(top)


# -----------------------------------------------------------------------------
# Edge classification: cross model-kind with gold-kind to a small category set.
# -----------------------------------------------------------------------------

# Display colour + width + dash settings per category. Picked so that:
#   - "match" categories are green; "false" categories are red; "kind mismatches"
#     are amber (right edge, wrong strength).
#   - "cause" kinds are solid + thicker; "enables" kinds are lighter + (where
#     supported) dashed. Annotation arrows can't carry a dash style, so the
#     world-model view leans on width / opacity / colour saturation; the diff
#     view (which uses Scatter line traces) gets a true dash pattern.

EDGE_CATEGORY_STYLE: dict[str, dict] = {
    "match_direct":   dict(color="#15803d", width=3.2, opacity=0.90, dash="solid",
                           label="gold causes  ·  model direct cause"),
    "match_enables":  dict(color="#16a34a", width=2.1, opacity=0.78, dash="dash",
                           label="gold enables  ·  model enables / contributes"),
    "underweighted":  dict(color="#a16207", width=2.0, opacity=0.78, dash="dash",
                           label="gold causes  ·  model only enables  (underweighted)"),
    "overweighted":   dict(color="#ca8a04", width=2.8, opacity=0.80, dash="solid",
                           label="gold enables  ·  model direct cause  (overweighted)"),
    "false_cause":    dict(color="#b91c1c", width=2.8, opacity=0.78, dash="solid",
                           label="not in gold  ·  model direct cause  (false positive)"),
    "false_enables":  dict(color="#ef4444", width=1.8, opacity=0.62, dash="dash",
                           label="not in gold  ·  model enables  (weak false positive)"),
    "missed":         dict(color="#64748b", width=1.4, opacity=0.55, dash="dot",
                           label="gold present  ·  model missed entirely"),
}

# Order used for legend ranking
EDGE_CATEGORY_ORDER = [
    "match_direct", "match_enables",
    "underweighted", "overweighted",
    "false_cause", "false_enables",
    "missed",
]


def _model_edge_kind(rating: float, thresholds: dict[str, float]) -> str | None:
    """Return 'cause', 'enables', or None given a (mean) pair-scaling rating."""
    if rating is None or not np.isfinite(rating):
        return None
    if rating >= thresholds["cause"]:
        return "cause"
    if rating >= thresholds["enables"]:
        return "enables"
    return None


def _gold_edge_kind(edge: tuple[str, str], gold_edges: dict[tuple[str, str], str]) -> str | None:
    """Return 'causes', 'enables', or None for an edge given the gold edge map."""
    return gold_edges.get(edge)


def _classify_edge(model_kind: str | None, gold_kind: str | None) -> str | None:
    """Map (model_kind, gold_kind) to one of EDGE_CATEGORY_STYLE keys."""
    if model_kind == "cause" and gold_kind == "causes":
        return "match_direct"
    if model_kind == "enables" and gold_kind == "enables":
        return "match_enables"
    if model_kind == "enables" and gold_kind == "causes":
        return "underweighted"
    if model_kind == "cause" and gold_kind == "enables":
        return "overweighted"
    if model_kind == "cause" and gold_kind is None:
        return "false_cause"
    if model_kind == "enables" and gold_kind is None:
        return "false_enables"
    if model_kind is None and gold_kind is not None:
        return "missed"
    return None  # no edge from either side — nothing to draw


def _gold_edge_map(gold_graph: dict | None) -> dict[tuple[str, str], str]:
    """{(source, target): 'causes' | 'enables'} from the author-intended graph."""
    if gold_graph is None:
        return {}
    out: dict[tuple[str, str], str] = {}
    for e in gold_graph.get("causal_edges", []):
        s, t = e.get("source"), e.get("target")
        if s and t:
            out[(s, t)] = e.get("type", "causes")
    return out


def _per_seed_rank_map(orderings: list[dict], story_id: str, condition: str) -> list[tuple[int, dict[str, int]]]:
    """List of (seed, {event_id -> 1-indexed rank}) for every seed with a parsed ordering."""
    rel = [
        o for o in orderings
        if o["story_id"] == story_id and o["condition"] == condition and o.get("parsed")
    ]
    out = []
    for o in rel:
        ranks = {eid: rank for rank, eid in enumerate(o["parsed"], start=1)}
        out.append((o["seed"], ranks))
    return out


# -----------------------------------------------------------------------------
# View 1: per-trial, per-story world model (A3 slider + A1 layout + A2 toggle)
# -----------------------------------------------------------------------------

def _build_world_model_fig(
    story_id: str,
    orderings: list[dict],
    matrices: list[dict],
    gold_graph: dict | None,
    cards: dict[str, str],
    chrono_ids: list[str],
    go,
    thresholds: dict[str, float] | None = None,
):
    """Single Plotly figure with one condition slider step per condition.

    Coord system (A1):
        x = mean predicted rank (continuous; 1..n, but fractional → "stretched"
            sections show events the model could not separate temporally)
        y = canonical / true chronological position (fixed; 1..n)

    Layered on each step:
        - aggregated-mean node trace (visible)
        - per-seed dispersion trace (legendonly; user clicks to overlay — A2)
        - directed edges as Plotly annotations, styled by edge category
          (cause / enables × matches-gold / mismatched / false / missed).
    """
    thr = thresholds or DEFAULT_EDGE_THRESHOLDS
    n = len(chrono_ids)
    canonical = {eid: int(eid[1:]) for eid in chrono_ids}  # E1..E8 -> 1..8
    gold_edges_map = _gold_edge_map(gold_graph)

    # Tiny deterministic jitter so coincident seed dots don't perfectly overplot.
    rng = np.random.default_rng(0)

    # ---- Collect per-condition data --------------------------------------
    per_condition: dict[str, dict[str, Any]] = {}
    for cond in MODEL_CONDITIONS:
        mean_ranks = aggregate_ordering(orderings, story_id, cond) or {}
        mat = aggregate_matrix(matrices, story_id, cond)
        per_condition[cond] = {
            "mean_ranks": mean_ranks,
            "mean_matrix": mat[0] if mat else None,
            "chrono_ids_for_matrix": mat[1] if mat else chrono_ids,
            "seed_ranks": _per_seed_rank_map(orderings, story_id, cond),
        }
    per_condition["gold"] = {
        "mean_ranks": {eid: float(canonical[eid]) for eid in chrono_ids},
        "mean_matrix": _synthesise_gold_matrix(gold_graph, chrono_ids),
        "chrono_ids_for_matrix": chrono_ids,
        "seed_ranks": [],
    }

    traces: list[Any] = []
    trace_meta: list[dict[str, str]] = []  # parallel: {"cond": ..., "role": "mean"|"seeds"}
    annotations_per_cond: dict[str, list[dict]] = {}

    for cond in ALL_CONDITIONS:
        d = per_condition[cond]
        color = CONDITION_COLORS[cond]
        ranks_for_x = d["mean_ranks"] if d["mean_ranks"] else {eid: float(canonical[eid]) for eid in chrono_ids}

        # ---- aggregated-mean node trace ----
        xs = [float(ranks_for_x.get(eid, canonical[eid])) for eid in chrono_ids]
        ys = [canonical[eid] for eid in chrono_ids]
        hover = [
            (
                f"<b>{eid}</b>  ({cond})<br>"
                f"{cards.get(eid, '')[:80]}<br>"
                f"predicted rank (mean): {x:.2f}<br>"
                f"canonical position: {y}<br>"
                f"displacement: {x - y:+.2f}"
            )
            for eid, x, y in zip(chrono_ids, xs, ys)
        ]
        # Misplacement halo: amber ring if mean rank rounds to a non-canonical slot.
        marker_line_colors = [
            "#fbbf24" if round(x) != y else "white"
            for x, y in zip(xs, ys)
        ]
        marker_line_widths = [
            2.0 if round(x) != y else 1.4
            for x, y in zip(xs, ys)
        ]
        traces.append(go.Scatter(
            x=xs, y=ys,
            mode="markers+text",
            text=chrono_ids,
            textfont=dict(size=10, color="white"),
            textposition="middle center",
            hovertext=hover, hoverinfo="text",
            marker=dict(
                size=22, color=color,
                line=dict(width=marker_line_widths, color=marker_line_colors),
                symbol="circle",
            ),
            name=f"{cond} (mean)",
            legendgroup=cond,
            showlegend=True,
            visible=(cond == "linear"),
        ))
        trace_meta.append({"cond": cond, "role": "mean"})

        # ---- per-seed dispersion overlay (A2) ----
        seed_xs: list[float] = []
        seed_ys: list[float] = []
        seed_hover: list[str] = []
        for seed, ranks in d["seed_ranks"]:
            for eid in chrono_ids:
                if eid not in ranks:
                    continue
                seed_xs.append(float(ranks[eid]))
                seed_ys.append(canonical[eid] + float(rng.uniform(-0.08, 0.08)))
                seed_hover.append(
                    f"<b>{eid}</b> | seed={seed} | {cond}<br>"
                    f"rank this seed: {ranks[eid]} (canonical {canonical[eid]})"
                )
        if seed_xs:
            traces.append(go.Scatter(
                x=seed_xs, y=seed_ys,
                mode="markers",
                hovertext=seed_hover, hoverinfo="text",
                marker=dict(size=7, color=color, opacity=0.45,
                            line=dict(width=0)),
                name=f"{cond} (per seed)",
                legendgroup=cond,
                showlegend=True,
                visible=("legendonly" if cond == "linear" else False),
            ))
            trace_meta.append({"cond": cond, "role": "seeds"})

        # ---- edges as annotations, styled by edge category ----
        # Plotly annotation arrows can't carry a `dash` style, so the world
        # model view encodes edge-kind via colour saturation + width + opacity
        # (see EDGE_CATEGORY_STYLE). The diff view does carry a dash style
        # because its edges are Scatter line traces.
        anns: list[dict] = []
        M = d["mean_matrix"]
        if M is not None:
            local_ids = d["chrono_ids_for_matrix"]
            eid_idx = {eid: i for i, eid in enumerate(local_ids)}
            # Walk every ordered pair: classify the model edge, cross with gold.
            seen_edges: set[tuple[str, str]] = set()
            for src in local_ids:
                for tgt in local_ids:
                    if src == tgt:
                        continue
                    r = M[eid_idx[src], eid_idx[tgt]]
                    r_val = float(r) if (r is not None and np.isfinite(r)) else None
                    m_kind = _model_edge_kind(r_val, thr) if r_val is not None else None
                    g_kind = _gold_edge_kind((src, tgt), gold_edges_map)
                    # Gold reference panel: ignore the model entirely; draw whatever the
                    # gold graph says, styled as match_* per its kind.
                    if cond == "gold":
                        cat = ("match_direct" if g_kind == "causes"
                               else "match_enables" if g_kind == "enables"
                               else None)
                    else:
                        cat = _classify_edge(m_kind, g_kind)
                    if cat is None or cat == "missed":
                        # "missed" edges are accumulated separately below so that
                        # they can be hidden by default — they're noisy to draw
                        # alongside live edges.
                        continue
                    seen_edges.add((src, tgt))
                    sty = EDGE_CATEGORY_STYLE[cat]
                    # Modulate width / opacity slightly by within-category strength.
                    if m_kind == "cause":
                        excess = (r_val - thr["cause"]) / max(6.0 - thr["cause"], 0.01) if r_val else 0.0
                    elif m_kind == "enables":
                        excess = (r_val - thr["enables"]) / max(thr["cause"] - thr["enables"], 0.01) if r_val else 0.0
                    else:
                        excess = 0.5
                    excess = float(np.clip(excess, 0.0, 1.0))
                    width = sty["width"] * (0.75 + 0.5 * excess)
                    alpha = sty["opacity"] * (0.75 + 0.35 * excess)
                    rating_str = "n/a" if r_val is None else f"{r_val:.2f}"
                    x_src = float(ranks_for_x.get(src, canonical[src]))
                    y_src = canonical[src]
                    x_tgt = float(ranks_for_x.get(tgt, canonical[tgt]))
                    y_tgt = canonical[tgt]
                    anns.append(dict(
                        x=x_tgt, y=y_tgt, ax=x_src, ay=y_src,
                        xref="x", yref="y", axref="x", ayref="y",
                        showarrow=True, arrowhead=3,
                        arrowsize=1.0, arrowwidth=float(width),
                        arrowcolor=sty["color"],
                        opacity=float(np.clip(alpha, 0.05, 0.98)),
                        standoff=11, startstandoff=11,
                        hovertext=(
                            f"<b>{src} → {tgt}</b><br>"
                            f"category: {cat}<br>"
                            f"mean rating: {rating_str}<br>"
                            f"model kind: {m_kind or 'none'}  ·  gold kind: {g_kind or 'none'}"
                        ),
                    ))

            # Missed gold edges: lay them on top as faint dotted arrows so the
            # reader can sanity-check coverage. They share the "missed" style.
            if cond != "gold":
                for (src, tgt), g_kind in gold_edges_map.items():
                    if (src, tgt) in seen_edges or src not in eid_idx or tgt not in eid_idx:
                        continue
                    r = M[eid_idx[src], eid_idx[tgt]]
                    r_val = float(r) if (r is not None and np.isfinite(r)) else None
                    if r_val is not None and r_val >= thr["enables"]:
                        continue  # already drawn above as a match
                    sty = EDGE_CATEGORY_STYLE["missed"]
                    rating_str = "n/a" if r_val is None else f"{r_val:.2f}"
                    x_src = float(ranks_for_x.get(src, canonical[src]))
                    y_src = canonical[src]
                    x_tgt = float(ranks_for_x.get(tgt, canonical[tgt]))
                    y_tgt = canonical[tgt]
                    anns.append(dict(
                        x=x_tgt, y=y_tgt, ax=x_src, ay=y_src,
                        xref="x", yref="y", axref="x", ayref="y",
                        showarrow=True, arrowhead=2,
                        arrowsize=0.9, arrowwidth=sty["width"],
                        arrowcolor=sty["color"], opacity=sty["opacity"],
                        standoff=11, startstandoff=11,
                        hovertext=(
                            f"<b>{src} → {tgt}</b><br>category: missed<br>"
                            f"mean rating: {rating_str} (below enables threshold "
                            f"{thr['enables']:g})<br>gold kind: {g_kind}"
                        ),
                    ))
        annotations_per_cond[cond] = anns

    # ---- Layout: diagonal reference, square aspect, legend on the right ----
    diag = dict(
        type="line",
        x0=0.5, y0=0.5, x1=n + 0.5, y1=n + 0.5,
        line=dict(color=NIGHT_AXIS, width=1.5, dash="dash"),
        layer="below",
    )

    # ---- Legend explainer traces for edge categories ----
    # Annotation arrows don't appear in the legend, so add invisible Scatter
    # entries with the matching colours so the reader can identify categories.
    for cat in EDGE_CATEGORY_ORDER:
        sty = EDGE_CATEGORY_STYLE[cat]
        traces.append(go.Scatter(
            x=[None], y=[None], mode="lines",
            line=dict(color=sty["color"], width=sty["width"], dash=sty["dash"]),
            opacity=sty["opacity"],
            name=sty["label"],
            legendgroup="edge_categories",
            legendgrouptitle=dict(text="edge categories (annotations on plot)"),
            showlegend=True,
            visible=True,
        ))
        trace_meta.append({"cond": "_legend", "role": "legend"})

    # Rebuild slider visibility arrays so legend traces stay visible across steps
    steps = []
    for cond in ALL_CONDITIONS:
        vis: list[Any] = []
        for tm in trace_meta:
            if tm["cond"] == "_legend":
                vis.append(True)
            elif tm["cond"] != cond:
                vis.append(False)
            elif tm["role"] == "mean":
                vis.append(True)
            else:  # "seeds"
                vis.append("legendonly")
        steps.append(dict(
            method="update",
            label=cond,
            args=[{"visible": vis}, {"annotations": annotations_per_cond[cond]}],
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=dict(
            text=(
                f"World model — <b>{story_id}</b>"
                "<br><sup>x = mean predicted rank · y = canonical position · "
                "diagonal = perfect ordering · edge taxonomy: "
                f"direct cause = mean ≥ {thr['cause']:g}, "
                f"enables / contributes = {thr['enables']:g} ≤ mean &lt; {thr['cause']:g}</sup>"
            ),
            font=dict(size=15),
            x=0.02, xanchor="left",
        ),
        xaxis=dict(
            title="model's predicted chronological position (mean rank)",
            range=[0.4, n + 0.6],
            tickmode="array",
            tickvals=list(range(1, n + 1)),
            zeroline=False,
        ),
        yaxis=dict(
            title="canonical (true) chronological position",
            range=[0.4, n + 0.6],
            tickmode="array",
            tickvals=list(range(1, n + 1)),
            zeroline=False,
            scaleanchor="x", scaleratio=1,
        ),
        sliders=[dict(
            steps=steps,
            active=0,
            x=0.08, len=0.86,
            pad=dict(t=40, b=10),
            currentvalue=dict(prefix="condition: ", font=dict(size=13, color=NIGHT_TEXT)),
            bgcolor=NIGHT_PANEL,
            activebgcolor=NIGHT_AXIS,
            bordercolor=NIGHT_AXIS,
            font=dict(color=NIGHT_TEXT),
        )],
        shapes=[diag],
        annotations=annotations_per_cond["linear"],
        height=720, width=900,
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top", y=0.99,
            xanchor="left", x=1.02,
            font=dict(size=10, color=NIGHT_TEXT),
            title=dict(text="legend (click to toggle)", font=dict(size=10, color=NIGHT_TEXT)),
        ),
        margin=dict(l=70, r=170, t=90, b=110),
    )
    _apply_night_layout(fig)
    return fig


def render_per_trial_world_models(trial_dir: Path, stimuli: StimulusBundle,
                                  fig_subdir: str = "world_models") -> int:
    """Per-story interactive world-model HTML. Returns number of files written."""
    go = _plotly_or_none()
    if go is None:
        print("    (plotly not installed; skipping interactive world-models)")
        return 0
    parsed = trial_dir / "parsed"
    if not (parsed / "pair_scaling_matrices.json").exists():
        return 0
    matrices = json.loads((parsed / "pair_scaling_matrices.json").read_text())
    ordering_path = parsed / "ordering.json"
    orderings = json.loads(ordering_path.read_text()) if ordering_path.exists() else []

    thresholds = get_thresholds(_trial_variant(trial_dir))
    fig_dir = trial_dir / "figures" / fig_subdir
    fig_dir.mkdir(exist_ok=True, parents=True)

    n_written = 0
    for sid in sorted({m["story_id"] for m in matrices}):
        story = stimuli.get_story(sid, "linear")
        chrono_ids = [ev.id for ev in story.events_chronological]
        cards = {ev.id: ev.card for ev in story.events_chronological}
        gold = stimuli.get_author_intended_graph(sid)
        fig = _build_world_model_fig(
            sid, orderings, matrices, gold, cards, chrono_ids, go,
            thresholds=thresholds,
        )
        fig.write_html(
            fig_dir / f"world_model_{sid}.html",
            include_plotlyjs="cdn", full_html=True,
        )
        n_written += 1
    return n_written


# -----------------------------------------------------------------------------
# View 2: per-trial cross-condition diff (one HTML per story)
# -----------------------------------------------------------------------------

def _build_diff_fig(
    story_id: str,
    matrices: list[dict],
    gold_graph: dict | None,
    cards: dict[str, str],
    chrono_ids: list[str],
    go,
    thresholds: dict[str, float] | None = None,
):
    """Cross-condition diff figure.

    Layout: all events on a horizontal line at their canonical positions (so
    layout is stable for comparison). Edges are drawn as Plotly Scatter line
    arcs and styled by:

      colour  — which condition(s) support the edge
                  green   robust (all 3 conditions)
                  amber   2 of 3 conditions
                  per-condition colour if exactly 1 condition
                  grey    gold-only (model missed it everywhere)
      dash    — predominant model kind across supporting conditions
                  solid    direct cause   (mean across supporting conds ≥ cause threshold)
                  dash     enables / contributes
                  dot      gold-only (no model rating reaches threshold)

    Each colour × dash combination is its own legend entry so the reader can
    isolate any class with one click.
    """
    thr = thresholds or DEFAULT_EDGE_THRESHOLDS
    n = len(chrono_ids)
    canonical = {eid: int(eid[1:]) for eid in chrono_ids}
    gold_edges_map = _gold_edge_map(gold_graph)
    gold_edges = set(gold_edges_map.keys())

    # Per-condition: collect edges that meet at least the *enables* threshold,
    # along with their mean rating and induced model kind.
    cond_edges: dict[str, set] = {}
    cond_strengths: dict[str, dict[tuple, float]] = {}
    cond_kinds: dict[str, dict[tuple, str]] = {}
    for cond in MODEL_CONDITIONS:
        mat = aggregate_matrix(matrices, story_id, cond)
        if mat is None:
            continue
        M, local_ids = mat
        eid_idx = {eid: i for i, eid in enumerate(local_ids)}
        edges: set[tuple[str, str]] = set()
        strengths: dict[tuple, float] = {}
        kinds: dict[tuple, str] = {}
        for src in local_ids:
            for tgt in local_ids:
                if src == tgt:
                    continue
                v = M[eid_idx[src], eid_idx[tgt]]
                if not np.isfinite(v):
                    continue
                k = _model_edge_kind(float(v), thr)
                if k is None:
                    continue
                edges.add((src, tgt))
                strengths[(src, tgt)] = float(v)
                kinds[(src, tgt)] = k
        cond_edges[cond] = edges
        cond_strengths[cond] = strengths
        cond_kinds[cond] = kinds

    all_edges = set(gold_edges)
    for s in cond_edges.values():
        all_edges |= s

    def classify(edge: tuple[str, str]) -> tuple[str, str, str, str]:
        """Return (colour_category, dash, hover_label, kind_label)."""
        present = tuple(c for c in MODEL_CONDITIONS if edge in cond_edges.get(c, set()))
        in_gold = edge in gold_edges
        # Colour category from presence pattern
        if len(present) == 3:
            colour_cat = "robust"
            present_label = "all three conditions"
        elif len(present) == 2:
            colour_cat = "two"
            present_label = "  ∩  ".join(present)
        elif len(present) == 1:
            colour_cat = f"only_{present[0]}"
            present_label = f"only in {present[0]}"
        else:
            colour_cat = "gold_only"
            present_label = "gold-only (model missed everywhere)"
        # Dash style from mean rating across supporting conditions
        if present:
            mean_r = float(np.mean([cond_strengths[c][edge] for c in present]))
            kind = "cause" if mean_r >= thr["cause"] else "enables"
            dash = "solid" if kind == "cause" else "dash"
            kind_label = (f"direct cause (mean across {len(present)} cond. = {mean_r:.2f})"
                          if kind == "cause"
                          else f"enables / contributes (mean across {len(present)} cond. = {mean_r:.2f})")
        else:
            dash = "dot"
            kind_label = "no model rating reached the enables threshold"
        in_gold_lbl = "  (in gold)" if in_gold else ""
        return colour_cat, dash, f"{present_label}{in_gold_lbl}", kind_label

    # Colour per presence-category
    colour_for = {
        "robust":          "#15803d",
        "two":             "#a16207",
        "only_linear":     CONDITION_COLORS["linear"],
        "only_nonlinear":  CONDITION_COLORS["nonlinear"],
        "only_atemporal":  CONDITION_COLORS["atemporal"],
        "gold_only":       "#64748b",
    }
    width_for = {
        "robust": 3.0, "two": 2.4,
        "only_linear": 1.9, "only_nonlinear": 1.9, "only_atemporal": 1.9,
        "gold_only": 1.6,
    }
    opacity_for = {
        "robust": 0.88, "two": 0.80,
        "only_linear": 0.78, "only_nonlinear": 0.78, "only_atemporal": 0.78,
        "gold_only": 0.65,
    }
    colour_legend_order = ["robust", "two", "only_linear", "only_nonlinear",
                           "only_atemporal", "gold_only"]
    colour_legend_labels = {
        "robust":          "robust (all 3 conditions)",
        "two":             "in 2 of 3 conditions",
        "only_linear":     "linear-only",
        "only_nonlinear":  "nonlinear-only",
        "only_atemporal":  "atemporal-only",
        "gold_only":       "gold-only (model missed)",
    }
    dash_legend_label = {
        "solid": "direct cause  (solid)",
        "dash":  "enables / contributes  (dashed)",
        "dot":   "gold-only  (dotted)",
    }

    # ---- Nodes: a horizontal line at canonical positions ----
    node_x = [canonical[eid] for eid in chrono_ids]
    node_y = [0.0] * n
    node_hover = [
        f"<b>{eid}</b><br>{cards.get(eid, '')[:120]}<br>canonical position {canonical[eid]}"
        for eid in chrono_ids
    ]
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        text=chrono_ids,
        textfont=dict(size=10, color="white"),
        textposition="middle center",
        hovertext=node_hover, hoverinfo="text",
        marker=dict(size=22, color="#3b82f6",
                    line=dict(width=1.4, color="white")),
        name="events", showlegend=False,
    )

    # ---- Edge traces (one Scatter line per edge; grouped by colour category) ----
    edge_traces: list[Any] = []
    legend_seen_colour: set[str] = set()
    arrow_xs, arrow_ys, arrow_colors, arrow_hover = [], [], [], []

    for edge in sorted(all_edges, key=lambda e: (canonical[e[0]], canonical[e[1]])):
        colour_cat, dash, presence_label, kind_label = classify(edge)
        colour = colour_for[colour_cat]
        width = width_for[colour_cat]
        opacity = opacity_for[colour_cat]
        src, tgt = edge
        x0, x1 = canonical[src], canonical[tgt]
        sign = 1.0 if x1 > x0 else -1.0
        rad = sign * (0.22 + 0.05 * abs(x1 - x0))
        mx = (x0 + x1) / 2.0
        cy = rad * (abs(x1 - x0))
        t = np.linspace(0.0, 1.0, 22)
        xs_curve = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t ** 2 * x1
        ys_curve = (1 - t) ** 2 * 0 + 2 * (1 - t) * t * cy + t ** 2 * 0

        present = tuple(c for c in MODEL_CONDITIONS if edge in cond_edges.get(c, set()))
        if present:
            per_cond = ", ".join(
                f"{c}: {cond_strengths[c][edge]:.2f} [{cond_kinds[c][edge]}]"
                for c in present
            )
        else:
            per_cond = "no model rating reached the enables threshold"
        gold_kind = gold_edges_map.get(edge)
        gold_str = f"gold kind: {gold_kind}" if gold_kind else "not in gold"

        is_first = colour_cat not in legend_seen_colour
        legend_seen_colour.add(colour_cat)
        edge_traces.append(go.Scatter(
            x=xs_curve, y=ys_curve,
            mode="lines",
            line=dict(color=colour, width=width, shape="spline", dash=dash),
            opacity=opacity,
            hovertext=(
                f"<b>{src} → {tgt}</b><br>"
                f"presence: {presence_label}<br>"
                f"kind: {kind_label}<br>{gold_str}<br>"
                f"per-condition: {per_cond}"
            ),
            hoverinfo="text",
            name=colour_legend_labels[colour_cat],
            legendgroup=colour_cat,
            showlegend=is_first,
        ))

        # Arrowhead glyph at the tip
        t_tip = 0.96
        xt = (1 - t_tip) ** 2 * x0 + 2 * (1 - t_tip) * t_tip * mx + t_tip ** 2 * x1
        yt = (1 - t_tip) ** 2 * 0 + 2 * (1 - t_tip) * t_tip * cy + t_tip ** 2 * 0
        arrow_xs.append(xt); arrow_ys.append(yt)
        arrow_colors.append(colour)
        arrow_hover.append(f"{src} → {tgt}  ·  {presence_label}")

    if arrow_xs:
        edge_traces.append(go.Scatter(
            x=arrow_xs, y=arrow_ys, mode="markers",
            marker=dict(size=10, color=arrow_colors,
                        symbol="circle", line=dict(width=0)),
            hovertext=arrow_hover, hoverinfo="text",
            showlegend=False, name="arrowheads",
        ))

    # ---- Legend explainer traces: dash patterns (cause vs enables vs missed) ----
    # Lets the reader decode the line style independently of colour.
    for dash, name in [("solid", "direct cause  (solid)"),
                       ("dash",  "enables / contributes  (dashed)"),
                       ("dot",   "gold-only  (dotted)")]:
        edge_traces.append(go.Scatter(
            x=[None], y=[None], mode="lines",
            line=dict(color=NIGHT_MUTED, width=2.2, dash=dash),
            opacity=0.9,
            name=name,
            legendgroup="dash_meaning",
            legendgrouptitle=dict(text="line style = model edge kind"),
            showlegend=True,
        ))

    # Order legend entries explicitly
    legend_rank = {cat: i for i, cat in enumerate(colour_legend_order)}
    for tr in edge_traces:
        for cat, lbl in colour_legend_labels.items():
            if tr.name == lbl:
                tr.legendrank = legend_rank.get(cat, 99)
                break

    fig = go.Figure(data=[node_trace] + edge_traces)
    fig.update_layout(
        title=dict(
            text=(
                f"Cross-condition edge diff — <b>{story_id}</b>"
                "<br><sup>nodes at canonical positions · "
                "colour = which condition(s) support the edge · "
                "line style = predominant model kind  ·  "
                f"thresholds: cause ≥ {thr['cause']:g}, "
                f"enables ≥ {thr['enables']:g}</sup>"
            ),
            font=dict(size=15),
            x=0.02, xanchor="left",
        ),
        xaxis=dict(
            title="canonical chronological position",
            range=[0.3, n + 0.7],
            tickmode="array",
            tickvals=list(range(1, n + 1)),
            zeroline=False,
        ),
        yaxis=dict(
            range=[-(n * 0.55), n * 0.55],
            showticklabels=False,
            zeroline=True, zerolinewidth=1.5,
        ),
        height=620, width=1040,
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top", y=0.99,
            xanchor="left", x=1.02,
            font=dict(size=10, color=NIGHT_TEXT),
            title=dict(text="edge category", font=dict(size=10, color=NIGHT_TEXT)),
        ),
        margin=dict(l=60, r=240, t=90, b=70),
    )
    _apply_night_layout(fig)
    return fig


def render_per_trial_condition_diff(trial_dir: Path, stimuli: StimulusBundle,
                                    fig_subdir: str = "world_models") -> int:
    go = _plotly_or_none()
    if go is None:
        print("    (plotly not installed; skipping condition-diff views)")
        return 0
    parsed = trial_dir / "parsed"
    if not (parsed / "pair_scaling_matrices.json").exists():
        return 0
    matrices = json.loads((parsed / "pair_scaling_matrices.json").read_text())
    thresholds = get_thresholds(_trial_variant(trial_dir))
    fig_dir = trial_dir / "figures" / fig_subdir
    fig_dir.mkdir(exist_ok=True, parents=True)

    n_written = 0
    for sid in sorted({m["story_id"] for m in matrices}):
        story = stimuli.get_story(sid, "linear")
        chrono_ids = [ev.id for ev in story.events_chronological]
        cards = {ev.id: ev.card for ev in story.events_chronological}
        gold = stimuli.get_author_intended_graph(sid)
        fig = _build_diff_fig(sid, matrices, gold, cards, chrono_ids, go,
                              thresholds=thresholds)
        fig.write_html(
            fig_dir / f"condition_diff_{sid}.html",
            include_plotlyjs="cdn", full_html=True,
        )
        n_written += 1
    return n_written


# -----------------------------------------------------------------------------
# View 3: meta map (one node per run cell, positioned by MDS of pair-scaling RDM)
# -----------------------------------------------------------------------------

def _build_meta_map_fig(
    cells: list[dict],
    go,
    *,
    include_gold: bool = True,
    title_suffix: str = "",
    stimuli: StimulusBundle | None = None,
):
    """Render a meta map from a list of cell dicts.

    Each cell dict must carry:
        story_id, condition, seed, matrix, event_ids_chronological,
        and optionally `model_id`, `prompt_variant` (used at the sweep level).

    Cells are positioned by classical MDS of the 1 - Spearman ρ distance on
    their 56 off-diagonal pair-scaling cells. Gold reference points (one per
    story) are added when `include_gold=True` and a stimuli bundle is supplied.
    """
    if not cells:
        return None

    # Build vectors + labels
    vecs: list[np.ndarray] = []
    labels: list[dict] = []
    for c in cells:
        vecs.append(_matrix_to_vec(c["matrix"]))
        labels.append({
            "story_id":       c["story_id"],
            "condition":      c["condition"],
            "seed":           c.get("seed"),
            "model_id":       c.get("model_id"),
            "prompt_variant": c.get("prompt_variant"),
            "is_gold":        False,
        })

    if include_gold and stimuli is not None:
        for sid in sorted({c["story_id"] for c in cells}):
            gold = stimuli.get_author_intended_graph(sid)
            if gold is None:
                continue
            # Use the first matching cell's event-id ordering so axes align.
            any_cell = next(c for c in cells if c["story_id"] == sid)
            chrono_ids = any_cell["event_ids_chronological"]
            M = _synthesise_gold_matrix(gold, chrono_ids)
            vecs.append(_matrix_to_vec(M))
            labels.append({
                "story_id": sid, "condition": "gold", "seed": None,
                "model_id": None, "prompt_variant": None, "is_gold": True,
            })

    n = len(vecs)
    if n < 3:
        return None
    rdm = np.full((n, n), np.nan)
    for i in range(n):
        rdm[i, i] = 0.0
        for j in range(i + 1, n):
            d = _spearman_distance(vecs[i], vecs[j])
            rdm[i, j] = rdm[j, i] = d
    coords = _classical_mds(rdm, n_dims=3)

    # Plotly's 3D scatter supports a smaller symbol set than 2D:
    # circle, circle-open, square, square-open, diamond, diamond-open, cross, x.
    SYMBOL_LIST_3D = [
        "circle", "square", "diamond", "cross", "x",
        "circle-open", "square-open", "diamond-open",
    ]
    stories_seen = sorted({l["story_id"] for l in labels})
    story_symbol = {sid: SYMBOL_LIST_3D[i % len(SYMBOL_LIST_3D)]
                    for i, sid in enumerate(stories_seen)}

    fig = go.Figure()

    # Non-gold cells, grouped by condition for clean legend
    for cond in MODEL_CONDITIONS:
        for sid in stories_seen:
            xs, ys, zs, hovers = [], [], [], []
            for i, l in enumerate(labels):
                if l["is_gold"] or l["condition"] != cond or l["story_id"] != sid:
                    continue
                xs.append(coords[i, 0])
                ys.append(coords[i, 1])
                zs.append(coords[i, 2])
                pieces = [f"<b>{sid}</b>  ({cond})"]
                if l["seed"] is not None:
                    pieces.append(f"seed: {l['seed']}")
                if l["model_id"]:
                    pieces.append(f"model: {l['model_id']}")
                if l["prompt_variant"]:
                    pieces.append(f"prompt: {l['prompt_variant']}")
                hovers.append("<br>".join(pieces))
            if xs:
                fig.add_trace(go.Scatter3d(
                    x=xs, y=ys, z=zs, mode="markers",
                    marker=dict(
                        size=5,
                        color=CONDITION_COLORS[cond],
                        symbol=story_symbol[sid],
                        line=dict(width=0.6, color="white"),
                        opacity=0.88,
                    ),
                    name=f"{sid} · {cond}",
                    legendgroup=cond,
                    legendgrouptitle=dict(text=cond),
                    hovertext=hovers, hoverinfo="text",
                ))

    # Gold reference points
    gxs, gys, gzs, ghover, g_symbols = [], [], [], [], []
    for i, l in enumerate(labels):
        if not l["is_gold"]:
            continue
        gxs.append(coords[i, 0])
        gys.append(coords[i, 1])
        gzs.append(coords[i, 2])
        g_symbols.append(story_symbol[l["story_id"]])
        ghover.append(f"<b>{l['story_id']}</b><br>gold (author-intended)")
    if gxs:
        fig.add_trace(go.Scatter3d(
            x=gxs, y=gys, z=gzs, mode="markers",
            marker=dict(
                size=9, color=CONDITION_COLORS["gold"],
                symbol=g_symbols,
                line=dict(width=1.6, color="white"),
                opacity=1.0,
            ),
            name="gold (per story)",
            legendgroup="gold",
            legendgrouptitle=dict(text="reference"),
            hovertext=ghover, hoverinfo="text",
        ))

    fig.update_layout(
        title=dict(
            text=(
                "Meta map — pair-scaling matrices in 3-D MDS embedding"
                + (f" · {title_suffix}" if title_suffix else "")
                + "<br><sup>drag to rotate · scroll to zoom · "
                "distance = 1 − Spearman ρ on 56 off-diagonal cells · "
                "colour = condition · symbol = story · larger outlined markers = gold</sup>"
            ),
            font=dict(size=14, color=NIGHT_TEXT),
            x=0.02, xanchor="left",
        ),
        scene=dict(
            xaxis=dict(title="MDS dim 1 (a.u.)"),
            yaxis=dict(title="MDS dim 2 (a.u.)"),
            zaxis=dict(title="MDS dim 3 (a.u.)"),
            aspectmode="data",
            camera=dict(eye=dict(x=1.6, y=1.6, z=1.1)),
        ),
        height=760, width=1080,
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top", y=0.99,
            xanchor="left", x=1.02,
            font=dict(size=10, color=NIGHT_TEXT),
            groupclick="toggleitem",
        ),
        margin=dict(l=10, r=260, t=90, b=10),
    )
    _apply_night_layout(fig, is_3d=True)
    return fig


def render_trial_meta_map(trial_dir: Path, stimuli: StimulusBundle,
                          fig_subdir: str = "diagnostics") -> int:
    go = _plotly_or_none()
    if go is None:
        print("    (plotly not installed; skipping trial meta map)")
        return 0
    parsed = trial_dir / "parsed"
    path = parsed / "pair_scaling_matrices.json"
    if not path.exists():
        return 0
    matrices = json.loads(path.read_text())
    if not matrices:
        return 0
    fig = _build_meta_map_fig(
        matrices, go,
        include_gold=True,
        stimuli=stimuli,
        title_suffix=f"trial: {trial_dir.name}",
    )
    if fig is None:
        return 0
    fig_dir = trial_dir / "figures" / fig_subdir
    fig_dir.mkdir(exist_ok=True, parents=True)
    fig.write_html(
        fig_dir / "meta_map.html",
        include_plotlyjs="cdn", full_html=True,
    )
    return 1


# -----------------------------------------------------------------------------
# Sweep-level meta map (pools across all trials under a sweep root)
# -----------------------------------------------------------------------------

def _load_trial_cells(trial_dir: Path) -> list[dict]:
    """Read parsed/pair_scaling_matrices.json and tag each row with model_id /
    prompt_variant pulled from the trial's manifest.json (if present)."""
    parsed = trial_dir / "parsed"
    path = parsed / "pair_scaling_matrices.json"
    if not path.exists():
        return []
    matrices = json.loads(path.read_text())
    model_id = None
    prompt_variant = None
    manifest_path = trial_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
            model_id = manifest.get("model_id")
            prompt_variant = manifest.get("pair_scaling_variant")
        except Exception:
            pass
    for m in matrices:
        m["model_id"] = model_id
        m["prompt_variant"] = prompt_variant
        m["trial_dir"] = trial_dir.name
    return matrices


def render_sweep_meta_map(sweep_root: Path, stimuli: StimulusBundle) -> int:
    """Aggregate all trial cells under `sweep_root` and write `meta_map.html`."""
    go = _plotly_or_none()
    if go is None:
        print("    (plotly not installed; skipping sweep meta map)")
        return 0
    trials = sorted(
        p for p in sweep_root.glob("trial_*")
        if (p / "parsed" / "pair_scaling_matrices.json").exists()
    )
    if not trials:
        return 0
    cells: list[dict] = []
    for t in trials:
        cells.extend(_load_trial_cells(t))
    if not cells:
        return 0
    fig = _build_meta_map_fig(
        cells, go,
        include_gold=True,
        stimuli=stimuli,
        title_suffix=f"sweep: {sweep_root.name}  ·  {len(trials)} trial(s), "
                     f"{len(cells)} cell(s)",
    )
    if fig is None:
        return 0
    fig.write_html(
        sweep_root / "meta_map.html",
        include_plotlyjs="cdn", full_html=True,
    )
    return 1


# -----------------------------------------------------------------------------
# Convenience: render all per-trial interactive views in one call
# -----------------------------------------------------------------------------

def render_all_interactive(trial_dir: Path, stimuli: StimulusBundle) -> None:
    """Drive all per-trial interactive renders. Safe to call repeatedly."""
    if _plotly_or_none() is None:
        print("    (plotly not installed; install with `pip install plotly` to enable "
              "interactive HTML views)")
        return
    n_wm  = render_per_trial_world_models(trial_dir, stimuli)
    n_df  = render_per_trial_condition_diff(trial_dir, stimuli)
    n_mm  = render_trial_meta_map(trial_dir, stimuli)
    print(f"    interactive: world_models={n_wm}, condition_diff={n_df}, meta_map={n_mm}")
