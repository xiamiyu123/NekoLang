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
import type { ASTNode, SyntaxTreeNode } from "../types/compiler";
import { astThemeColors, type ResolvedTheme } from "../styles/theme";

type AstThemeColors = (typeof astThemeColors)[ResolvedTheme];

/** AST keys that are metadata, not children */
const META_KEYS = new Set(["nodeType", "line", "column", "tokenType"]);

interface Props {
  ast: ASTNode | null;
  syntaxTree?: SyntaxTreeNode | null;
  theme: ResolvedTheme;
}

type TreeNode = ASTNode | SyntaxTreeNode;
type TreeMode = "ast" | "syntax";

function labelFor(node: TreeNode): string {
  if (node.nodeType === "Terminal") {
    return String(node.value ?? node.tokenType ?? "");
  }
  const parts = [node.nodeType];
  if (node.name != null) parts.push(String(node.name));
  if (node.value != null) parts.push(String(node.value));
  if (node.operator != null) parts.push(String(node.operator));
  return parts.join("\n");
}

/** Recursively convert AST JSON → react-flow nodes + edges, with unique id counter */
function convertTree(
  ast: TreeNode,
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
    data: {
      handleColor: themeColors.handle,
      isTerminal: ast.nodeType === "Terminal",
      label: labelFor(ast),
    },
  });

  for (const [key, val] of Object.entries(ast)) {
    if (META_KEYS.has(key)) continue;
    if (Array.isArray(val)) {
      val.forEach((child, i) => {
        if (child != null && typeof child === "object" && "nodeType" in child) {
          const childId = `${prefix}-${key}-${i}`;
          edges.push({ id: `${id}->${childId}`, source: id, target: childId, style: { stroke: themeColors.edge } });
          convertTree(child as TreeNode, childId, nodes, edges, theme);
        }
      });
    } else if (val != null && typeof val === "object" && "nodeType" in val) {
      const childId = `${prefix}-${key}`;
      edges.push({ id: `${id}->${childId}`, source: id, target: childId, style: { stroke: themeColors.edge } });
      convertTree(val as TreeNode, childId, nodes, edges, theme);
    }
  }
}

/** dagre auto-layout */
function layoutNodes(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 30, ranksep: 60 });
  for (const n of nodes) {
    const isTerminal = Boolean(n.data?.isTerminal);
    g.setNode(n.id, { width: isTerminal ? 76 : 150, height: isTerminal ? 38 : 50 });
  }
  for (const e of edges) {
    g.setEdge(e.source, e.target);
  }
  dagre.layout(g);
  return nodes.map((n) => {
    const d = g.node(n.id);
    const isTerminal = Boolean(n.data?.isTerminal);
    const width = isTerminal ? 76 : 150;
    const height = isTerminal ? 38 : 50;
    return {
      ...n,
      position: {
        x: d.x - width / 2,
        y: d.y - height / 2,
      },
    };
  });
}

export function astToFlow(ast: TreeNode, theme: ResolvedTheme = "dark"): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  convertTree(ast, "root", nodes, edges, theme);
  return { nodes: layoutNodes(nodes, edges), edges };
}

/** Custom AST node display */
function ASTNodeDisplay({ data }: { data: { handleColor: string; isTerminal?: boolean; label: string } }) {
  return (
    <div
      className={`ast-flow-node ${data.isTerminal ? "terminal" : ""}`}
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

export function ASTPanel({ ast, syntaxTree, theme }: Props) {
  const [treeMode, setTreeMode] = useState<TreeMode>("ast");
  const [fullViewOpen, setFullViewOpen] = useState(false);
  const activeTree = treeMode === "syntax" ? syntaxTree : ast;
  const { nodes, edges } = useMemo(() => {
    if (!activeTree) return { nodes: [], edges: [] };
    return astToFlow(activeTree, theme);
  }, [activeTree, theme]);
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
        {syntaxTree ? (
          <div className="quad-toolbar compact" role="tablist" aria-label="语法树模式">
            <button
              className={`tab-button ${treeMode === "ast" ? "active" : ""}`}
              type="button"
              role="tab"
              aria-selected={treeMode === "ast"}
              onClick={() => setTreeMode("ast")}
            >
              抽象 AST
            </button>
            <button
              className={`tab-button ${treeMode === "syntax" ? "active" : ""}`}
              type="button"
              role="tab"
              aria-selected={treeMode === "syntax"}
              onClick={() => setTreeMode("syntax")}
            >
              精确语法树
            </button>
          </div>
        ) : null}
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
                <strong>{activeTree?.nodeType ?? ast.nodeType}</strong>
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
