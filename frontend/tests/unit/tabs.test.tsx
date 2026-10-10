import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { ReportTabs, type TabId } from "../../src/components/report/ReportTabs";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "breakdown", label: "Breakdown" },
  { id: "risks", label: "Risks (3)" },
  { id: "improved", label: "Improved Code" },
  { id: "transparency", label: "Transparency" },
] as const;

function Harness() {
  const [active, setActive] = useState<TabId>("overview");
  return (
    <ReportTabs tabs={[...TABS]} active={active} onChange={setActive}>
      <p>Panel: {active}</p>
    </ReportTabs>
  );
}

describe("ReportTabs keyboard navigation", () => {
  it("moves with arrow keys, Home and End", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const overview = screen.getByRole("tab", { name: "Overview" });
    expect(overview).toHaveAttribute("aria-selected", "true");
    overview.focus();

    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Breakdown" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Breakdown" })).toHaveFocus();
    expect(screen.getByText("Panel: breakdown")).toBeInTheDocument();

    await user.keyboard("{ArrowLeft}{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "Transparency" })).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{Home}");
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Transparency" })).toHaveAttribute("aria-selected", "true");
  });

  it("uses a roving tabindex and links the panel to its tab", () => {
    render(<Harness />);
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("tab", { name: "Risks (3)" })).toHaveAttribute("tabindex", "-1");
    expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", "tab-overview");
  });
});
