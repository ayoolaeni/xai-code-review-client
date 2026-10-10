import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConfidenceBadge, SeverityBadge, SourceBadge } from "../../src/components/Badges";

describe("badges show text labels, not only colour (NFR8)", () => {
  it("severity", () => {
    render(<SeverityBadge level="CRITICAL" />);
    expect(screen.getByText("Severity: Critical")).toBeInTheDocument();
  });

  it("severity without prefix and NONE", () => {
    render(<SeverityBadge level="NONE" prefix="" />);
    expect(screen.getByTestId("severity-badge")).toHaveTextContent("None");
  });

  it("confidence", () => {
    render(<ConfidenceBadge level="LOW" />);
    expect(screen.getByText("Confidence: Low")).toBeInTheDocument();
  });

  it.each([
    ["both", "Found by: static analysis + AI"],
    ["static", "Found by: static analysis only"],
    ["llm", "Found by: AI only"],
  ] as const)("source %s", (source, text) => {
    render(<SourceBadge source={source} />);
    expect(screen.getByTestId("source-badge")).toHaveTextContent(text);
  });
});
