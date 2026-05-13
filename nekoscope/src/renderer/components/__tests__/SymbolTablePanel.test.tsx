import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SymbolTablePanel } from "../SymbolTablePanel";

describe("SymbolTablePanel", () => {
  it("renders symbol entries and constants", () => {
    render(
      <SymbolTablePanel
        symbols={{
          entries: [{ name: "a", type: "int", category: "v", address: 1 }],
          constants: { "42": 2 },
        }}
      />
    );

    expect(screen.getByText("a")).toBeTruthy();
    expect(screen.getByText("int")).toBeTruthy();
    expect(screen.getByText("变量")).toBeTruthy();
    expect(screen.getByText("42")).toBeTruthy();
  });

  it("renders placeholder before compile", () => {
    render(<SymbolTablePanel symbols={null} />);
    expect(screen.getByText(/运行编译后可以看到符号表/)).toBeTruthy();
  });
});
