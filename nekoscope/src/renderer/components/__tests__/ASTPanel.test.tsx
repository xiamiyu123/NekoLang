import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ASTPanel, astToFlow } from "../ASTPanel";
import type { ASTNode, SyntaxTreeNode } from "../../types/compiler";

const fnDef: ASTNode = {
  nodeType: "FunctionDef",
  name: "t",
  line: 1,
  column: 1,
  params: [],
  body: {
    nodeType: "Block",
    line: 3,
    column: 1,
    statements: [
      { nodeType: "AssignStmt", line: 4, column: 5, name: "a", value: { nodeType: "IntLiteral", line: 4, column: 12, value: 10 } },
    ],
  },
  returnType: "int",
};

const intLit: ASTNode = { nodeType: "IntLiteral", line: 1, column: 1, value: 42 };

const syntaxTree: SyntaxTreeNode = {
  nodeType: "SyntaxTree",
  line: 1,
  column: 1,
  children: [
    {
      nodeType: "SyntaxForm",
      line: 1,
      column: 1,
      children: [
        { nodeType: "Terminal", tokenType: "(", value: "(", line: 1, column: 1 },
        { nodeType: "Terminal", tokenType: "program", value: "nya", line: 1, column: 2 },
        { nodeType: "Terminal", tokenType: "IDENTIFIER", value: "t", line: 1, column: 6 },
        {
          nodeType: "SyntaxForm",
          line: 1,
          column: 8,
          children: [
            { nodeType: "Terminal", tokenType: "(", value: "(", line: 1, column: 8 },
            { nodeType: "Terminal", tokenType: "begin", value: "paw", line: 1, column: 9 },
            { nodeType: "Terminal", tokenType: ")", value: ")", line: 1, column: 12 },
          ],
        },
        { nodeType: "Terminal", tokenType: ")", value: ")", line: 1, column: 13 },
      ],
    },
  ],
};

describe("astToFlow", () => {
  it("converts a leaf node to a single node with no edges", () => {
    const { nodes, edges } = astToFlow(intLit);
    expect(nodes).toHaveLength(1);
    expect(nodes[0].data.label).toContain("IntLiteral");
    expect(nodes[0].data.label).toContain("42");
    expect(edges).toHaveLength(0);
  });

  it("converts nested AST to nodes and edges", () => {
    const { nodes, edges } = astToFlow(fnDef);
    // FunctionDef, Block, AssignStmt, IntLiteral = 4 nodes
    expect(nodes.length).toBeGreaterThanOrEqual(4);
    // should have edges for body, statements, value
    expect(edges.length).toBeGreaterThanOrEqual(3);
    const nodeTypes = nodes.map((n) => n.data.label);
    expect(nodeTypes.some((l) => l.includes("FunctionDef"))).toBe(true);
    expect(nodeTypes.some((l) => l.includes("Block"))).toBe(true);
    expect(nodeTypes.some((l) => l.includes("AssignStmt"))).toBe(true);
    expect(nodeTypes.some((l) => l.includes("IntLiteral"))).toBe(true);
  });

  it("shows value for leaf nodes", () => {
    const { nodes } = astToFlow(intLit);
    expect(nodes[0].data.label).toContain("42");
  });

  it("shows name when present", () => {
    const { nodes } = astToFlow(fnDef);
    const fnNode = nodes.find((n) => n.data.label.includes("FunctionDef"));
    expect(fnNode?.data.label).toContain("t");
  });

  it("marks concrete syntax terminals as compact leaf nodes", () => {
    const { nodes } = astToFlow(syntaxTree);
    const terminal = nodes.find((n) => n.data.label === "nya");
    expect(terminal?.data.isTerminal).toBe(true);
  });
});

describe("ASTPanel", () => {
  it("shows placeholder when ast is null", () => {
    render(<ASTPanel ast={null} theme="dark" />);
    expect(screen.getByText(/运行编译后可以看到 AST/)).toBeTruthy();
  });

  it("renders react-flow container when ast is provided", () => {
    render(<ASTPanel ast={fnDef} theme="dark" />);
    // react-flow renders its container
    expect(document.querySelector(".react-flow")).toBeTruthy();
    expect(screen.queryByRole("tab", { name: "精确语法树" })).toBeNull();
  });

  it("defaults to abstract AST and switches to concrete syntax tree", async () => {
    const user = userEvent.setup();
    render(<ASTPanel ast={fnDef} syntaxTree={syntaxTree} theme="dark" />);

    expect(screen.getByRole("tab", { name: "抽象 AST" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText((content) => content.includes("FunctionDef"))).toBeTruthy();
    expect(screen.queryByText("SyntaxTree")).toBeNull();

    await user.click(screen.getByRole("tab", { name: "精确语法树" }));

    expect(screen.getByRole("tab", { name: "精确语法树" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getAllByText("SyntaxTree").length).toBeGreaterThan(0);
    expect(screen.getByText("nya")).toBeTruthy();
    expect(screen.getAllByText("(").length).toBeGreaterThan(0);
    expect(screen.getAllByText(")").length).toBeGreaterThan(0);
  });

  it("shows the current tree in the full overview dialog", async () => {
    const user = userEvent.setup();
    render(<ASTPanel ast={fnDef} syntaxTree={syntaxTree} theme="dark" />);

    await user.click(screen.getByRole("tab", { name: "精确语法树" }));
    await user.click(screen.getByRole("button", { name: "查看语法树全貌" }));

    expect(screen.getByRole("dialog", { name: "语法树全貌" })).toBeTruthy();
    expect(screen.getAllByText("SyntaxTree").length).toBeGreaterThan(0);
  });

  it("opens and closes the full AST overview", async () => {
    const user = userEvent.setup();
    render(<ASTPanel ast={fnDef} theme="dark" />);

    expect(screen.queryByRole("dialog", { name: "语法树全貌" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "查看语法树全貌" }));
    expect(screen.getByRole("dialog", { name: "语法树全貌" })).toBeTruthy();
    expect(screen.getByText("FunctionDef")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "关闭语法树全貌" }));
    expect(screen.queryByRole("dialog", { name: "语法树全貌" })).toBeNull();
  });
});
