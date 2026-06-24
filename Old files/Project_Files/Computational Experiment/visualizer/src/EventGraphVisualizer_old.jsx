import { useState, useEffect, useRef, useCallback } from "react";
import * as d3 from "d3";

const GOLD_STANDARD = {
  domains: {
    medical: {
      events: [
        { id: "E1", description: "A hospital administrator approves a policy reducing overnight staffing.", canonical_position: 1, time_to_next: "long" },
        { id: "E2", description: "A contractor disables a ventilator alarm during maintenance.", canonical_position: 2, time_to_next: "immediate" },
        { id: "E3", description: "The contractor leaves without re-enabling the alarm.", canonical_position: 3, time_to_next: "short" },
        { id: "E4", description: "A nurse is assigned more patients than usual.", canonical_position: 4, time_to_next: "short" },
        { id: "E5", description: "A brief power interruption occurs.", canonical_position: 5, time_to_next: "immediate" },
        { id: "E6", description: "The ventilator stops without sounding an alarm.", canonical_position: 6, time_to_next: "short" },
        { id: "E7", description: "The nurse discovers a patient in respiratory distress.", canonical_position: 7, time_to_next: "long" },
        { id: "E8", description: "An inquest later reviews the incident.", canonical_position: 8, time_to_next: null },
      ],
      edges: [
        { source: "E1", target: "E4", type: "causal", subtype: "enables" },
        { source: "E2", target: "E3", type: "causal", subtype: "enables" },
        { source: "E3", target: "E6", type: "causal", subtype: "enables" },
        { source: "E5", target: "E6", type: "causal", subtype: "causes" },
        { source: "E6", target: "E7", type: "causal", subtype: "causes" },
        { source: "E4", target: "E7", type: "causal", subtype: "enables" },
        { source: "E7", target: "E8", type: "causal", subtype: "causes" },
      ],
    },
    workplace: {
      events: [
        { id: "E1", description: "A manager approves a plan to consolidate server resources.", canonical_position: 1, time_to_next: "long" },
        { id: "E2", description: "A technician updates configuration settings on a backup system.", canonical_position: 2, time_to_next: "immediate" },
        { id: "E3", description: "The technician does not restart one service.", canonical_position: 3, time_to_next: "short" },
        { id: "E4", description: "An analyst begins processing a large dataset.", canonical_position: 4, time_to_next: "immediate" },
        { id: "E5", description: "System load increases across the network.", canonical_position: 5, time_to_next: "immediate" },
        { id: "E6", description: "A critical service stops responding.", canonical_position: 6, time_to_next: "short" },
        { id: "E7", description: "Users report being unable to access shared files.", canonical_position: 7, time_to_next: "long" },
        { id: "E8", description: "An internal review examines the incident.", canonical_position: 8, time_to_next: null },
      ],
      edges: [
        { source: "E1", target: "E4", type: "causal", subtype: "enables" },
        { source: "E2", target: "E3", type: "causal", subtype: "enables" },
        { source: "E3", target: "E6", type: "causal", subtype: "enables" },
        { source: "E4", target: "E5", type: "causal", subtype: "causes" },
        { source: "E5", target: "E6", type: "causal", subtype: "causes" },
        { source: "E6", target: "E7", type: "causal", subtype: "causes" },
        { source: "E4", target: "E7", type: "causal", subtype: "enables" },
        { source: "E7", target: "E8", type: "causal", subtype: "causes" },
      ],
    },
    coastal: {
      events: [
        { id: "E1", description: "A city council approves a pilot floodgate project for a coastal road.", canonical_position: 1, time_to_next: "medium" },
        { id: "E2", description: "Contractors install temporary barriers and signage near the road.", canonical_position: 2, time_to_next: "medium" },
        { id: "E3", description: "A utilities team schedules a routine inspection of a pump station.", canonical_position: 3, time_to_next: "short" },
        { id: "E4", description: "The inspection requires a temporary shutdown of the pump station.", canonical_position: 4, time_to_next: "medium" },
        { id: "E5", description: "A weather service issues a coastal surge warning.", canonical_position: 5, time_to_next: "short" },
        { id: "E6", description: "The floodgate is activated during the warning period.", canonical_position: 6, time_to_next: "short" },
        { id: "E7", description: "Water enters the road area and traffic is halted.", canonical_position: 7, time_to_next: "long" },
        { id: "E8", description: "A municipal review later examines the sequence of events.", canonical_position: 8, time_to_next: null },
      ],
      edges: [
        { source: "E1", target: "E2", type: "causal", subtype: "causes" },
        { source: "E1", target: "E6", type: "causal", subtype: "enables" },
        { source: "E3", target: "E4", type: "causal", subtype: "causes" },
        { source: "E4", target: "E7", type: "causal", subtype: "enables" },
        { source: "E5", target: "E6", type: "causal", subtype: "causes" },
        { source: "E5", target: "E7", type: "causal", subtype: "causes" },
        { source: "E6", target: "E7", type: "causal", subtype: "enables" },
        { source: "E7", target: "E8", type: "causal", subtype: "causes" },
      ],
    },
  },
};

