import { useMemo } from "react";
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
import { colors } from "../styles/theme";

/** AST keys that are metadata, not children */
const META_KEYS = new Set(["nodeType", "line", "column"]);

interface Props {
  ast: ASTNode | null;
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
): void {
  const id = prefix;
  nodes.push({
    id,
    type: "astNode",
    position: { x: 0, y: 0 },
    data: { label: labelFor(ast) },
  });

  for (const [key, val] of Object.entries(ast)) {
    if (META_KEYS.has(key)) continue;
    if (Array.isArray(val)) {
      val.forEach((child, i) => {
        if (child != null && typeof child === "object" && "nodeType" in child) {
          const childId = `${prefix}-${key}-${i}`;
          edges.push({ id: `${id}->${childId}`, source: id, target: childId, style: { stroke: colors.overlay0 } });
          convertTree(child as ASTNode, childId, nodes, edges);
        }
      });
    } else if (val != null && typeof val === "object" && "nodeType" in val) {
      const childId = `${prefix}-${key}`;
      edges.push({ id: `${id}->${childId}`, source: id, target: childId, style: { stroke: colors.overlay0 } });
      convertTree(val as ASTNode, childId, nodes, edges);
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

export function astToFlow(ast: ASTNode): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  convertTree(ast, "root", nodes, edges);
  return { nodes: layoutNodes(nodes, edges), edges };
}

/** Custom AST node display */
function ASTNodeDisplay({ data }: { data: { label: string } }) {
  return (
    <div
      className="ast-flow-node"
    >
      <Handle type="target" position={Position.Top} style={{ background: colors.surface1 }} />
      {data.label}
      <Handle type="source" position={Position.Bottom} style={{ background: colors.surface1 }} />
    </div>
  );
}

const nodeTypes = { astNode: ASTNodeDisplay };

export function ASTPanel({ ast }: Props) {
  const { nodes, edges } = useMemo(() => {
    if (!ast) return { nodes: [], edges: [] };
    return astToFlow(ast);
  }, [ast]);

  if (!ast) {
    return (
      <div className="empty-panel">
        运行编译后可以看到 AST。
      </div>
    );
  }

  return (
    <div className="ast-panel">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-left"
      >
        <Background color={colors.surface0} gap={20} />
        <Controls style={{ background: colors.surface0, borderRadius: 4 }} />
        <MiniMap
          style={{ background: colors.mantle, borderRadius: 4 }}
          nodeColor={() => colors.surface1}
          maskColor={`${colors.base}dd`}
        />
      </ReactFlow>
    </div>
  );
}
