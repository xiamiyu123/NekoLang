import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AssemblyPanel } from "../AssemblyPanel";

describe("AssemblyPanel", () => {
  it("renders assembly code text", () => {
    render(
      <AssemblyPanel
        assembly="mov x0, #42\nret"
        backend="arm64"
        onBackendChange={() => {}}
      />
    );
    expect(screen.getByText(/mov x0, #42/)).toBeTruthy();
  });

  it("shows backend selector with current backend selected", () => {
    render(
      <AssemblyPanel
        assembly=""
        backend="llvm"
        onBackendChange={() => {}}
      />
    );
    const sel = screen.getByRole("combobox") as HTMLSelectElement;
    expect(sel.value).toBe("llvm");
    expect(screen.getByText("LLVM IR")).toBeTruthy();
    expect(screen.getByText("ARM64")).toBeTruthy();
  });

  it("shows placeholder when assembly is null", () => {
    render(
      <AssemblyPanel
        assembly={null}
        backend="llvm"
        onBackendChange={() => {}}
      />
    );
    expect(screen.getByText(/运行编译后可以看到目标代码/)).toBeTruthy();
  });

  it("calls onBackendChange when dropdown changes", async () => {
    const user = userEvent.setup();
    let called = "";
    render(
      <AssemblyPanel
        assembly=""
        backend="arm64"
        onBackendChange={(b) => { called = b; }}
      />
    );
    await user.selectOptions(screen.getByRole("combobox"), "llvm");
    expect(called).toBe("llvm");
  });
});
