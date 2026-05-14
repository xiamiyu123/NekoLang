import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
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
          source: "ARM64 AST optimizer",
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
            },
          ],
          diagnostics: [],
        }}
      />
    );

    expect(screen.getByText("C1 = 2")).toBeTruthy();
    await user.click(screen.getByRole("tab", { name: "优化过程" }));
    expect(screen.getByText("O1 常量折叠")).toBeTruthy();
    expect(screen.getByText("3 -> 2")).toBeTruthy();
    await user.click(screen.getByRole("tab", { name: "优化结果" }));
    expect(screen.getByText("C1 = 5")).toBeTruthy();
  });

  it("renders placeholder before compile", () => {
    render(<QuadruplePanel quadruples={null} />);
    expect(screen.getByText(/运行编译后可以看到四元式/)).toBeTruthy();
  });
});
