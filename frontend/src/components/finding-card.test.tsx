import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FindingCard } from "./finding-card";
import type { Finding } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

const finding: Finding = {
  id: "f1",
  agent: "design-reviewer",
  title: "Card spacing differs from the design",
  severity: "Medium",
  category: "regression",
  location: "/pricing · mobile",
  expected: "24px gap",
  actual: "12px gap",
  suggested_fix: null,
  evidence: [
    { kind: "screenshot", label: "pricing-mobile.png", path: "agent-output/design-reviewer/pricing-mobile.png", text: null },
    { kind: "design", label: "Design (mobile)", path: "designs/pricing.mobile.png", text: null },
  ],
  status: "open",
  ignore_reason: null,
  fingerprint: "abc",
};

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

describe("FindingCard", () => {
  it("shows the page screenshot and the design side by side", () => {
    render(<FindingCard runId="r1" finding={finding} />);

    expect(screen.getByText("Design reviewer · /pricing · mobile")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "screenshot pricing-mobile.png" })).toHaveAttribute(
      "src",
      expect.stringContaining("/runs/r1/files/agent-output/design-reviewer/pricing-mobile.png"),
    );
    expect(screen.getByRole("img", { name: "design Design (mobile)" })).toBeInTheDocument();
  });

  it("needs a reason before ignoring and doesn't call the API without one", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<FindingCard runId="r1" finding={finding} />);

    fireEvent.click(screen.getByRole("button", { name: "Ignore" }));
    fireEvent.click(screen.getByRole("button", { name: "Ignore finding" }));

    expect(screen.getByRole("alert")).toHaveTextContent("one-line reason");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("ignores with a reason and reports the decision", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(json({ ...finding, status: "ignored", ignore_reason: "Known issue" }));
    vi.stubGlobal("fetch", fetchMock);
    const onDecided = vi.fn();
    render(<FindingCard runId="r1" finding={finding} onDecided={onDecided} />);

    fireEvent.click(screen.getByRole("button", { name: "Ignore" }));
    fireEvent.change(screen.getByLabelText("Why ignore it?"), { target: { value: "Known issue" } });
    fireEvent.click(screen.getByRole("button", { name: "Ignore finding" }));

    expect(await screen.findByText("Ignored: Known issue")).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/runs\/r1\/findings\/f1\/decision$/);
    expect(JSON.parse(init.body as string)).toEqual({ decision: "ignore", reason: "Known issue" });
    expect(onDecided).toHaveBeenCalledWith(expect.objectContaining({ status: "ignored" }));
  });

  it("shows the backend's error message when a decision fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(json({ detail: "Wait until the run finishes before deciding on its findings" }, 409)),
    );
    render(<FindingCard runId="r1" finding={finding} />);

    fireEvent.click(screen.getByRole("button", { name: "Accept" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Wait until the run finishes");
  });
});
