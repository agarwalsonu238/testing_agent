import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentSteps, defaultStage, ReviewStage, StageTabs, stageStates, type StageKey } from "./run-stages";
import type { RunDetail, TestCase } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

const testCase = (over: Partial<TestCase>): TestCase => ({
  id: "TC-1",
  title: "Guest books a stay",
  agent: "functionality-tester",
  steps: [],
  expected: "",
  status: "planned",
  note: null,
  review_note: null,
  review_status: "approved",
  ...over,
});

const run = (over: Partial<RunDetail>) =>
  ({
    id: "r1",
    status: "finished",
    stage: null,
    activity: null,
    awaiting_approval: false,
    plan_summary: "Plan",
    test_cases: [],
    agents: [],
    ...over,
  }) as RunDetail;

describe("stage progress", () => {
  it("follows the stage the backend reports while the run is going", () => {
    const running = (stage: RunDetail["stage"]) => run({ status: "running", stage, test_cases: [testCase({})] });
    expect(defaultStage(running("planning"))).toBe("plan");
    expect(defaultStage(running("reviewing"))).toBe("review");
    expect(defaultStage(running("awaiting_approval"))).toBe("review");
    expect(defaultStage(running("running"))).toBe("run");
    expect(defaultStage(running("reporting"))).toBe("report");
    expect(stageStates(running("reporting"))).toMatchObject({ run: "done", report: "active" });
  });

  it("infers the stage for runs saved before stages existed", () => {
    expect(defaultStage(run({ status: "running", plan_summary: null }))).toBe("plan");
    expect(defaultStage(run({ status: "running", plan_summary: "Plan" }))).toBe("review");
    expect(defaultStage(run({ status: "running", test_cases: [testCase({})] }))).toBe("run");
  });

  it("opens a finished run on the last stage it reached", () => {
    const agent = [{ agent: "functionality-tester" }] as RunDetail["agents"];
    expect(defaultStage(run({ test_cases: [testCase({})], agents: agent }))).toBe("report");
    // Blocked before anything ran: the report tab would be empty.
    expect(defaultStage(run({ test_cases: [testCase({})], agents: [] }))).toBe("review");
  });
});

describe("ReviewStage", () => {
  it("shows what the reviewer approved, rewrote and rejected", () => {
    render(
      <ReviewStage
        run={run({
          test_cases: [
            testCase({ id: "TC-1", review_status: "approved" }),
            testCase({ id: "TC-2", review_status: "rewritten", review_note: "Made the expected line concrete" }),
            testCase({ id: "TC-3", review_status: "rejected", status: "skipped", note: "No file named" }),
          ],
        })}
      />,
    );
    expect(screen.getByText(/1 approved as written · 1 rewritten · 1 rejected/)).toBeInTheDocument();
    expect(screen.getByText("What changed: Made the expected line concrete")).toBeInTheDocument();
    expect(screen.getByText("Why: No file named")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
  });

  it("lets you untick cases and sends only those you skip when you approve", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({}), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const onApproved = vi.fn();
    render(
      <ReviewStage
        onApproved={onApproved}
        run={run({
          status: "running",
          stage: "awaiting_approval",
          awaiting_approval: true,
          test_cases: [
            testCase({ id: "TC-1" }),
            testCase({ id: "TC-2", title: "Cancel a stay" }),
            testCase({ id: "TC-3", review_status: "rejected", status: "skipped", note: "vague" }),
          ],
        })}
      />,
    );
    expect(screen.getByRole("button", { name: "Approve and run 2 cases" })).toBeInTheDocument();
    // A rejected case can't be run, so it has no checkbox.
    expect(screen.queryByRole("checkbox", { name: "Run TC-3" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: "Run TC-2" }));
    fireEvent.click(screen.getByRole("button", { name: "Approve and run 1 case" }));

    await waitFor(() => expect(onApproved).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/runs/r1/approve");
    expect(JSON.parse(init.body as string)).toEqual({ skip: ["TC-2"] });
  });
});

describe("AgentSteps", () => {
  it("shows each agent in turn with where it stands", () => {
    render(
      <AgentSteps
        run={run({
          status: "running",
          stage: "running",
          activity: "code-reviewer · 2 of 2: Review this change",
          test_cases: [
            testCase({ id: "TC-1", status: "pass", note: "Booked fine" }),
            testCase({ id: "TC-2", agent: "code-reviewer", title: "api.py:1" }),
          ],
        })}
      />,
    );
    const names = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(names).toEqual(["Functionality tester Executed", "Code reviewer Running now"]);
    expect(screen.getByText("Booked fine")).toBeInTheDocument();
  });

  it("leaves out cases the reviewer rejected and marks agents that never started as not run", () => {
    render(
      <AgentSteps
        run={run({
          test_cases: [
            testCase({ id: "TC-1", agent: "api-checker", title: "GET /x" }),
            testCase({ id: "TC-2", agent: "api-checker", title: "Rejected one", review_status: "rejected", status: "skipped" }),
          ],
        })}
      />,
    );
    expect(screen.getByText(/TC-1 · GET \/x/)).toBeInTheDocument();
    expect(screen.queryByText(/Rejected one/)).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3 })).toHaveTextContent("API checker Not run");
  });
});

describe("StageTabs", () => {
  function Harness() {
    const [stage, setStage] = useState<StageKey>("plan");
    return <StageTabs run={run({ test_cases: [testCase({})] })} selected={stage} onSelect={setStage} />;
  }

  it("switches stage on click and with the arrow keys", () => {
    render(<Harness />);
    const tab = (name: RegExp) => screen.getByRole("tab", { name });
    expect(tab(/1 · Plan/)).toHaveAttribute("aria-selected", "true");
    fireEvent.click(tab(/3 · Run/));
    expect(tab(/3 · Run/)).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(tab(/3 · Run/), { key: "ArrowRight" });
    expect(tab(/4 · Report/)).toHaveAttribute("aria-selected", "true");
  });
});
