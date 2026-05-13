import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TabBar } from "../TabBar";

const TABS = [
  { key: "tokens", label: "Tokens" },
  { key: "ast", label: "AST" },
  { key: "assembly", label: "Assembly" },
];

describe("TabBar", () => {
  it("renders all tab labels", () => {
    render(<TabBar tabs={TABS} active="tokens" onChange={() => {}} />);
    expect(screen.getByText("Tokens")).toBeTruthy();
    expect(screen.getByText("AST")).toBeTruthy();
    expect(screen.getByText("Assembly")).toBeTruthy();
  });

  it("highlights the active tab with accent color", () => {
    render(<TabBar tabs={TABS} active="ast" onChange={() => {}} />);
    const astTab = screen.getByText("AST");
    expect(astTab.style.color.toLowerCase()).toBe("rgb(245, 194, 231)");
  });

  it("calls onChange when a tab is clicked", async () => {
    const user = userEvent.setup();
    let selected = "";
    render(<TabBar tabs={TABS} active="tokens" onChange={(k) => { selected = k; }} />);
    await user.click(screen.getByText("Assembly"));
    expect(selected).toBe("assembly");
  });
});
