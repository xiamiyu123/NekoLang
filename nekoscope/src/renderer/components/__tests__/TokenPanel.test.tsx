import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TokenPanel } from "../TokenPanel";
import type { Token } from "../../types/compiler";

function tk(type: string, value: string, line: number = 1, column: number = 1): Token {
  return { type, value, line, column };
}

describe("TokenPanel", () => {
  it("renders token type, value, and line for each token", () => {
    const tokens: Token[] = [
      tk("program", "nya", 1, 1),
      tk("identifier", "t", 2, 3),
    ];
    render(<TokenPanel tokens={tokens} theme="dark" />);
    expect(screen.getByText("nya")).toBeTruthy();
    expect(screen.getByText("t")).toBeTruthy();
    expect(screen.getByText("program")).toBeTruthy();
    expect(screen.getByText("identifier")).toBeTruthy();
  });

  it("shows line and column info for each token", () => {
    const tokens: Token[] = [tk("keyword", "nyan", 3, 5)];
    render(<TokenPanel tokens={tokens} theme="dark" />);
    expect(screen.getByText(/3:5/)).toBeTruthy();
  });

  it("renders empty state when no tokens", () => {
    render(<TokenPanel tokens={[]} theme="dark" />);
    expect(screen.getByText(/没有生成词法单元/)).toBeTruthy();
  });

  it("renders hint when null tokens passed", () => {
    render(<TokenPanel tokens={null as unknown as Token[]} theme="dark" />);
    expect(screen.getByText(/运行编译后可以看到词法单元/)).toBeTruthy();
  });
});
