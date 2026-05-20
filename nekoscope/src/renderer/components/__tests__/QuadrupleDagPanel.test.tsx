import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuadrupleDagPanel, dagToFlow } from "../QuadrupleDagPanel";
import { buildQuadrupleDag } from "../../quadrupleDag";
import type { QuadrupleDagBlock } from "../../types/compiler";

const block: QuadrupleDagBlock = {
  blockIndex: 1,
  startQuad: 2,
  endQuad: 5,
  statements: [
    { index: 2, text: "(+, I1, I2, T1)", op: "+", ob1: "I1", ob2: "I2", t: "T1" },
    { index: 3, text: "(+, I1, I2, T2)", op: "+", ob1: "I1", ob2: "I2", t: "T2" },
  ],
  nodes: [
    { id: "n1", number: 1, op: "value", value: "I1", names: [] },
    { id: "n2", number: 2, op: "value", value: "I2", names: [] },
    { id: "n3", number: 3, op: "+", value: "", names: ["T1", "T2"] },
  ],
  edges: [
    { source: "n3", target: "n1", role: "left" },
    { source: "n3", target: "n2", role: "right" },
  ],
  skipped: [],
};

const emptyBlock: QuadrupleDagBlock = {
  blockIndex: 2,
  startQuad: 6,
  endQuad: 6,
  statements: [{ index: 6, text: "(print, T1, _, _)", op: "print", ob1: "T1", ob2: "_", t: "_" }],
  nodes: [],
  edges: [],
  skipped: [{ index: 6, op: "print", ob1: "T1", ob2: "_", t: "_", reason: "ignored" }],
};

describe("dagToFlow", () => {
  it("converts DAG nodes and edges to react-flow data", () => {
    const { nodes, edges } = dagToFlow(block);

    expect(nodes).toHaveLength(3);
    expect(edges).toHaveLength(2);
    expect(nodes.find((node) => node.id === "n3")?.data.names).toBe("T1, T2");
    expect(nodes.find((node) => node.id === "n3")?.sourcePosition).toBe("bottom");
    expect(nodes.find((node) => node.id === "n3")?.targetPosition).toBe("top");
    expect(nodes.find((node) => node.id === "n3")?.position.y).toBeLessThan(
      nodes.find((node) => node.id === "n1")?.position.y ?? 0
    );
  });
});

describe("buildQuadrupleDag", () => {
  it("orders commutative fallback operands by constant, named variable, then temporary", () => {
    const dag = buildQuadrupleDag(
      [
        { op: "+", ob1: "I1", ob2: "C1", t: "T1" },
        { op: "+", ob1: "T1", ob2: "I1", t: "T2" },
      ],
      { "3": "C1" },
    );
    const block = dag.blocks[0];
    const nodesById = new Map(block.nodes.map((node) => [node.id, node]));
    const plusNodes = block.nodes.filter((node) => node.op === "+");
    const firstEdges = Object.fromEntries(
      block.edges
        .filter((edge) => edge.source === plusNodes[0].id)
        .map((edge) => [edge.role, nodesById.get(edge.target)])
    );
    const secondEdges = Object.fromEntries(
      block.edges
        .filter((edge) => edge.source === plusNodes[1].id)
        .map((edge) => [edge.role, nodesById.get(edge.target)])
    );

    expect(firstEdges.left?.value).toBe("3");
    expect(firstEdges.right?.value).toBe("I1");
    expect(secondEdges.left?.value).toBe("I1");
    expect(secondEdges.right?.op).toBe("+");
    expect(secondEdges.right?.names).toContain("T1");
  });

  it("shares not-equal commutativity with the backend DAG", () => {
    const dag = buildQuadrupleDag([
      { op: "!=", ob1: "I2", ob2: "I1", t: "T1" },
      { op: "!=", ob1: "I1", ob2: "I2", t: "T2" },
    ]);

    expect(dag.blocks[0].nodes.filter((node) => node.op === "!=")).toHaveLength(1);
  });
});

describe("QuadrupleDagPanel", () => {
  it("renders DAG node labels", () => {
    render(
      <QuadrupleDagPanel
        dag={{
          blocks: [
            {
              ...block,
              skipped: [{ index: 4, op: "print", ob1: "T1", ob2: "_", t: "_", reason: "ignored" }],
            },
          ],
        }}
        theme="dark"
      />
    );

    expect(screen.getByText("B1")).toBeTruthy();
    expect(screen.getByText("四元式序列")).toBeTruthy();
    expect(screen.getByText("(+, I1, I2, T1)")).toBeTruthy();
    expect(screen.getByText("+")).toBeTruthy();
    expect(screen.getByText("T1, T2")).toBeTruthy();
    expect(screen.queryByText(/未纳入 DAG/)).toBeNull();
    expect(document.querySelector(".react-flow")).toBeTruthy();
  });

  it("shows placeholder when there is no DAG block", () => {
    render(<QuadrupleDagPanel dag={{ blocks: [] }} theme="dark" />);

    expect(screen.getByText(/没有可构造 DAG 的基本块/)).toBeTruthy();
  });

  it("ignores empty backend DAG blocks", () => {
    render(<QuadrupleDagPanel dag={{ blocks: [emptyBlock] }} theme="dark" />);

    expect(screen.getByText(/没有可构造 DAG 的基本块/)).toBeTruthy();
    expect(document.querySelector(".react-flow")).toBeNull();
  });

  it("clamps the selected block when DAG blocks shrink", async () => {
    const user = userEvent.setup();
    const secondBlock: QuadrupleDagBlock = {
      ...block,
      blockIndex: 2,
      startQuad: 8,
      endQuad: 9,
      statements: [{ index: 8, text: "(*, I1, I2, T3)", op: "*", ob1: "I1", ob2: "I2", t: "T3" }],
      nodes: block.nodes.map((node) => node.id === "n3" ? { ...node, op: "*", names: ["T3"] } : node),
    };
    const { rerender } = render(<QuadrupleDagPanel dag={{ blocks: [block, secondBlock] }} theme="dark" />);

    await user.click(screen.getByText("B2"));
    expect(screen.getByText("(*, I1, I2, T3)")).toBeTruthy();

    rerender(<QuadrupleDagPanel dag={{ blocks: [block] }} theme="dark" />);
    expect(screen.getByText("B1")).toBeTruthy();
    expect(screen.getByText("(+, I1, I2, T1)")).toBeTruthy();
    expect(screen.queryByText("(*, I1, I2, T3)")).toBeNull();
  });

  it("opens and closes the full DAG overview", async () => {
    const user = userEvent.setup();
    render(<QuadrupleDagPanel dag={{ blocks: [block] }} theme="dark" />);

    expect(screen.queryByRole("dialog", { name: "DAG 全貌" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "查看 DAG 全貌" }));
    expect(screen.getByRole("dialog", { name: "DAG 全貌" })).toBeTruthy();
    expect(screen.getByText("B1 · 四元式 2-5")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "关闭 DAG 全貌" }));
    expect(screen.queryByRole("dialog", { name: "DAG 全貌" })).toBeNull();
  });
});
