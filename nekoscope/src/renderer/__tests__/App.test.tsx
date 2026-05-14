import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "../App";

vi.mock("@monaco-editor/react", () => ({
  default: () => <div data-testid="monaco-editor" />,
}));

describe("App", () => {
  it("shows compiler failures separately from API connection failures", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/examples")) {
        return new Response(JSON.stringify({ examples: [] }), { status: 200 });
      }
      if (url.endsWith("/api/compile")) {
        return new Response(
          JSON.stringify({ detail: "[Parser] Line 1, Column 8: 期望 ')'" }),
          { status: 400 }
        );
      }
      return new Response("Not Found", { status: 404 });
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("编译失败")).toBeTruthy();
    });
    expect(screen.getByText(/期望 '\)'/)).toBeTruthy();
    expect(screen.queryByText("API 连接失败")).toBeNull();
  });
});
