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

describe("SourceWorkbench", () => {
  it("enables Monaco automatic layout to follow container size changes", () => {
    render(
      <SourceWorkbench
        source="(nya t (paw))"
        examples={[]}
        activeExample={null}
        loading={false}
        theme="dark"
        onSourceChange={() => {}}
        onExampleLoad={() => {}}
        onCompileNow={() => {}}
        onReset={() => {}}
      />
    );

    expect(screen.getByText("源码编辑器")).toBeTruthy();
    expect(editorMock.props.options).toMatchObject({ automaticLayout: true });
  });
});
