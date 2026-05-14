import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
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
});
