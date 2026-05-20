import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuadruplePanel } from "../QuadruplePanel";

describe("QuadruplePanel", () => {
  it("renders quadruple rows", () => {
    render(
      <QuadruplePanel
        quadruples={[
          { op: ":=", ob1: "C1", ob2: "_", t: "I2" },
          { op: "print", ob1: "I2", ob2: "_", t: "_" },
        ]}
        theme="dark"
      />
    );

    expect(screen.getByText(":=")).toBeTruthy();
    expect(screen.getByText("print")).toBeTruthy();
    expect(screen.getByText("C1")).toBeTruthy();
    expect(screen.getAllByText("I2")).toHaveLength(2);
  });

  it("switches between optimization process and result", async () => {
    const user = userEvent.setup();
    render(
      <QuadruplePanel
        quadruples={[
          { op: "program", ob1: "t", ob2: "_", t: "_" },
          { op: "+", ob1: "C1", ob2: "C2", t: "T1" },
          { op: ":=", ob1: "T1", ob2: "_", t: "I1" },
        ]}
        optimization={{
          level: "O1",
          source: "Quadruple DAG optimizer",
          enabled: true,
          changed: true,
          beforeCount: 3,
          afterCount: 2,
          initial: [
            { op: "program", ob1: "t", ob2: "_", t: "_" },
            { op: "+", ob1: "C1", ob2: "C2", t: "T1" },
            { op: ":=", ob1: "T1", ob2: "_", t: "I1" },
          ],
          optimized: [
            { op: "program", ob1: "t", ob2: "_", t: "_" },
            { op: ":=", ob1: "C1", ob2: "_", t: "I1" },
          ],
          initialConstants: { "2": "C1", "3": "C2" },
          optimizedConstants: { "5": "C1" },
          steps: [
            {
              name: "O1 常量折叠",
              detail: "对字面量算术、比较和字符内建表达式先求值。",
              beforeCount: 3,
              afterCount: 2,
              changed: true,
              beforeRows: [
                { op: "program", ob1: "t", ob2: "_", t: "_" },
                { op: "+", ob1: "C1", ob2: "C2", t: "T1" },
                { op: ":=", ob1: "T1", ob2: "_", t: "I1" },
              ],
              afterRows: [
                { op: "program", ob1: "t", ob2: "_", t: "_" },
                { op: ":=", ob1: "C3", ob2: "_", t: "I1" },
              ],
              removedRows: [
                { op: "+", ob1: "C1", ob2: "C2", t: "T1" },
                { op: ":=", ob1: "T1", ob2: "_", t: "I1" },
              ],
            },
          ],
          diagnostics: [],
        }}
        theme="dark"
      />
    );

    expect(screen.getByText("C1 = 2")).toBeTruthy();
    await user.click(screen.getByRole("tab", { name: "优化过程" }));
    expect(screen.getByText("四元式序列")).toBeTruthy();
    expect(screen.getByText("O1 常量折叠")).toBeTruthy();
    expect(screen.getByText("3 -> 2")).toBeTruthy();
    const removedTable = screen.getByRole("table", { name: "O1 常量折叠 已优化掉的四元式" });
    expect(within(removedTable).getByText("+")).toBeTruthy();
    expect(within(removedTable).getByText("C2")).toBeTruthy();
    expect(screen.getByRole("table", { name: "O1 常量折叠 优化后四元式" })).toBeTruthy();
    await user.click(screen.getByRole("tab", { name: "优化结果" }));
    expect(screen.getByText("C1 = 5")).toBeTruthy();
  });

  it("renders placeholder before compile", () => {
    render(<QuadruplePanel quadruples={null} theme="dark" />);
    expect(screen.getByText(/运行编译后可以看到四元式/)).toBeTruthy();
  });

  it("shows the DAG inside the optimization process", async () => {
    const user = userEvent.setup();
    render(
      <QuadruplePanel
        quadruples={[
          { op: "+", ob1: "I1", ob2: "I2", t: "T1" },
          { op: "+", ob1: "I1", ob2: "I2", t: "T2" },
        ]}
        dag={{
          blocks: [
            {
              blockIndex: 1,
              startQuad: 1,
              endQuad: 2,
              statements: [
                { index: 1, text: "(+, I1, I2, T1)", op: "+", ob1: "I1", ob2: "I2", t: "T1" },
                { index: 2, text: "(+, I1, I2, T2)", op: "+", ob1: "I1", ob2: "I2", t: "T2" },
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
            },
          ],
        }}
        theme="dark"
      />
    );

    expect(screen.queryByRole("tab", { name: "DAG 图" })).toBeNull();
    await user.click(screen.getByRole("tab", { name: "优化过程" }));
    expect(screen.getByText("T1, T2")).toBeTruthy();
  });

  it("builds a DAG from quadruples when backend DAG data is missing", async () => {
    const user = userEvent.setup();
    render(
      <QuadruplePanel
        quadruples={[
          { op: "+", ob1: "I1", ob2: "I2", t: "T1" },
          { op: "+", ob1: "I1", ob2: "I2", t: "T2" },
        ]}
        theme="dark"
      />
    );

    await user.click(screen.getByRole("tab", { name: "优化过程" }));
    expect(screen.queryByText(/没有可构造 DAG/)).toBeNull();
    expect(screen.getByText("T1, T2")).toBeTruthy();
  });
});
