import { useState, useEffect, useRef, useCallback } from "react";
import * as d3 from "d3";

const GOLD_STANDARD = {
  temporal_distance_scale: {
    immediate: { label: "Minutes / same scene", spacing: 1 },
    short: { label: "Hours / same day", spacing: 2 },
    medium: { label: "Days", spacing: 3 },
    long: { label: "Weeks or more", spacing: 4.5 },
  },
  domains: {
    medical: {
      events: [
        { id: "E1", description: "A hospital administrator approves a policy reducing overnight staffing.", canonical_position: 1 },
        { id: "E2", description: "A contractor disables a ventilator alarm during maintenance.", canonical_position: 2 },
        { id: "E3", description: "The contractor leaves without re-enabling the alarm.", canonical_position: 3 },
        { id: "E4", description: "A nurse is assigned more patients than usual.", canonical_position: 4 },
        { id: "E5", description: "A brief power interruption occurs.", canonical_position: 5 },
        { id: "E6", description: "The ventilator stops without sounding an alarm.", canonical_position: 6 },
        { id: "E7", description: "The nurse discovers a patient in respiratory distress.", canonical_position: 7 },
        { id: "E8", description: "An inquest later reviews the incident.", canonical_position: 8 },
      ],
      edges: [
        { source: "E1", target: "E2", type: "temporal", relation: "before", distance: "long" },
        { source: "E2", target: "E3", type: "temporal", relation: "before", distance: "immediate" },
        { source: "E3", target: "E4", type: "temporal", relation: "before", distance: "short" },
        { source: "E4", target: "E5", type: "temporal", relation: "before", distance: "short" },
        { source: "E5", target: "E6", type: "temporal", relation: "before", distance: "immediate" },
        { source: "E6", target: "E7", type: "temporal", relation: "before", distance: "short" },
        { source: "E7", target: "E8", type: "temporal", relation: "before", distance: "long" },
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
        { id: "E1", description: "A manager approves a plan to consolidate server resources.", canonical_position: 1 },
        { id: "E2", description: "A technician updates configuration settings on a backup system.", canonical_position: 2 },
        { id: "E3", description: "The technician does not restart one service.", canonical_position: 3 },
        { id: "E4", description: "An analyst begins processing a large dataset.", canonical_position: 4 },
        { id: "E5", description: "System load increases across the network.", canonical_position: 5 },
        { id: "E6", description: "A critical service stops responding.", canonical_position: 6 },
        { id: "E7", description: "Users report being unable to access shared files.", canonical_position: 7 },
        { id: "E8", description: "An internal review examines the incident.", canonical_position: 8 },
      ],
      edges: [
        { source: "E1", target: "E2", type: "temporal", relation: "before", distance: "long" },
        { source: "E2", target: "E3", type: "temporal", relation: "before", distance: "immediate" },
        { source: "E3", target: "E4", type: "temporal", relation: "before", distance: "short" },
        { source: "E4", target: "E5", type: "temporal", relation: "before", distance: "immediate" },
        { source: "E5", target: "E6", type: "temporal", relation: "before", distance: "immediate" },
        { source: "E6", target: "E7", type: "temporal", relation: "before", distance: "short" },
        { source: "E7", target: "E8", type: "temporal", relation: "before", distance: "long" },
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
        { id: "E1", description: "A city council approves a pilot floodgate project for a coastal road.", canonical_position: 1 },
        { id: "E2", description: "Contractors install temporary barriers and signage near the road.", canonical_position: 2 },
        { id: "E3", description: "A utilities team schedules a routine inspection of a pump station.", canonical_position: 3 },
        { id: "E4", description: "The inspection requires a temporary shutdown of the pump station.", canonical_position: 4 },
        { id: "E5", description: "A weather service issues a coastal surge warning.", canonical_position: 5 },
        { id: "E6", description: "The floodgate is activated during the warning period.", canonical_position: 6 },
        { id: "E7", description: "Water enters the road area and traffic is halted.", canonical_position: 7 },
        { id: "E8", description: "A municipal review later examines the sequence of events.", canonical_position: 8 },
      ],
      edges: [
        { source: "E1", target: "E2", type: "temporal", relation: "before", distance: "medium" },
        { source: "E2", target: "E3", type: "temporal", relation: "before", distance: "medium" },
        { source: "E3", target: "E4", type: "temporal", relation: "before", distance: "short" },
        { source: "E4", target: "E5", type: "temporal", relation: "before", distance: "medium" },
        { source: "E5", target: "E6", type: "temporal", relation: "before", distance: "short" },
        { source: "E6", target: "E7", type: "temporal", relation: "before", distance: "short" },
        { source: "E7", target: "E8", type: "temporal", relation: "before", distance: "long" },
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

const COLORS = {
  bg: "#0a0e17",
  surface: "#111827",
  surfaceAlt: "#1a2234",
  border: "#1e293b",
  borderHover: "#334155",
  text: "#e2e8f0",
  textMuted: "#94a3b8",
  textDim: "#64748b",
  temporal: "#38bdf8",
  temporalMuted: "rgba(56, 189, 248, 0.15)",
  causes: "#f472b6",
  causesMuted: "rgba(244, 114, 182, 0.15)",
  enables: "#a78bfa",
  enablesMuted: "rgba(167, 139, 250, 0.15)",
  node: "#1e293b",
  nodeStroke: "#334155",
  nodeHover: "#263249",
  accent: "#38bdf8",
};

const DISTANCE_SPACING = { immediate: 80, short: 130, medium: 190, long: 280 };

export default function EventGraphVisualizer() {
  const [domain, setDomain] = useState("medical");
  const [showTemporal, setShowTemporal] = useState(true);
  const [showCauses, setShowCauses] = useState(true);
  const [showEnables, setShowEnables] = useState(true);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [hoveredEdge, setHoveredEdge] = useState(null);
  const [jsonInput, setJsonInput] = useState("");
  const [customGraph, setCustomGraph] = useState(null);
  const [parseError, setParseError] = useState(null);
  const [viewMode, setViewMode] = useState("gold");
  const [compareMode, setCompareMode] = useState(false);
  const svgRef = useRef(null);
  const compareSvgRef = useRef(null);

  const currentData =
    viewMode === "custom" && customGraph
      ? customGraph.domains?.[domain] || customGraph
      : GOLD_STANDARD.domains[domain];

  const handleJsonParse = () => {
    try {
      const parsed = JSON.parse(jsonInput);
      if (parsed.domains) {
        setCustomGraph(parsed);
      } else if (parsed.events && parsed.edges) {
        setCustomGraph({ domains: { [domain]: parsed } });
      } else {
        throw new Error("JSON must have 'domains' or 'events'+'edges'");
      }
      setParseError(null);
      setViewMode("custom");
    } catch (e) {
      setParseError(e.message);
    }
  };

  const computeNodePositions = useCallback((data, width, height) => {
    const events = data.events;
    const temporalEdges = data.edges.filter((e) => e.type === "temporal");
    const positions = {};
    const paddingX = 70;
    const paddingY = 60;

    let cumulativeX = paddingX;
    const xPositions = [cumulativeX];
    for (let i = 0; i < temporalEdges.length; i++) {
      const dist = temporalEdges[i].distance || "short";
      cumulativeX += DISTANCE_SPACING[dist] || 130;
      xPositions.push(cumulativeX);
    }

    const totalWidth = cumulativeX + paddingX;
    const scale = Math.min(1, (width - paddingX * 2) / (totalWidth - paddingX * 2));
    const offsetX = (width - (cumulativeX * scale + paddingX)) / 2;

    const causalEdges = data.edges.filter((e) => e.type === "causal");
    const yOffsets = {};
    events.forEach((ev) => { yOffsets[ev.id] = 0; });

    const causalSources = {};
    causalEdges.forEach((e) => {
      if (!causalSources[e.target]) causalSources[e.target] = [];
      causalSources[e.target].push(e.source);
    });

    const convergenceNodes = Object.keys(causalSources).filter(
      (k) => causalSources[k].length > 1
    );

    convergenceNodes.forEach((target) => {
      const sources = causalSources[target];
      sources.forEach((src, i) => {
        const srcIdx = events.findIndex((e) => e.id === src);
        const tgtIdx = events.findIndex((e) => e.id === target);
        if (tgtIdx - srcIdx > 1) {
          yOffsets[src] = (i % 2 === 0 ? -1 : 1) * 40;
        }
      });
    });

    events.forEach((ev, i) => {
      const x = xPositions[i] * scale + offsetX + paddingX / 2;
      const y = height / 2 + yOffsets[ev.id];
      positions[ev.id] = { x, y };
    });

    return positions;
  }, []);

  const renderGraph = useCallback(
    (svgEl, data, positions, isCompare = false) => {
      if (!svgEl || !data) return;

      const svg = d3.select(svgEl);
      svg.selectAll("*").remove();

      const width = svgEl.clientWidth;
      const height = svgEl.clientHeight;

      const defs = svg.append("defs");

      [
        { id: "arrow-temporal", color: COLORS.temporal },
        { id: "arrow-causes", color: COLORS.causes },
        { id: "arrow-enables", color: COLORS.enables },
      ].forEach(({ id, color }) => {
        defs
          .append("marker")
          .attr("id", `${id}${isCompare ? "-cmp" : ""}`)
          .attr("viewBox", "0 0 10 6")
          .attr("refX", 10)
          .attr("refY", 3)
          .attr("markerWidth", 8)
          .attr("markerHeight", 5)
          .attr("orient", "auto")
          .append("path")
          .attr("d", "M0,0 L10,3 L0,6 Z")
          .attr("fill", color);
      });

      const g = svg.append("g");

      const edgeGroup = g.append("g").attr("class", "edges");
      const nodeGroup = g.append("g").attr("class", "nodes");

      const visibleEdges = data.edges.filter((e) => {
        if (e.type === "temporal" && !showTemporal) return false;
        if (e.type === "causal" && e.subtype === "causes" && !showCauses) return false;
        if (e.type === "causal" && e.subtype === "enables" && !showEnables) return false;
        return true;
      });

      visibleEdges.forEach((edge, i) => {
        const src = positions[edge.source];
        const tgt = positions[edge.target];
        if (!src || !tgt) return;

        const isTemporal = edge.type === "temporal";
        const isCauses = edge.type === "causal" && edge.subtype === "causes";
        const color = isTemporal ? COLORS.temporal : isCauses ? COLORS.causes : COLORS.enables;
        const markerId = isTemporal
          ? "arrow-temporal"
          : isCauses
          ? "arrow-causes"
          : "arrow-enables";

        const nodeRadius = 22;
        const dx = tgt.x - src.x;
        const dy = tgt.y - src.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const offsetSx = (dx / dist) * nodeRadius;
        const offsetSy = (dy / dist) * nodeRadius;
        const offsetTx = (dx / dist) * (nodeRadius + 8);
        const offsetTy = (dy / dist) * (nodeRadius + 8);

        const x1 = src.x + offsetSx;
        const y1 = src.y + offsetSy;
        const x2 = tgt.x - offsetTx;
        const y2 = tgt.y - offsetTy;

        if (isTemporal) {
          edgeGroup
            .append("line")
            .attr("x1", x1)
            .attr("y1", y1)
            .attr("x2", x2)
            .attr("y2", y2)
            .attr("stroke", color)
            .attr("stroke-width", hoveredEdge === i ? 2.5 : 1.5)
            .attr("stroke-opacity", hoveredEdge === i ? 1 : 0.5)
            .attr("marker-end", `url(#${markerId}${isCompare ? "-cmp" : ""})`)
            .style("cursor", "pointer");

          if (edge.distance) {
            const mx = (x1 + x2) / 2;
            const my = (y1 + y2) / 2 - 10;
            edgeGroup
              .append("text")
              .attr("x", mx)
              .attr("y", my)
              .attr("text-anchor", "middle")
              .attr("fill", COLORS.textDim)
              .attr("font-size", "9px")
              .attr("font-family", "'JetBrains Mono', monospace")
              .text(edge.distance);
          }
        } else {
          const midX = (x1 + x2) / 2;
          const midY = (y1 + y2) / 2;
          const arcStrength = Math.abs(tgt.y - src.y) < 20 ? -40 - (i % 3) * 15 : 0;
          const cpX = midX;
          const cpY = midY + arcStrength;

          edgeGroup
            .append("path")
            .attr("d", `M${x1},${y1} Q${cpX},${cpY} ${x2},${y2}`)
            .attr("fill", "none")
            .attr("stroke", color)
            .attr("stroke-width", hoveredEdge === i ? 2.5 : 1.5)
            .attr("stroke-opacity", hoveredEdge === i ? 1 : 0.5)
            .attr("stroke-dasharray", edge.subtype === "enables" ? "6,4" : "none")
            .attr("marker-end", `url(#${markerId}${isCompare ? "-cmp" : ""})`)
            .style("cursor", "pointer");
        }
      });

      data.events.forEach((ev) => {
        const pos = positions[ev.id];
        if (!pos) return;
        const isHovered = hoveredNode === ev.id;

        nodeGroup
          .append("circle")
          .attr("cx", pos.x)
          .attr("cy", pos.y)
          .attr("r", isHovered ? 26 : 22)
          .attr("fill", isHovered ? COLORS.nodeHover : COLORS.node)
          .attr("stroke", isHovered ? COLORS.accent : COLORS.nodeStroke)
          .attr("stroke-width", isHovered ? 2 : 1.5)
          .style("cursor", "pointer")
          .style("transition", "all 0.15s ease");

        nodeGroup
          .append("text")
          .attr("x", pos.x)
          .attr("y", pos.y + 1)
          .attr("text-anchor", "middle")
          .attr("dominant-baseline", "central")
          .attr("fill", isHovered ? COLORS.accent : COLORS.text)
          .attr("font-size", "12px")
          .attr("font-weight", "600")
          .attr("font-family", "'JetBrains Mono', monospace")
          .text(ev.id)
          .style("cursor", "pointer")
          .style("pointer-events", "none");
      });
    },
    [showTemporal, showCauses, showEnables, hoveredNode, hoveredEdge]
  );

  useEffect(() => {
    if (!svgRef.current) return;
    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;
    const positions = computeNodePositions(currentData, width, height);
    renderGraph(svgRef.current, currentData, positions);
  }, [currentData, renderGraph, computeNodePositions]);

  useEffect(() => {
    if (!compareMode || !compareSvgRef.current || !customGraph) return;
    const goldData = GOLD_STANDARD.domains[domain];
    const width = compareSvgRef.current.clientWidth;
    const height = compareSvgRef.current.clientHeight;
    const positions = computeNodePositions(goldData, width, height);
    renderGraph(compareSvgRef.current, goldData, positions, true);
  }, [compareMode, domain, customGraph, renderGraph, computeNodePositions]);

  const connectedEdges = hoveredNode
    ? currentData.edges
        .filter((e) => e.source === hoveredNode || e.target === hoveredNode)
        .filter((e) => {
          if (e.type === "temporal" && !showTemporal) return false;
          if (e.type === "causal" && e.subtype === "causes" && !showCauses) return false;
          if (e.type === "causal" && e.subtype === "enables" && !showEnables) return false;
          return true;
        })
    : [];

  const hoveredEvent = hoveredNode
    ? currentData.events.find((e) => e.id === hoveredNode)
    : null;

  return (
    <div style={{ background: COLORS.bg, minHeight: "100vh", color: COLORS.text, fontFamily: "'Inter', -apple-system, sans-serif", padding: "24px" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@400;500;600&display=swap');
      `}</style>

      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ fontSize: 18, fontWeight: 600, fontFamily: "'JetBrains Mono', monospace", color: COLORS.text, margin: 0, letterSpacing: "-0.02em" }}>
            Event Graph Visualizer
          </h1>
          <p style={{ fontSize: 12, color: COLORS.textDim, margin: "4px 0 0", fontFamily: "'JetBrains Mono', monospace" }}>
            Gold standard · Narrative comprehension study
          </p>
        </div>

        {/* Controls Row */}
        <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
          {/* Domain Tabs */}
          {["medical", "workplace", "coastal"].map((d) => (
            <button
              key={d}
              onClick={() => setDomain(d)}
              style={{
                padding: "6px 14px",
                borderRadius: 6,
                border: `1px solid ${domain === d ? COLORS.accent : COLORS.border}`,
                background: domain === d ? "rgba(56, 189, 248, 0.1)" : "transparent",
                color: domain === d ? COLORS.accent : COLORS.textMuted,
                fontSize: 12,
                fontFamily: "'JetBrains Mono', monospace",
                fontWeight: 500,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              {d}
            </button>
          ))}

          <div style={{ width: 1, height: 24, background: COLORS.border, margin: "0 4px" }} />

          {/* Edge Toggles */}
          {[
            { label: "temporal", active: showTemporal, toggle: () => setShowTemporal(!showTemporal), color: COLORS.temporal },
            { label: "causes", active: showCauses, toggle: () => setShowCauses(!showCauses), color: COLORS.causes },
            { label: "enables", active: showEnables, toggle: () => setShowEnables(!showEnables), color: COLORS.enables },
          ].map(({ label, active, toggle, color }) => (
            <button
              key={label}
              onClick={toggle}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 12px",
                borderRadius: 6,
                border: `1px solid ${active ? color : COLORS.border}`,
                background: active ? `${color}15` : "transparent",
                color: active ? color : COLORS.textDim,
                fontSize: 11,
                fontFamily: "'JetBrains Mono', monospace",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              <span style={{
                width: 16, height: 2,
                background: active ? color : COLORS.textDim,
                display: "block",
                borderTop: label === "enables" ? `2px dashed ${active ? color : COLORS.textDim}` : "none",
                borderBottom: label !== "enables" ? `2px solid ${active ? color : COLORS.textDim}` : "none",
              }} />
              {label}
            </button>
          ))}

          <div style={{ width: 1, height: 24, background: COLORS.border, margin: "0 4px" }} />

          {/* View Mode */}
          {["gold", "custom"].map((v) => (
            <button
              key={v}
              onClick={() => setViewMode(v)}
              style={{
                padding: "6px 12px",
                borderRadius: 6,
                border: `1px solid ${viewMode === v ? COLORS.accent : COLORS.border}`,
                background: viewMode === v ? "rgba(56, 189, 248, 0.1)" : "transparent",
                color: viewMode === v ? COLORS.accent : COLORS.textMuted,
                fontSize: 11,
                fontFamily: "'JetBrains Mono', monospace",
                cursor: "pointer",
              }}
            >
              {v === "gold" ? "gold standard" : "model output"}
            </button>
          ))}

          {customGraph && (
            <button
              onClick={() => setCompareMode(!compareMode)}
              style={{
                padding: "6px 12px",
                borderRadius: 6,
                border: `1px solid ${compareMode ? "#fbbf24" : COLORS.border}`,
                background: compareMode ? "rgba(251, 191, 36, 0.1)" : "transparent",
                color: compareMode ? "#fbbf24" : COLORS.textMuted,
                fontSize: 11,
                fontFamily: "'JetBrains Mono', monospace",
                cursor: "pointer",
              }}
            >
              compare
            </button>
          )}
        </div>

        {/* Main Graph */}
        <div style={{
          background: COLORS.surface,
          borderRadius: 10,
          border: `1px solid ${COLORS.border}`,
          overflow: "hidden",
          marginBottom: 12,
        }}>
          <div style={{ padding: "8px 14px", borderBottom: `1px solid ${COLORS.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 11, color: COLORS.textDim, fontFamily: "'JetBrains Mono', monospace" }}>
              {viewMode === "gold" ? "gold standard" : "model output"} · {domain}
            </span>
            <span style={{ fontSize: 10, color: COLORS.textDim, fontFamily: "'JetBrains Mono', monospace" }}>
              {currentData.events.length} events · {currentData.edges.filter(e => {
                if (e.type === "temporal" && !showTemporal) return false;
                if (e.type === "causal" && e.subtype === "causes" && !showCauses) return false;
                if (e.type === "causal" && e.subtype === "enables" && !showEnables) return false;
                return true;
              }).length} visible edges
            </span>
          </div>
          <svg
            ref={svgRef}
            width="100%"
            height={280}
            style={{ display: "block" }}
            onMouseMove={(e) => {
              const svg = svgRef.current;
              if (!svg) return;
              const rect = svg.getBoundingClientRect();
              const mx = e.clientX - rect.left;
              const my = e.clientY - rect.top;
              const width = svg.clientWidth;
              const height = svg.clientHeight;
              const positions = computeNodePositions(currentData, width, height);
              let found = null;
              currentData.events.forEach((ev) => {
                const pos = positions[ev.id];
                const dist = Math.sqrt((mx - pos.x) ** 2 + (my - pos.y) ** 2);
                if (dist < 28) found = ev.id;
              });
              setHoveredNode(found);
            }}
            onMouseLeave={() => setHoveredNode(null)}
          />
        </div>

        {/* Compare view */}
        {compareMode && customGraph && (
          <div style={{
            background: COLORS.surface,
            borderRadius: 10,
            border: `1px solid ${COLORS.border}`,
            overflow: "hidden",
            marginBottom: 12,
          }}>
            <div style={{ padding: "8px 14px", borderBottom: `1px solid ${COLORS.border}` }}>
              <span style={{ fontSize: 11, color: COLORS.textDim, fontFamily: "'JetBrains Mono', monospace" }}>
                gold standard · {domain} (reference)
              </span>
            </div>
            <svg ref={compareSvgRef} width="100%" height={250} style={{ display: "block" }} />
          </div>
        )}

        {/* Bottom panels */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {/* Event detail / hover info */}
          <div style={{
            background: COLORS.surface,
            borderRadius: 10,
            border: `1px solid ${COLORS.border}`,
            padding: 16,
            minHeight: 180,
          }}>
            {hoveredEvent ? (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                  <span style={{
                    background: "rgba(56, 189, 248, 0.15)",
                    color: COLORS.accent,
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontSize: 12,
                    fontFamily: "'JetBrains Mono', monospace",
                    fontWeight: 600,
                  }}>
                    {hoveredEvent.id}
                  </span>
                  <span style={{ fontSize: 10, color: COLORS.textDim, fontFamily: "'JetBrains Mono', monospace" }}>
                    canonical position {hoveredEvent.canonical_position}
                  </span>
                </div>
                <p style={{ fontSize: 13, color: COLORS.text, lineHeight: 1.5, margin: "0 0 14px" }}>
                  {hoveredEvent.description}
                </p>
                {connectedEdges.length > 0 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    {connectedEdges.map((e, i) => {
                      const isTemporal = e.type === "temporal";
                      const color = isTemporal ? COLORS.temporal : e.subtype === "causes" ? COLORS.causes : COLORS.enables;
                      const direction = e.source === hoveredNode ? "→" : "←";
                      const other = e.source === hoveredNode ? e.target : e.source;
                      return (
                        <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>
                          <span style={{ color, minWidth: 58 }}>{isTemporal ? "temporal" : e.subtype}</span>
                          <span style={{ color: COLORS.textDim }}>{direction}</span>
                          <span style={{ color: COLORS.text }}>{other}</span>
                          {isTemporal && e.distance && (
                            <span style={{ color: COLORS.textDim, fontSize: 10 }}>({e.distance})</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            ) : (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", minHeight: 120 }}>
                <span style={{ fontSize: 12, color: COLORS.textDim, fontFamily: "'JetBrains Mono', monospace" }}>
                  hover over a node to inspect
                </span>
              </div>
            )}
          </div>

          {/* JSON Input */}
          <div style={{
            background: COLORS.surface,
            borderRadius: 10,
            border: `1px solid ${COLORS.border}`,
            padding: 16,
            minHeight: 180,
            display: "flex",
            flexDirection: "column",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <span style={{ fontSize: 11, color: COLORS.textDim, fontFamily: "'JetBrains Mono', monospace" }}>
                paste model-generated JSON
              </span>
              <button
                onClick={handleJsonParse}
                style={{
                  padding: "4px 12px",
                  borderRadius: 5,
                  border: `1px solid ${COLORS.accent}`,
                  background: "rgba(56, 189, 248, 0.1)",
                  color: COLORS.accent,
                  fontSize: 11,
                  fontFamily: "'JetBrains Mono', monospace",
                  cursor: "pointer",
                }}
              >
                load
              </button>
            </div>
            <textarea
              value={jsonInput}
              onChange={(e) => setJsonInput(e.target.value)}
              placeholder='{"events": [...], "edges": [...]}'
              style={{
                flex: 1,
                background: COLORS.surfaceAlt,
                border: `1px solid ${parseError ? "#ef4444" : COLORS.border}`,
                borderRadius: 6,
                color: COLORS.text,
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11,
                padding: 10,
                resize: "none",
                outline: "none",
                lineHeight: 1.5,
              }}
            />
            {parseError && (
              <span style={{ fontSize: 10, color: "#ef4444", fontFamily: "'JetBrains Mono', monospace", marginTop: 4 }}>
                {parseError}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
