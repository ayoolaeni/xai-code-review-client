import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { FindingCard } from "../../src/components/report/FindingCard";
import { filterAndSort, RisksTab } from "../../src/components/report/RisksTab";
import { finding, report } from "./fixtures";

function ControlledCard() {
  const [open, setOpen] = useState(false);
  return (
    <FindingCard
      finding={finding()}
      code={report().submission.original_code!}
      expanded={open}
      onToggle={setOpen}
    />
  );
}

describe("FindingCard", () => {
  it("expands and collapses and shows every part of the explanation", async () => {
    const user = userEvent.setup();
    render(<ControlledCard />);
    const toggle = screen.getByRole("button", { name: /SQL injection/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Why it matters")).not.toBeInTheDocument();

    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    for (const heading of ["Why it matters", "Evidence", "How to fix", "Why this confidence"]) {
      expect(screen.getByText(heading)).toBeInTheDocument();
    }
    expect(screen.getByText(/Found by both static analysis/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /CWE-89/ })).toHaveAttribute("rel", "noopener noreferrer");

    await user.click(screen.getByRole("button", { name: "Show in code" }));
    expect(screen.getByLabelText(/Code excerpt/)).toBeInTheDocument();

    await user.click(toggle);
    expect(screen.queryByText("Why it matters")).not.toBeInTheDocument();
  });

  it("shows the AI's view for static-only findings", () => {
    render(
      <FindingCard
        finding={finding({ source: "static", ai_assessment: "likely_false_positive" })}
        code=""
        expanded
        onToggle={() => undefined}
      />,
    );
    expect(screen.getByText(/thinks this may be a false positive/)).toBeInTheDocument();
  });
});

describe("RisksTab filtering and sorting", () => {
  const findings = report().findings;

  it("filterAndSort by severity and by line", () => {
    const all = { category: "all", severity: "all", source: "all" } as const;
    expect(filterAndSort(findings, all, "severity").map((f) => f.key)).toEqual(["F1", "F2", "F3"]);
    expect(filterAndSort(findings, all, "line").map((f) => f.key)).toEqual(["F2", "F1", "F3"]);
    expect(filterAndSort(findings, { ...all, source: "static" }, "severity").map((f) => f.key)).toEqual([
      "F2",
    ]);
    expect(
      filterAndSort(findings, { ...all, category: "performance" }, "severity").map((f) => f.key),
    ).toEqual(["F3"]);
  });

  it("filters through the controls", async () => {
    const user = userEvent.setup();
    render(
      <RisksTab
        findings={findings}
        code=""
        expanded={new Set()}
        onToggle={() => undefined}
        focusKey={null}
      />,
    );
    expect(screen.getAllByTestId("finding-card")).toHaveLength(3);
    await user.selectOptions(screen.getByLabelText("Severity"), "MEDIUM");
    const cards = screen.getAllByTestId("finding-card");
    expect(cards).toHaveLength(1);
    expect(within(cards[0]).getByText("Bare except")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Sort by"), "line");
    expect(screen.getByText("Showing 1 of 3 finding(s).")).toBeInTheDocument();
  });

  it("shows the empty state when there are no findings", () => {
    render(
      <RisksTab findings={[]} code="" expanded={new Set()} onToggle={() => undefined} focusKey={null} />,
    );
    expect(
      screen.getByText("No problems were found. This does not prove the code is safe."),
    ).toBeInTheDocument();
  });
});
