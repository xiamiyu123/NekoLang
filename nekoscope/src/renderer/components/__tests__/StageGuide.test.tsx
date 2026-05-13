import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Binary, Route } from "lucide-react";
import { StageGuide, type StageInfo } from "../StageGuide";

const stages: StageInfo[] = [
  {
    key: "overview",
    label: "路线图",
    shortLabel: "Pipeline",
    outputName: "全局观察",
    description: "",
    focus: "",
    icon: Route,
  },
  {
    key: "tokens",
    label: "词法分析",
    shortLabel: "Lexing",
    outputName: "Tokens",
    description: "",
    focus: "",
    icon: Binary,
  },
];

describe("StageGuide", () => {
  it("renders stage labels and output names", () => {
    render(
      <StageGuide
        stages={stages}
        activeStage="overview"
        completedStages={new Set(["overview"])}
        onSelect={() => {}}
      />
    );

    expect(screen.getByText("路线图")).toBeTruthy();
    expect(screen.getByText("Tokens")).toBeTruthy();
  });

  it("selects a stage", async () => {
    const user = userEvent.setup();
    let selected = "";
    render(
      <StageGuide
        stages={stages}
        activeStage="overview"
        completedStages={new Set(["overview"])}
        onSelect={(stage) => { selected = stage; }}
      />
    );

    await user.click(screen.getByText("词法分析"));
    expect(selected).toBe("tokens");
  });
});
