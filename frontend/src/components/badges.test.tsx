import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SeverityBadge, VerdictBadge } from "./badges";

describe("badges", () => {
  it("shows the verdict word, or RUNNING while a run has none", () => {
    const { rerender } = render(<VerdictBadge verdict="FAILING" />);
    expect(screen.getByText("FAILING")).toBeInTheDocument();
    rerender(<VerdictBadge verdict={null} />);
    expect(screen.getByText("RUNNING")).toBeInTheDocument();
  });

  it("shows the severity word (not colour alone)", () => {
    render(<SeverityBadge severity="Warning" />);
    expect(screen.getByText("Warning")).toBeInTheDocument();
  });
});
