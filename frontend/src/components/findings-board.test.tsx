import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FindingsBoard } from "./findings-board";

const search = vi.hoisted(() => ({ value: "" }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(search.value),
}));

afterEach(() => {
  vi.unstubAllGlobals();
  search.value = "";
});

const item = {
  id: "f1",
  agent: "quick-scan",
  title: "API call answered 500: GET /api/plans",
  severity: "High",
  category: "regression",
  location: "/ · mobile",
  expected: "HTTP 2xx/3xx",
  actual: "HTTP 500",
  suggested_fix: null,
  evidence: [],
  status: "open",
  ignore_reason: null,
  fingerprint: "x",
  run_id: "20261117-101010-quick-scan-abcdef",
  run_title: "Quick Scan · mocked",
  run_started_at: "2026-11-17T10:10:10Z",
};

describe("FindingsBoard", () => {
  it("lists open findings grouped by run", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify([item]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<FindingsBoard />);

    expect(await screen.findByText("API call answered 500: GET /api/plans")).toBeInTheDocument();
    expect(screen.getByText("1 open finding")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Quick Scan · mocked" })).toHaveAttribute(
      "href",
      "/runs/20261117-101010-quick-scan-abcdef",
    );
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/findings\?status=open$/);
  });

  it("filters by the agent tab in the URL", async () => {
    search.value = "agent=code-reviewer";
    const fetchMock = vi.fn().mockResolvedValue(new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<FindingsBoard />);

    expect(await screen.findByText("Nothing to review.")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toMatch(/status=open&agent=code-reviewer$/);
    expect(screen.getByRole("link", { name: "Code review" })).toHaveAttribute("aria-current", "page");
  });

  it("shows a retryable error when the backend is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    render(<FindingsBoard />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load findings: Failed to fetch");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
