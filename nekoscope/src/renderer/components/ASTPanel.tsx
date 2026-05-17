import { useMemo, useState } from "react";
import { Maximize2, X } from "lucide-react";
import ReactFlow, {
  Node,
  Edge,
  Handle,
  Position,
  Background,
  Controls,
  MiniMap,
} from "reactflow";
import "reactflow/dist/style.css";
import dagre from "dagre";
import type { ASTNode } from "../types/compiler";
import { astThemeColors, type ResolvedTheme } from "../styles/theme";

type AstThemeColors = (typeof astThemeColors)[ResolvedTheme];

/** AST keys that are metadata, not children */
const META_KEYS = new Set(["nodeType", "line", "column"]);

interface Props {
  ast: ASTNode | null;
  theme: ResolvedTheme;
}

function labelFor(node: ASTNode): string {
  const parts = [node.nodeType];
  if (node.name != null) parts.push(String(node.name));
  if (node.value != null) parts.push(String(node.value));
  if (node.operator != null) parts.push(String(node.operator));
  return parts.join("\n");
}

/** Recursively convert AST JSON → react-flow nodes + edges, with unique id counter */
function convertTree(
  ast: ASTNode,
  prefix: string,
  nodes: Node[],
  edges: Edge[],
  theme: ResolvedTheme,
): void {
  const themeColors = astThemeColors[theme];
  const id = prefix;
  nodes.push({
    id,
    type: "astNode",
    position: { x: 0, y: 0 },
    data: { handleColor: themeColors.handle, label: labelFor(ast) },
  });

  for (const [key, val] of Object.entries(ast)) {
    if (META_KEYS.has(key)) continue;
    if (Array.isArray(val)) {
      val.forEach((child, i) => {
        if (child != null && typeof child === "object" && "nodeType" in child) {
          const childId = `${prefix}-${key}-${i}`;
          edges.push({ id: `${id}->${childId}`, source: id, target: childId, style: { stroke: themeColors.edge } });
          convertTree(child as ASTNode, childId, nodes, edges, theme);
        }
      });
    } else if (val != null && typeof val === "object" && "nodeType" in val) {
      const childId = `${prefix}-${key}`;
      edges.push({ id: `${id}->${childId}`, source: id, target: childId, style: { stroke: themeColors.edge } });
      convertTree(val as ASTNode, childId, nodes, edges, theme);
    }
  }
}

/** dagre auto-layout */
function layoutNodes(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 30, ranksep: 60 });
  for (const n of nodes) {
    g.setNode(n.id, { width: 150, height: 50 });
  }
  for (const e of edges) {
    g.setEdge(e.source, e.target);
  }
  dagre.layout(g);
  return nodes.map((n) => {
    const d = g.node(n.id);
    return {
      ...n,
      position: {
        x: d.x - 75,
        y: d.y - 25,
      },
    };
  });
}

export function astToFlow(ast: ASTNode, theme: ResolvedTheme = "dark"): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  convertTree(ast, "root", nodes, edges, theme);
  return { nodes: layoutNodes(nodes, edges), edges };
}

/** Custom AST node display */
function ASTNodeDisplay({ data }: { data: { handleColor: string; label: string } }) {
  return (
    <div
      className="ast-flow-node"
    >
      <Handle type="target" position={Position.Top} style={{ background: data.handleColor }} />
      {data.label}
      <Handle type="source" position={Position.Bottom} style={{ background: data.handleColor }} />
    </div>
  );
}

const nodeTypes = { astNode: ASTNodeDisplay };

function ASTCanvas({
  nodes,
  edges,
  colors,
  full = false,
}: {
  nodes: Node[];
  edges: Edge[];
  colors: AstThemeColors;
  full?: boolean;
}) {
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: full ? 0.14 : 0.24, maxZoom: full ? 1.1 : 0.9 }}
      attributionPosition="bottom-left"
      minZoom={0.06}
      maxZoom={1.4}
    >
      <Background color={colors.background} gap={full ? 22 : 20} />
      <Controls style={{ background: colors.controlBackground, borderRadius: 4 }} />
      <MiniMap
        style={{ background: colors.minimap, borderRadius: 4 }}
        nodeColor={() => colors.minimapNode}
        maskColor={colors.minimapMask}
      />
    </ReactFlow>
  );
}

export function ASTPanel({ ast, theme }: Props) {
  const [fullViewOpen, setFullViewOpen] = useState(false);
  const { nodes, edges } = useMemo(() => {
    if (!ast) return { nodes: [], edges: [] };
    return astToFlow(ast, theme);
  }, [ast, theme]);
  const themeColors = astThemeColors[theme];

  if (!ast) {
    return (
      <div className="empty-panel">
        运行编译后可以看到 AST。
      </div>
    );
  }

  return (
    <div className="ast-panel">
      <div className="ast-toolbar">
        <button
          className="dag-overview-button"
          type="button"
          onClick={() => setFullViewOpen(true)}
          title="查看语法树全貌"
          aria-label="查看语法树全貌"
        >
          <Maximize2 size={15} />
          全貌
        </button>
      </div>
      <div className="ast-canvas">
        <ASTCanvas nodes={nodes} edges={edges} colors={themeColors} />
      </div>

      {fullViewOpen ? (
        <div className="ast-modal" role="dialog" aria-modal="true" aria-label="语法树全貌">
          <div className="ast-modal-panel">
            <header className="ast-modal-head">
              <div>
                <span>语法树全貌</span>
                <strong>{ast.nodeType}</strong>
              </div>
              <button
                className="icon-button"
                type="button"
                onClick={() => setFullViewOpen(false)}
                aria-label="关闭语法树全貌"
                title="关闭"
              >
                <X size={16} />
              </button>
            </header>
            <div className="ast-modal-canvas">
              <ASTCanvas nodes={nodes} edges={edges} colors={themeColors} full />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
