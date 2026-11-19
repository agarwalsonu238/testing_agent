import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EvidenceView } from "./evidence-view";
import type { Evidence } from "@/lib/api";

describe("EvidenceView", () => {
  it("collapses screenshots behind a toggle instead of showing them open", () => {
    const evidence: Evidence[] = [
      { kind: "screenshot", label: "home-desktop.png", path: "screenshots/home-desktop.png", text: null },
    ];
    render(<EvidenceView runId="r1" evidence={evidence} />);

    const toggle = screen.getByText("Show screenshot").closest("summary");
    expect(toggle).toBeInTheDocument();
    expect(toggle?.closest("details")).not.toHaveAttribute("open");
    // Still in the document (so it renders instantly on click) — just collapsed, not removed.
    expect(screen.getByRole("img", { name: "screenshot home-desktop.png" })).toBeInTheDocument();
  });

  it("counts multiple screenshots in the toggle label", () => {
    const evidence: Evidence[] = [
      { kind: "screenshot", label: "a.png", path: "a.png", text: null },
      { kind: "design", label: "Design (mobile)", path: "b.png", text: null },
    ];
    render(<EvidenceView runId="r1" evidence={evidence} />);
    expect(screen.getByText("Show screenshots (2)")).toBeInTheDocument();
  });

  it("renders nothing for a finding with no evidence", () => {
    const { container } = render(<EvidenceView runId="r1" evidence={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
