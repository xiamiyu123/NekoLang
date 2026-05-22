import { useEffect, useMemo, useState } from "react";
import { Maximize2, X } from "lucide-react";
import ReactFlow, {
  Background,
  Controls,
  Edge,
  Handle,
  MiniMap,
  Node,
  Position,
} from "reactflow";
import "reactflow/dist/style.css";
import dagre from "dagre";
import type { QuadrupleDag, QuadrupleDagBlock, QuadrupleDagNode } from "../types/compiler";
import { astThemeColors, type ResolvedTheme } from "../styles/theme";

type DagThemeColors = (typeof astThemeColors)[ResolvedTheme];

interface Props {
  dag?: QuadrupleDag | null;
  theme: ResolvedTheme;
}

function formatNodeMain(node: QuadrupleDagNode): string {
  return node.op === "value" ? node.value : node.op;
}

function formatNodeNames(node: QuadrupleDagNode): string {
  return node.names.join(", ");
}

export function dagToFlow(block: QuadrupleDagBlock, theme: ResolvedTheme = "dark"): { nodes: Node[]; edges: Edge[] } {
  const colors = astThemeColors[theme];
  const nodes: Node[] = block.nodes.map((node) => ({
    id: node.id,
    type: "dagNode",
    position: { x: 0, y: 0 },
    sourcePosition: Position.Bottom,
    targetPosition: Position.Top,
    data: {
      number: node.number,
      main: formatNodeMain(node),
      names: formatNodeNames(node),
      isValue: node.op === "value",
      handleColor: colors.handle,
    },
  }));
  const edges: Edge[] = block.edges.map((edge, index) => ({
    id: `${edge.source}-${edge.target}-${index}`,
    source: edge.source,
    target: edge.target,
    style: { stroke: colors.edge },
  }));
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 24, ranksep: 58, marginx: 8, marginy: 8 });
  for (const node of nodes) {
    g.setNode(node.id, { width: 108, height: 38 });
  }
  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }
  dagre.layout(g);
  return {
    nodes: nodes.map((node) => {
      const position = g.node(node.id);
      return { ...node, position: { x: position.x - 54, y: position.y - 19 } };
    }),
    edges,
  };
}

function DagNodeDisplay({
  data,
}: {
  data: { number: number; main: string; names: string; isValue: boolean; handleColor: string };
}) {
  return (
    <div className={`dag-flow-node ${data.isValue ? "value" : "operator"}`}>
      <Handle type="target" position={Position.Top} style={{ background: data.handleColor }} />
      <div className="dag-node-main">
        {data.isValue ? (
          <>
            <span className="dag-node-number">{data.number}</span>
            <strong>{data.main}</strong>
          </>
        ) : (
          <>
            <strong className="dag-node-operator">{data.main}</strong>
            <span className="dag-node-number">{data.number}</span>
          </>
        )}
        {data.names ? <span className="dag-node-inline-names">{data.names}</span> : null}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: data.handleColor }} />
    </div>
  );
}

const nodeTypes = { dagNode: DagNodeDisplay };

function DagCanvas({
  nodes,
  edges,
  colors,
  full = false,
}: {
  nodes: Node[];
  edges: Edge[];
  colors: DagThemeColors;
  full?: boolean;
}) {
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: full ? 0.14 : 0.22, maxZoom: full ? 1.2 : 0.95 }}
      attributionPosition="bottom-left"
      minZoom={0.08}
      maxZoom={1.6}
    >
      <Background color={colors.background} gap={full ? 22 : 18} />
      <Controls
        showInteractive={false}
        style={{ background: colors.controlBackground, borderRadius: 4 }}
      />
      {full || nodes.length > 8 ? (
        <MiniMap
          position="top-right"
          style={{ width: full ? 140 : 104, height: full ? 92 : 72, background: colors.minimap, borderRadius: 4 }}
          nodeColor={() => colors.minimapNode}
          maskColor={colors.minimapMask}
        />
      ) : null}
    </ReactFlow>
  );
}

export function QuadrupleDagPanel({ dag, theme }: Props) {
  const blocks = useMemo(() => (dag?.blocks ?? []).filter((item) => item.nodes.length > 0), [dag]);
  const preferredBlock = useMemo(() => {
    const opIndex = blocks.findIndex((item) => item.nodes.some((node) => node.op !== "value"));
    return opIndex >= 0 ? opIndex : 0;
  }, [blocks]);
  const [selectedBlock, setSelectedBlock] = useState<number | null>(null);
  useEffect(() => {
    setSelectedBlock(null);
  }, [dag]);
  const selectedIndex =
    selectedBlock == null || blocks.length === 0
      ? preferredBlock
      : Math.min(Math.max(selectedBlock, 0), blocks.length - 1);
  const activeBlock = selectedIndex;
  const block = blocks[activeBlock] ?? null;
  const [fullViewOpen, setFullViewOpen] = useState(false);
  const colors = astThemeColors[theme];
  const { nodes, edges } = useMemo(() => {
    if (!block) return { nodes: [], edges: [] };
    return dagToFlow(block, theme);
  }, [block, theme]);

  if (!dag || blocks.length === 0) {
    return <div className="empty-panel">当前四元式序列没有可构造 DAG 的基本块。</div>;
  }

  return (
    <div className="dag-panel">
      <div className="dag-toolbar">
        <div className="dag-block-bar" aria-label="基本块列表">
          {blocks.map((item, index) => (
            <button
              className={`dag-block-button ${index === activeBlock ? "active" : ""}`}
              type="button"
              key={item.blockIndex}
              onClick={() => setSelectedBlock(index)}
            >
              B{item.blockIndex}
              <span>{item.startQuad}-{item.endQuad}</span>
            </button>
          ))}
        </div>
        <button
          className="dag-overview-button"
          type="button"
          onClick={() => setFullViewOpen(true)}
          title="查看 DAG 全貌"
          aria-label="查看 DAG 全貌"
        >
          <Maximize2 size={15} />
          全貌
        </button>
      </div>

      <div className="dag-workspace">
        <aside className="dag-sequence">
          <div className="dag-section-title">四元式序列</div>
          {block?.statements.map((statement) => (
            <div className="dag-statement" key={statement.index}>
              <span>({statement.index})</span>
              <strong>{statement.text}</strong>
            </div>
          ))}
        </aside>

        <div className="dag-canvas">
          <DagCanvas nodes={nodes} edges={edges} colors={colors} />
        </div>
      </div>

      {fullViewOpen ? (
        <div className="dag-modal" role="dialog" aria-modal="true" aria-label="DAG 全貌">
          <div className="dag-modal-panel">
            <header className="dag-modal-head">
              <div>
                <span>DAG 全貌</span>
                <strong>B{block?.blockIndex} · 四元式 {block?.startQuad}-{block?.endQuad}</strong>
              </div>
              <button
                className="icon-button"
                type="button"
                onClick={() => setFullViewOpen(false)}
                aria-label="关闭 DAG 全貌"
                title="关闭"
              >
                <X size={16} />
              </button>
            </header>
            <div className="dag-modal-canvas">
              <DagCanvas nodes={nodes} edges={edges} colors={colors} full />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
