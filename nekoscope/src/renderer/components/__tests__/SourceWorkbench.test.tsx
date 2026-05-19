import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SourceWorkbench } from "../SourceWorkbench";

const editorMock = vi.hoisted(() => ({
  props: {} as Record<string, unknown>,
}));

vi.mock("@monaco-editor/react", () => ({
  default: (props: Record<string, unknown>) => {
    editorMock.props = props;
    return <div data-testid="monaco-editor" />;
  },
}));

const noop = () => {};
const baseProps = {
  onOpenFile: noop,
  onOpenFolder: noop,
  workspaceTree: null as any,
  workspaceRoot: null,
  activeFilePath: null,
  onFileSelect: noop,
  fileTreeVisible: false,
  onToggleFileTree: noop,
  onSave: noop,
  onNewFile: noop,
  isNewFile: false,
  canSaveDirectly: false,
};

describe("SourceWorkbench", () => {
  it("enables Monaco automatic layout to follow container size changes", () => {
    render(
      <SourceWorkbench
        source="(nya t (paw))"
        examples={[]}
        activeExample={null}
        loading={false}
        running={false}
        theme="dark"
        onSourceChange={() => {}}
        onExampleLoad={() => {}}
        onCompileNow={() => {}}
        onRunNow={() => {}}
        onReset={() => {}}
        {...baseProps}
      />
    );

    expect(screen.getByText("源码编辑器")).toBeTruthy();
    expect(editorMock.props.options).toMatchObject({ automaticLayout: true });
  });

  it("renders separate compile and run actions", () => {
    render(
      <SourceWorkbench
        source="(nya t (paw))"
        examples={[]}
        activeExample={null}
        loading={false}
        running={false}
        theme="light"
        onSourceChange={() => {}}
        onExampleLoad={() => {}}
        onCompileNow={() => {}}
        onRunNow={() => {}}
        onReset={() => {}}
        {...baseProps}
      />
    );

    expect(screen.getByRole("button", { name: "立即编译" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "运行" })).toBeTruthy();
  });

  it("renders the DAG optimization sample in the example strip", async () => {
    const user = userEvent.setup();
    const onExampleLoad = vi.fn();
    render(
      <SourceWorkbench
        source="(nya t (paw))"
        examples={[{ name: "dag_optimization_demo", description: "DAG 优化示例" }]}
        activeExample="dag_optimization_demo"
        loading={false}
        running={false}
        theme="light"
        onSourceChange={() => {}}
        onExampleLoad={onExampleLoad}
        onCompileNow={() => {}}
        onRunNow={() => {}}
        onReset={() => {}}
        {...baseProps}
      />
    );

    const sampleButton = screen.getByRole("button", { name: "DAG 优化示例" });
    expect(sampleButton.className).toContain("active");
    await user.click(sampleButton);
    expect(onExampleLoad).toHaveBeenCalledWith("dag_optimization_demo");
  });
});