const C = {
  bg: "#0a0e17", surface: "#111827", surfaceAlt: "#1a2234",
  border: "#1e293b", text: "#e2e8f0", textMuted: "#94a3b8", textDim: "#64748b",
  causes: "#f472b6", enables: "#a78bfa",
  node: "#1e293b", nodeStroke: "#334155", nodeHover: "#263249", accent: "#38bdf8",
  green: "#34d399", yellow: "#fbbf24", red: "#f87171",
};

const SPACING = { immediate: 80, short: 130, medium: 190, long: 280 };
const MONO = "'JetBrains Mono', monospace";

export default function EventGraphVisualizer() {
  const [domain, setDomain] = useState("medical");
  const [showCauses, setShowCauses] = useState(true);
  const [showEnables, setShowEnables] = useState(true);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [viewMode, setViewMode] = useState("gold");
  const [compareMode, setCompareMode] = useState(false);
  const [layoutMode, setLayoutMode] = useState("canonical");
  const [customGraph, setCustomGraph] = useState(null);
  const [evalData, setEvalData] = useState(null);
  const [inputTab, setInputTab] = useState("graph");
  const [graphInput, setGraphInput] = useState("");
  const [evalInput, setEvalInput] = useState("");
  const [parseError, setParseError] = useState(null);
  const svgRef = useRef(null);
  const compareSvgRef = useRef(null);

  const currentData = viewMode === "custom" && customGraph
    ? customGraph.domains?.[domain] || customGraph
    : GOLD_STANDARD.domains[domain];

  // Which eval result to display (prefer revised, fall back to incremental)
  const activeEval = evalData?.revised_graph || evalData?.incremental_graph || null;
  const idMapping = activeEval?.event_matching?.mapping || {};
  const reverseMapping = Object.fromEntries(Object.entries(idMapping).map(([k, v]) => [v, k]));

  const handleLoadGraph = () => {
    try {
      const parsed = JSON.parse(graphInput);
      if (parsed.domains) setCustomGraph(parsed);
      else if (parsed.events && parsed.edges) setCustomGraph({ domains: { [domain]: parsed } });
      else throw new Error("Need 'domains' or 'events'+'edges'");
      setParseError(null);
      setViewMode("custom");
    } catch (e) { setParseError(e.message); }
  };

  const handleLoadEval = () => {
    try {
      const parsed = JSON.parse(evalInput);
      if (parsed.incremental_graph || parsed.revised_graph) {
        setEvalData(parsed);
        setParseError(null);
      } else throw new Error("Need 'incremental_graph' or 'revised_graph' key");
    } catch (e) { setParseError(e.message); }
  };

  const computePositions = useCallback((data, width, height) => {
    const events = data.events;
    const positions = {};
    const px = 70;

    if (layoutMode === "canonical") {
      const sorted = [...events].sort((a, b) => (a.canonical_position || 0) - (b.canonical_position || 0));
      let cx = px;
      const xs = [cx];
      for (let i = 1; i < sorted.length; i++) {
        cx += SPACING[sorted[i - 1].time_to_next] || 130;
        xs.push(cx);
      }
      const scale = Math.min(1, (width - px * 2) / (cx));
      const off = (width - (cx * scale + px)) / 2;

      const causalEdges = data.edges.filter(e => e.type === "causal");
      const yOff = {};
      events.forEach(ev => { yOff[ev.id] = 0; });
      const srcs = {};
      causalEdges.forEach(e => { (srcs[e.target] ||= []).push(e.source); });
      Object.keys(srcs).filter(k => srcs[k].length > 1).forEach(tgt => {
        const tIdx = sorted.findIndex(e => e.id === tgt);
        srcs[tgt].forEach((src, i) => {
          const sIdx = sorted.findIndex(e => e.id === src);
          if (tIdx - sIdx > 1) yOff[src] = (i % 2 === 0 ? -1 : 1) * 40;
        });
      });
      sorted.forEach((ev, i) => {
        positions[ev.id] = { x: xs[i] * scale + off + px / 2, y: height / 2 + yOff[ev.id] };
      });
    } else {
      // Encounter order: sort by numeric ID (E1, E2, E3...) since IDs are assigned in encounter order
      const byEncounter = [...events].sort((a, b) => {
        const numA = parseInt(a.id.replace(/\D/g, "")) || 0;
        const numB = parseInt(b.id.replace(/\D/g, "")) || 0;
        return numA - numB;
      });
      const step = Math.min(130, (width - px * 2) / Math.max(byEncounter.length - 1, 1));
      byEncounter.forEach((ev, i) => {
        positions[ev.id] = { x: px + i * step, y: height / 2 };
      });
    }
    return positions;
  }, [layoutMode]);

  const renderGraph = useCallback((svgEl, data, positions, opts = {}) => {
    if (!svgEl || !data) return;
    const { isCompare = false, mapping = null } = opts;
    const svg = d3.select(svgEl);
    svg.selectAll("*").remove();

    const defs = svg.append("defs");
    [{ id: "arrow-causes", color: C.causes }, { id: "arrow-enables", color: C.enables }].forEach(({ id, color }) => {
      defs.append("marker").attr("id", `${id}${isCompare ? "-c" : ""}`).attr("viewBox", "0 0 10 6")
        .attr("refX", 10).attr("refY", 3).attr("markerWidth", 8).attr("markerHeight", 5).attr("orient", "auto")
        .append("path").attr("d", "M0,0 L10,3 L0,6 Z").attr("fill", color);
    });

    const g = svg.append("g");
    const edgeG = g.append("g");
    const nodeG = g.append("g");

    // Temporal spine
    const sorted = [...data.events].sort((a, b) => (a.canonical_position || 0) - (b.canonical_position || 0));
    for (let i = 0; i < sorted.length - 1; i++) {
      const s = positions[sorted[i].id], t = positions[sorted[i + 1].id];
      if (!s || !t) continue;
      const dx = t.x - s.x, dy = t.y - s.y, d = Math.sqrt(dx * dx + dy * dy);
      if (d === 0) continue;
      const r = 22;
      edgeG.append("line")
        .attr("x1", s.x + dx / d * r).attr("y1", s.y + dy / d * r)
        .attr("x2", t.x - dx / d * r).attr("y2", t.y - dy / d * r)
        .attr("stroke", C.textDim).attr("stroke-width", 1).attr("stroke-opacity", 0.25).attr("stroke-dasharray", "3,4");
      const label = sorted[i].time_to_next;
      if (label) {
        edgeG.append("text").attr("x", (s.x + t.x) / 2).attr("y", (s.y + t.y) / 2 - 10)
          .attr("text-anchor", "middle").attr("fill", C.textDim).attr("font-size", "9px").attr("font-family", MONO).text(label);
      }
    }

    // Causal edges
    data.edges.filter(e => e.type === "causal" && ((e.subtype === "causes" && showCauses) || (e.subtype === "enables" && showEnables)))
      .forEach((edge, i) => {
        const s = positions[edge.source], t = positions[edge.target];
        if (!s || !t) return;
        const dx = t.x - s.x, dy = t.y - s.y, d = Math.sqrt(dx * dx + dy * dy);
        if (d === 0) return;
        const r = 22, isCauses = edge.subtype === "causes", color = isCauses ? C.causes : C.enables;
        const x1 = s.x + dx / d * r, y1 = s.y + dy / d * r, x2 = t.x - dx / d * (r + 8), y2 = t.y - dy / d * (r + 8);
        const arc = Math.abs(dy) < 20 ? -40 - (i % 3) * 15 : 0;
        edgeG.append("path")
          .attr("d", `M${x1},${y1} Q${(x1 + x2) / 2},${(y1 + y2) / 2 + arc} ${x2},${y2}`)
          .attr("fill", "none").attr("stroke", color).attr("stroke-width", 1.5).attr("stroke-opacity", 0.6)
          .attr("stroke-dasharray", edge.subtype === "enables" ? "6,4" : "none")
          .attr("marker-end", `url(#${isCauses ? "arrow-causes" : "arrow-enables"}${isCompare ? "-c" : ""})`);
      });

    // Nodes
    data.events.forEach(ev => {
      const pos = positions[ev.id];
      if (!pos) return;
      const hov = (opts.highlightId || hoveredNode) === ev.id;

      nodeG.append("circle").attr("cx", pos.x).attr("cy", pos.y).attr("r", hov ? 26 : 22)
        .attr("fill", hov ? C.nodeHover : C.node).attr("stroke", hov ? C.accent : C.nodeStroke)
        .attr("stroke-width", hov ? 2 : 1.5).style("cursor", "pointer");

      // Main ID label
      nodeG.append("text").attr("x", pos.x).attr("y", pos.y + (mapping ? -2 : 1))
        .attr("text-anchor", "middle").attr("dominant-baseline", "central")
        .attr("fill", hov ? C.accent : C.text).attr("font-size", "12px").attr("font-weight", "600")
        .attr("font-family", MONO).text(ev.id).style("pointer-events", "none");

      // Gold ID mapping label (shown on model graph when eval is loaded)
      if (mapping && mapping[ev.id]) {
        nodeG.append("text").attr("x", pos.x).attr("y", pos.y + 10)
          .attr("text-anchor", "middle").attr("dominant-baseline", "central")
          .attr("fill", C.green).attr("font-size", "8px").attr("font-weight", "500")
          .attr("font-family", MONO).attr("opacity", 0.8)
          .text(`→${mapping[ev.id]}`).style("pointer-events", "none");
      }
    });
  }, [showCauses, showEnables, hoveredNode]);

  useEffect(() => {
    if (!svgRef.current) return;
    const w = svgRef.current.clientWidth, h = svgRef.current.clientHeight;
    const showMapping = viewMode === "custom" && activeEval ? idMapping : null;
    renderGraph(svgRef.current, currentData, computePositions(currentData, w, h), { mapping: showMapping });
  }, [currentData, renderGraph, computePositions, viewMode, activeEval, idMapping]);

  useEffect(() => {
    if (!compareMode || !compareSvgRef.current || !customGraph) return;
    const gold = GOLD_STANDARD.domains[domain];
    const w = compareSvgRef.current.clientWidth, h = compareSvgRef.current.clientHeight;
    // When hovering a model node, highlight the mapped gold node in the compare graph
    const mappedGoldId = hoveredNode && idMapping[hoveredNode] ? idMapping[hoveredNode] : null;
    renderGraph(compareSvgRef.current, gold, computePositions(gold, w, h), { isCompare: true, highlightId: mappedGoldId });
  }, [compareMode, domain, customGraph, renderGraph, computePositions, hoveredNode, idMapping]);

  const hoveredEvent = hoveredNode ? currentData.events.find(e => e.id === hoveredNode) : null;
  const connectedEdges = hoveredNode
    ? currentData.edges.filter(e => (e.source === hoveredNode || e.target === hoveredNode) && ((e.subtype === "causes" && showCauses) || (e.subtype === "enables" && showEnables)))
    : [];

  // --- Metric bar helper ---
  const MetricBar = ({ label, value, max = 1 }) => {
    const pct = Math.round(value * 100);
    const color = pct >= 80 ? C.green : pct >= 50 ? C.yellow : C.red;
    return (
      <div style={{ marginBottom: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
          <span style={{ fontSize: 10, color: C.textMuted, fontFamily: MONO }}>{label}</span>
          <span style={{ fontSize: 10, color, fontFamily: MONO, fontWeight: 600 }}>{pct}%</span>
        </div>
        <div style={{ height: 3, background: C.surfaceAlt, borderRadius: 2 }}>
          <div style={{ height: 3, width: `${pct}%`, background: color, borderRadius: 2, transition: "width 0.3s ease" }} />
        </div>
      </div>
    );
  };

  const Pill = ({ children, color = C.textDim }) => (
    <span style={{ fontSize: 9, color, fontFamily: MONO, padding: "1px 6px", borderRadius: 3, border: `1px solid ${color}30`, background: `${color}10` }}>{children}</span>
  );

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, fontFamily: "'Inter', -apple-system, sans-serif", padding: "24px" }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@400;500;600&display=swap');`}</style>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ marginBottom: 20 }}>
          <h1 style={{ fontSize: 18, fontWeight: 600, fontFamily: MONO, margin: 0, letterSpacing: "-0.02em" }}>Event Graph Visualizer</h1>
          <p style={{ fontSize: 11, color: C.textDim, margin: "4px 0 0", fontFamily: MONO }}>v0.2 · Temporal on nodes · Causal edges only</p>
        </div>

        {/* Controls */}
        <div style={{ display: "flex", gap: 6, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
          {["medical", "workplace", "coastal"].map(d => (
            <button key={d} onClick={() => setDomain(d)} style={{
              padding: "5px 12px", borderRadius: 5, border: `1px solid ${domain === d ? C.accent : C.border}`,
              background: domain === d ? `${C.accent}18` : "transparent", color: domain === d ? C.accent : C.textMuted,
              fontSize: 11, fontFamily: MONO, fontWeight: 500, cursor: "pointer",
            }}>{d}</button>
          ))}
          <div style={{ width: 1, height: 20, background: C.border, margin: "0 2px" }} />
          {[{ l: "causes", a: showCauses, t: () => setShowCauses(!showCauses), c: C.causes },
            { l: "enables", a: showEnables, t: () => setShowEnables(!showEnables), c: C.enables }].map(({ l, a, t, c }) => (
            <button key={l} onClick={t} style={{
              display: "flex", alignItems: "center", gap: 5, padding: "5px 10px", borderRadius: 5,
              border: `1px solid ${a ? c : C.border}`, background: a ? `${c}15` : "transparent",
              color: a ? c : C.textDim, fontSize: 10, fontFamily: MONO, cursor: "pointer",
            }}>
              <span style={{ width: 14, height: 0, display: "block", borderBottom: `2px ${l === "enables" ? "dashed" : "solid"} ${a ? c : C.textDim}` }} />
              {l}
            </button>
          ))}
          <div style={{ width: 1, height: 20, background: C.border, margin: "0 2px" }} />
          {["gold", "custom"].map(v => (
            <button key={v} onClick={() => setViewMode(v)} style={{
              padding: "5px 10px", borderRadius: 5, border: `1px solid ${viewMode === v ? C.accent : C.border}`,
              background: viewMode === v ? `${C.accent}18` : "transparent", color: viewMode === v ? C.accent : C.textMuted,
              fontSize: 10, fontFamily: MONO, cursor: "pointer",
            }}>{v === "gold" ? "gold standard" : "model output"}</button>
          ))}
          {customGraph && (
            <button onClick={() => setCompareMode(!compareMode)} style={{
              padding: "5px 10px", borderRadius: 5, border: `1px solid ${compareMode ? C.yellow : C.border}`,
              background: compareMode ? `${C.yellow}15` : "transparent", color: compareMode ? C.yellow : C.textMuted,
              fontSize: 10, fontFamily: MONO, cursor: "pointer",
            }}>compare</button>
          )}
          <div style={{ width: 1, height: 20, background: C.border, margin: "0 2px" }} />
          {["canonical", "encounter"].map(l => (
            <button key={l} onClick={() => setLayoutMode(l)} style={{
              padding: "5px 10px", borderRadius: 5, border: `1px solid ${layoutMode === l ? C.green : C.border}`,
              background: layoutMode === l ? `${C.green}15` : "transparent", color: layoutMode === l ? C.green : C.textMuted,
              fontSize: 10, fontFamily: MONO, cursor: "pointer",
            }}>{l === "canonical" ? "chronological" : "encounter order"}</button>
          ))}
        </div>

        {/* Main graph */}
        <div style={{ background: C.surface, borderRadius: 8, border: `1px solid ${C.border}`, overflow: "hidden", marginBottom: 10 }}>
          <div style={{ padding: "6px 12px", borderBottom: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: 10, color: C.textDim, fontFamily: MONO }}>
              {viewMode === "gold" ? "gold standard" : "model output"} · {domain}
              {viewMode === "custom" && activeEval && <span style={{ color: C.green, marginLeft: 8 }}>● eval loaded</span>}
            </span>
            <span style={{ fontSize: 10, color: C.textDim, fontFamily: MONO }}>
              {currentData.events.length} events · {currentData.edges.filter(e => (e.subtype === "causes" && showCauses) || (e.subtype === "enables" && showEnables)).length} edges
            </span>
          </div>
          <svg ref={svgRef} width="100%" height={260} style={{ display: "block" }}
            onMouseMove={e => {
              const svg = svgRef.current; if (!svg) return;
              const rect = svg.getBoundingClientRect();
              const mx = e.clientX - rect.left, my = e.clientY - rect.top;
              const pos = computePositions(currentData, svg.clientWidth, svg.clientHeight);
              let found = null;
              currentData.events.forEach(ev => { if (Math.hypot(mx - pos[ev.id].x, my - pos[ev.id].y) < 28) found = ev.id; });
              setHoveredNode(found);
            }}
            onMouseLeave={() => setHoveredNode(null)}
          />
        </div>

        {/* Compare */}
        {compareMode && customGraph && (
          <div style={{ background: C.surface, borderRadius: 8, border: `1px solid ${C.border}`, overflow: "hidden", marginBottom: 10 }}>
            <div style={{ padding: "6px 12px", borderBottom: `1px solid ${C.border}` }}>
              <span style={{ fontSize: 10, color: C.textDim, fontFamily: MONO }}>gold standard · {domain} (reference)</span>
            </div>
            <svg ref={compareSvgRef} width="100%" height={220} style={{ display: "block" }} />
          </div>
        )}

        {/* Bottom panels */}
        <div style={{ display: "grid", gridTemplateColumns: activeEval ? "1fr 1fr 1fr" : "1fr 1fr", gap: 10 }}>

          {/* Panel 1: Node inspector */}
          <div style={{ background: C.surface, borderRadius: 8, border: `1px solid ${C.border}`, padding: 14, minHeight: 170 }}>
            {hoveredEvent ? (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
                  <Pill color={C.accent}>{hoveredEvent.id}</Pill>
                  {viewMode === "custom" && idMapping[hoveredEvent.id] && (
                    <Pill color={C.green}>gold {idMapping[hoveredEvent.id]}</Pill>
                  )}
                  <span style={{ fontSize: 9, color: C.textDim, fontFamily: MONO }}>
                    pos {hoveredEvent.canonical_position} · {hoveredEvent.time_to_next || "last"}
                  </span>
                </div>
                <p style={{ fontSize: 12, color: C.text, lineHeight: 1.5, margin: "0 0 10px" }}>{hoveredEvent.description}</p>
                {connectedEdges.length > 0 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                    {connectedEdges.map((e, i) => {
                      const color = e.subtype === "causes" ? C.causes : C.enables;
                      const dir = e.source === hoveredNode ? "→" : "←";
                      const other = e.source === hoveredNode ? e.target : e.source;
                      const goldOther = idMapping[other];
                      return (
                        <div key={i} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 10, fontFamily: MONO }}>
                          <span style={{ color, minWidth: 50 }}>{e.subtype}</span>
                          <span style={{ color: C.textDim }}>{dir}</span>
                          <span style={{ color: C.text }}>{other}</span>
                          {goldOther && <span style={{ color: C.green, fontSize: 9 }}>({goldOther})</span>}
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            ) : (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", minHeight: 100 }}>
                <span style={{ fontSize: 11, color: C.textDim, fontFamily: MONO }}>hover over a node</span>
              </div>
            )}
          </div>

          {/* Panel 2: Evaluation metrics (shown when eval loaded) OR expanded input */}
          {activeEval && (
            <div style={{ background: C.surface, borderRadius: 8, border: `1px solid ${C.border}`, padding: 14, minHeight: 170 }}>
              <div style={{ fontSize: 10, color: C.textDim, fontFamily: MONO, marginBottom: 10 }}>
                evaluation · {activeEval === evalData?.revised_graph ? "revised" : "incremental"}
              </div>

              <MetricBar label="pairwise ordering" value={activeEval.ordering?.pairwise_accuracy || 0} />
              <MetricBar label="temporal labels" value={activeEval.temporal_labels?.accuracy || 0} />
              <MetricBar label="causal F1 (strict)" value={activeEval.causal_edges?.strict?.f1 || 0} />
              <MetricBar label="causal F1 (relaxed)" value={activeEval.causal_edges?.relaxed?.f1 || 0} />

              <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
                <Pill color={C.text}>{activeEval.model_event_count}/{activeEval.gold_event_count} events</Pill>
                <Pill color={C.text}>{activeEval.model_edge_count}/{activeEval.gold_edge_count} edges</Pill>
                {activeEval.event_matching?.unmatched_gold?.length > 0 && (
                  <Pill color={C.red}>missing: {activeEval.event_matching.unmatched_gold.join(", ")}</Pill>
                )}
              </div>

              {/* Event mapping table */}
              <div style={{ marginTop: 10, borderTop: `1px solid ${C.border}`, paddingTop: 8 }}>
                <div style={{ fontSize: 9, color: C.textDim, fontFamily: MONO, marginBottom: 4 }}>id mapping</div>
                {Object.entries(activeEval.event_matching?.match_scores || {}).map(([mId, info]) => (
                  <div key={mId} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 9, fontFamily: MONO, marginBottom: 2 }}>
                    <span style={{ color: C.textMuted, minWidth: 22 }}>{mId}</span>
                    <span style={{ color: C.green }}>→</span>
                    <span style={{ color: C.green, minWidth: 22 }}>{info.gold_id}</span>
                    <span style={{ color: C.textDim }}>({Math.round(info.similarity * 100)}%)</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Panel 3 (or 2): Input area */}
          <div style={{ background: C.surface, borderRadius: 8, border: `1px solid ${C.border}`, padding: 14, minHeight: 170, display: "flex", flexDirection: "column" }}>
            {/* Tabs */}
            <div style={{ display: "flex", gap: 4, marginBottom: 8 }}>
              {[{ key: "graph", label: "model json" }, { key: "eval", label: "evaluation" }].map(({ key, label }) => (
                <button key={key} onClick={() => { setInputTab(key); setParseError(null); }} style={{
                  padding: "3px 8px", borderRadius: 4, border: `1px solid ${inputTab === key ? C.accent : C.border}`,
                  background: inputTab === key ? `${C.accent}15` : "transparent",
                  color: inputTab === key ? C.accent : C.textDim, fontSize: 9, fontFamily: MONO, cursor: "pointer",
                }}>{label}{key === "eval" && evalData && <span style={{ color: C.green, marginLeft: 4 }}>●</span>}</button>
              ))}
              <div style={{ flex: 1 }} />
              <button onClick={inputTab === "graph" ? handleLoadGraph : handleLoadEval} style={{
                padding: "3px 10px", borderRadius: 4, border: `1px solid ${C.accent}`, background: `${C.accent}15`,
                color: C.accent, fontSize: 9, fontFamily: MONO, cursor: "pointer",
              }}>load</button>
            </div>
            <textarea
              value={inputTab === "graph" ? graphInput : evalInput}
              onChange={e => inputTab === "graph" ? setGraphInput(e.target.value) : setEvalInput(e.target.value)}
              placeholder={inputTab === "graph" ? '{"events": [...], "edges": [...]}' : 'paste evaluation.json contents'}
              style={{
                flex: 1, background: C.surfaceAlt, border: `1px solid ${parseError ? C.red : C.border}`,
                borderRadius: 5, color: C.text, fontFamily: MONO, fontSize: 10, padding: 8,
                resize: "none", outline: "none", lineHeight: 1.5,
              }}
            />
            {parseError && <span style={{ fontSize: 9, color: C.red, fontFamily: MONO, marginTop: 3 }}>{parseError}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
