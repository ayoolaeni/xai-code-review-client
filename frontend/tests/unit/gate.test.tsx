import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { ImprovedCodeTab } from "../../src/components/report/ImprovedCodeTab";
import { finding, report } from "./fixtures";

function Harness({ r = report() }) {
  const [opened, setOpened] = useState<Set<string>>(new Set());
  return (
    <ImprovedCodeTab report={r} opened={opened} onOpenFinding={(k) => setOpened((s) => new Set(s).add(k))} />
  );
}

describe("cognitive-forcing gate (Section 11.5)", () => {
  it("does not render the diff until every CRITICAL finding is opened", async () => {
    const user = userEvent.setup();
    const r = report({
      findings: [
        finding({ key: "F1" }),
        finding({ key: "F2", title: "Command injection", start_line: 9, end_line: 9 }),
      ],
    });
    render(<Harness r={r} />);
    expect(screen.getByTestId("ack-gate")).toHaveTextContent("This code has 2 critical finding(s)");
    expect(screen.queryByTestId("monaco-diff")).not.toBeInTheDocument();

    const buttons = screen.getAllByRole("button", { name: "Open" });
    await user.click(buttons[0]);
    expect(screen.queryByTestId("monaco-diff")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.getByTestId("monaco-diff")).toBeInTheDocument();
    expect(screen.getByText(/You reviewed the critical findings/)).toBeInTheDocument();
  });

  it("shows the diff directly when there are no critical findings", () => {
    const r = report({ findings: [finding({ severity: "HIGH" })] });
    render(<Harness r={{ ...r, improved: { ...r.improved, requires_acknowledgement: false } }} />);
    expect(screen.getByTestId("monaco-diff")).toBeInTheDocument();
    expect(screen.queryByTestId("ack-gate")).not.toBeInTheDocument();
  });

  it("explains when no improved version is available", () => {
    const r = report();
    render(<Harness r={{ ...r, improved: { ...r.improved, available: false, improved_code: null } }} />);
    expect(screen.getByText("No improved version is available")).toBeInTheDocument();
  });

  it("warns when automatic checks found problems", () => {
    const r = report({ findings: [finding({ severity: "LOW" })] });
    render(
      <Harness
        r={{
          ...r,
          improved: {
            ...r.improved,
            requires_acknowledgement: false,
            has_problems: true,
            check: {
              syntax_ok: false,
              syntax_message: "Line 2: invalid syntax",
              remaining_static_findings: null,
              new_high_or_critical: null,
            },
          },
        }}
      />,
    );
    expect(screen.getByText(/Do not copy it without reviewing it/)).toBeInTheDocument();
    expect(screen.getByText(/Line 2: invalid syntax/)).toBeInTheDocument();
  });
});
