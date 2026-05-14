import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import App from "../App";

vi.mock("@monaco-editor/react", () => ({
  default: () => <div data-testid="monaco-editor" />,
}));

Object.defineProperty(window, "nekoscope", {
  value: { openInTerminal: vi.fn() },
  writable: true,
});

function mockApi(
  compileResponse: Response = new Response(JSON.stringify({
    source: "(nya t)",
    tokens: [{ type: "program", value: "nya", line: 1, column: 2 }],
    ast: { nodeType: "Program", line: 1, column: 1, name: "t" },
    symbols: { entries: [], constants: {} },
    quadruples: [],
    assembly: "",
    errors: [],
    backend: "llvm",
  }), { status: 200 })
) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/api/examples")) {
      return new Response(JSON.stringify({ examples: [] }), { status: 200 });
    }
    if (url.endsWith("/api/compile")) {
      return compileResponse.clone();
    }
    if (url.endsWith("/api/run")) {
      return new Response(JSON.stringify({
        executablePath: "/tmp/nekoscope-test-run",
        errors: [],
        compileError: "",
      }), { status: 200 });
    }
    return new Response("Not Found", { status: 404 });
  });
}

describe("App", () => {
  it("shows compiler failures separately from API connection failures", async () => {
    mockApi(
      new Response(
        JSON.stringify({ detail: "[Parser] Line 1, Column 8: 期望 ')'" }),
        { status: 400 }
      )
    );

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("编译失败")).toBeTruthy();
    });
    expect(screen.getByText(/期望 '\)'/)).toBeTruthy();
    expect(screen.queryByText("API 连接失败")).toBeNull();
  });

  it("resizes the source pane from the keyboard separator", async () => {
    const user = userEvent.setup();
    mockApi();
    render(<App />);

    const workspace = document.querySelector(".workspace-grid") as HTMLElement;
    const separator = screen.getByRole("separator", { name: "调整源码编辑器宽度" });
    await user.click(separator);
    await user.keyboard("{ArrowRight}");

    expect(workspace.style.getPropertyValue("--source-pane-width")).toBe("46%");
    expect(separator).toHaveAttribute("aria-valuenow", "46");
  });

  it("collapses and restores the stage lesson panel", async () => {
    const user = userEvent.setup();
    mockApi();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "折叠阶段说明" }));

    expect(screen.queryByText("展示源码经过词法分析、语法分析、语义分析、中间表示和代码生成后的完整产物。")).toBeNull();
    await user.click(screen.getByRole("button", { name: "展开阶段说明" }));
    expect(screen.getByText("展示源码经过词法分析、语法分析、语义分析、中间表示和代码生成后的完整产物。")).toBeTruthy();
  });

  it("opens the matching artifact stage from the overview rows", async () => {
    const user = userEvent.setup();
    mockApi();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "查看Tokens阶段" }));

    expect(screen.getByRole("heading", { name: "Tokens" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /词法分析/ })).toHaveClass("active");
  });

  it("runs the current source and shows stdout", async () => {
    const user = userEvent.setup();
    mockApi();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "运行" }));

    await waitFor(() => {
      expect(screen.getByText("运行结果")).toBeTruthy();
    });
    expect(screen.getByText("已启动终端")).toBeTruthy();
    expect(screen.getByText("程序已在系统终端中启动。")).toBeTruthy();
  });
});
