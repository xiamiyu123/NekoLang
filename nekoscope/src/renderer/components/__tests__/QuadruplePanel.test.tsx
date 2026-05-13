import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
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

  it("renders placeholder before compile", () => {
    render(<QuadruplePanel quadruples={null} />);
    expect(screen.getByText(/运行编译后可以看到四元式/)).toBeTruthy();
  });
});
