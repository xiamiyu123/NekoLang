import type { Quadruple, QuadrupleDag, QuadrupleDagBlock, QuadrupleDagNode } from "./types/compiler";

const SUPPORTED_BINARY_OPS = new Set(["+", "-", "*", "/", "<", ">", "=", "<=", ">=", "!="]);
const COMMUTATIVE_OPS = new Set(["+", "*", "=", "!="]);

type OperandSortKey = [number, number, string];

interface DagBuildState {
  nodes: QuadrupleDagNode[];
  edges: { source: string; target: string; role: string }[];
  valueNodes: Map<string, string>;
  exprNodes: Map<string, string>;
  currentDef: Map<string, string>;
}

function createState(): DagBuildState {
  return {
    nodes: [],
    edges: [],
    valueNodes: new Map(),
    exprNodes: new Map(),
    currentDef: new Map(),
  };
}

function newNode(state: DagBuildState, op: string, value = ""): string {
  const number = state.nodes.length + 1;
  const id = `n${number}`;
  state.nodes.push({ id, number, op, value, names: [] });
  return id;
}

function labelOperand(value: string, labels: Record<string, string>): string {
  return labels[value] ?? value;
}

function operandSortKey(operand: string): OperandSortKey {
  const unknownMatch = operand.match(/^unknown:(.+):\d+$/);
  if (unknownMatch) operand = unknownMatch[1];

  if (operand.startsWith("const:")) {
    return [0, 0, operand.slice("const:".length)];
  }

  const exprMatch = operand.match(/^expr:(\d+)$/);
  if (exprMatch) {
    return [2, Number(exprMatch[1]), operand];
  }

  const addrMatch = operand.match(/^([CIT])(\d+)$/);
  if (addrMatch) {
    const rank = { C: 0, I: 1, T: 2 }[addrMatch[1] as "C" | "I" | "T"];
    return [rank, Number(addrMatch[2]), operand];
  }

  return [1, 0, operand];
}

function compareOperandSortKey(left: OperandSortKey, right: OperandSortKey): number {
  if (left[0] !== right[0]) return left[0] - right[0];
  if (left[1] !== right[1]) return left[1] - right[1];
  return left[2].localeCompare(right[2]);
}

function nodeForOperand(state: DagBuildState, operand: string, labels: Record<string, string>): string {
  const current = state.currentDef.get(operand);
  if (current) return current;
  const existing = state.valueNodes.get(operand);
  if (existing) return existing;
  const id = newNode(state, "value", labelOperand(operand, labels));
  state.valueNodes.set(operand, id);
  return id;
}

function nodeById(state: DagBuildState, id: string): QuadrupleDagNode {
  return state.nodes[Number(id.slice(1)) - 1];
}

function attachName(state: DagBuildState, id: string, name: string, labels: Record<string, string>) {
  if (name === "_") return;
  const label = labelOperand(name, labels);
  const oldId = state.currentDef.get(name);
  if (oldId && oldId !== id) {
    const oldNode = nodeById(state, oldId);
    oldNode.names = oldNode.names.filter((item) => item !== label);
  }
  const node = nodeById(state, id);
  if (!node.names.includes(label)) node.names.push(label);
  state.currentDef.set(name, id);
}

function nodeForExpression(
  state: DagBuildState,
  op: string,
  leftId: string,
  rightId: string,
  leftOperand: string,
  rightOperand: string,
): string {
  let keyLeft = leftId;
  let keyRight = rightId;
  if (COMMUTATIVE_OPS.has(op)) {
    const keyComparison = compareOperandSortKey(
      operandSortKey(rightOperand),
      operandSortKey(leftOperand),
    );
    if (keyComparison < 0 || (keyComparison === 0 && keyRight < keyLeft)) {
      [keyLeft, keyRight] = [keyRight, keyLeft];
    }
  }
  const key = `${op}|${keyLeft}|${keyRight}`;
  const existing = state.exprNodes.get(key);
  if (existing) return existing;

  const id = newNode(state, op);
  state.edges.push({ source: id, target: keyLeft, role: "left" });
  state.edges.push({ source: id, target: keyRight, role: "right" });
  state.exprNodes.set(key, id);
  return id;
}

function splitBasicBlocks(quadruples: Quadruple[]): Array<Array<{ index: number; quad: Quadruple }>> {
  const blocks: Array<Array<{ index: number; quad: Quadruple }>> = [];
  let current: Array<{ index: number; quad: Quadruple }> = [];
  const flush = () => {
    if (current.length > 0) {
      blocks.push(current);
      current = [];
    }
  };

  quadruples.forEach((quad, zeroIndex) => {
    const index = zeroIndex + 1;
    if (quad.op === "program" || quad.op === "end") {
      flush();
      return;
    }
    if (quad.op === "label") {
      flush();
      return;
    }
    current.push({ index, quad });
    if (quad.op === "goto" || quad.op === "if_false" || quad.op === "return") {
      flush();
    }
  });
  flush();
  return blocks;
}

function formatStatement(index: number, quad: Quadruple, labels: Record<string, string>) {
  const result = labelOperand(quad.t, labels);
  const left = labelOperand(quad.ob1, labels);
  const right = labelOperand(quad.ob2, labels);
  const text = `(${quad.op}, ${left}, ${right}, ${result})`;
  return { index, text, op: quad.op, ob1: quad.ob1, ob2: quad.ob2, t: quad.t };
}

function buildBlock(
  rows: Array<{ index: number; quad: Quadruple }>,
  blockIndex: number,
  labels: Record<string, string>,
): QuadrupleDagBlock {
  const state = createState();
  const skipped: QuadrupleDagBlock["skipped"] = [];

  rows.forEach(({ index, quad }) => {
    if (quad.op === ":=" && quad.ob1 !== "_") {
      const sourceId = nodeForOperand(state, quad.ob1, labels);
      attachName(state, sourceId, quad.t, labels);
      return;
    }
    if (SUPPORTED_BINARY_OPS.has(quad.op) && quad.ob1 !== "_" && quad.ob2 !== "_" && quad.t !== "_") {
      const leftId = nodeForOperand(state, quad.ob1, labels);
      const rightId = nodeForOperand(state, quad.ob2, labels);
      const exprId = nodeForExpression(state, quad.op, leftId, rightId, quad.ob1, quad.ob2);
      attachName(state, exprId, quad.t, labels);
      return;
    }
    skipped.push({ index, op: quad.op, ob1: quad.ob1, ob2: quad.ob2, t: quad.t, reason: "该四元式不参与表达式 DAG 构造" });
  });

  return {
    blockIndex,
    startQuad: rows[0]?.index ?? 0,
    endQuad: rows[rows.length - 1]?.index ?? 0,
    statements: rows.map(({ index, quad }) => formatStatement(index, quad, labels)),
    nodes: state.nodes,
    edges: state.edges,
    skipped,
  };
}

export function buildQuadrupleDag(
  quadruples: Quadruple[],
  constants: Record<string, string | number> = {},
): QuadrupleDag {
  const labels = Object.fromEntries(
    Object.entries(constants).map(([value, address]) => [String(address), String(value)])
  );
  const blocks = splitBasicBlocks(quadruples)
    .map((block, index) => buildBlock(block, index + 1, labels))
    .filter((block) => block.nodes.length > 0);
  return { blocks };
}
