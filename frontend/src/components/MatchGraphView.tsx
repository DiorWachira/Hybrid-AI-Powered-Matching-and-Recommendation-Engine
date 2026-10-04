import { useEffect, useRef, useState } from "react";
import type { Core } from "cytoscape";
import { Maximize, Minus, Network, Plus, RefreshCw } from "lucide-react";
import { api, type MatchGraph } from "../lib/api";

export function MatchGraphView({ matchId }: { matchId: string }) {
  const [data, setData] = useState<MatchGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [rendered, setRendered] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const graph = useRef<Core | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true); setError(null); setData(null);
    void api.matchGraph(matchId, localStorage.getItem("jobbridge_token") ?? "")
      .then((response) => { if (active) setData(response); })
      .catch((reason: Error) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [matchId, refresh]);

  useEffect(() => {
    if (loading || !container.current || !data?.nodes.length) return;
    let active = true;
    let instance: Core | null = null;
    let observer: ResizeObserver | null = null;
    setRendered(false);
    void import("cytoscape").then(({ default: cytoscape }) => {
      if (!active || !container.current) return;
      instance = cytoscape({
        container: container.current,
        elements: [...data.nodes.map((node) => ({ data: node })), ...data.edges.map((edge) => ({ data: edge }))],
        minZoom: 0.2, maxZoom: 3, wheelSensitivity: 0.25,
        layout: { name: "concentric", concentric: (node) => node.data("kind") === "skill" ? 1 : 2, levelWidth: () => 1, minNodeSpacing: 35, padding: 42, animate: false },
        style: [
          { selector: "node", style: { "background-color": "#a5bddd", label: "data(label)", color: "#edf0e9", "font-size": 12, "text-wrap": "wrap", "text-max-width": "100px", "text-valign": "bottom", "text-margin-y": 7, width: 25, height: 25 } },
          { selector: 'node[kind="candidate"]', style: { "background-color": "#d0ef91", width: 42, height: 42 } },
          { selector: 'node[kind="job"]', style: { "background-color": "#e6b285", shape: "round-rectangle", width: 42, height: 42 } },
          { selector: "edge", style: { width: 1.5, "line-color": "#788c84", "target-arrow-color": "#788c84", "target-arrow-shape": "triangle", "curve-style": "bezier" } },
          { selector: 'edge[label="RELATED_TO"]', style: { "line-style": "dashed", "line-color": "#a5bddd" } },
          { selector: ":selected", style: { "border-width": 3, "border-color": "#ffffff" } },
        ],
      });
      graph.current = instance;
      observer = new ResizeObserver(() => { instance?.resize(); instance?.fit(undefined, 42); });
      observer.observe(container.current);
      setRendered(true);
    }).catch(() => { if (active) setError("Graph display could not load. Relationships remain listed below."); });
    return () => { active = false; observer?.disconnect(); instance?.destroy(); graph.current = null; };
  }, [data, loading]);

  const labels = new Map(data?.nodes.map((node) => [node.id, node.label]));
  const zoom = (factor: number) => { const instance = graph.current; if (instance) instance.zoom({ level: Math.max(instance.minZoom(), Math.min(instance.maxZoom(), instance.zoom() * factor)), renderedPosition: { x: instance.width() / 2, y: instance.height() / 2 } }); };
  return <section className="match-graph-section" aria-label="Skill relationship graph">
    <div className="page-heading"><div><h3 className="section-heading"><Network size={18} />Skill relationships</h3><p>Current graph projection / separate from saved score</p></div><div className="match-actions"><button className="icon-button" aria-label="Refresh graph" title="Refresh graph" disabled={loading} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={16} /></button><button className="icon-button" aria-label="Zoom out graph" title="Zoom out" disabled={!rendered} onClick={() => zoom(0.8)}><Minus size={16} /></button><button className="icon-button" aria-label="Zoom in graph" title="Zoom in" disabled={!rendered} onClick={() => zoom(1.25)}><Plus size={16} /></button><button className="icon-button" aria-label="Fit graph" title="Fit graph" disabled={!rendered} onClick={() => graph.current?.fit(undefined, 42)}><Maximize size={16} /></button></div></div>
    {error && <p className="notice error" role="alert">{error}</p>}
    {loading ? <p role="status">Loading skill graph...</p> : data?.state === "awaiting_projection" ? <p role="status">Graph projection not yet available</p> : data?.nodes.length ? <>
      <div className="match-graph" ref={container} role="img" aria-label="Candidate and job skill relationships; text equivalent below" />
      {data.truncated && <p className="match-provenance">Partial graph: node or relationship limit reached</p>}
      <details><summary>Relationships ({data.edges.length})</summary><ul className="graph-relationships">{data.edges.map((edge) => <li key={edge.id}>{labels.get(edge.source)} / {edge.label.replaceAll("_", " ")} / {labels.get(edge.target)}{edge.weight != null ? ` / weight ${edge.weight}` : ""}{edge.status ? ` / ${edge.status}` : ""}</li>)}</ul></details>
    </> : null}
  </section>;
}