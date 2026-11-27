import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StartRunForm } from "./start-run-form";
import type { QaConfigSummary } from "@/lib/api";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

const config: QaConfigSummary = {
  app_url: "https://app.example.test",
  app_repo_path: "/repos/example-app",
  pages: [],
  viewports: [],
  designs: [],
  agents: [],
};

const stubFetch = (response: () => Response) => vi.stubGlobal("fetch", vi.fn(async () => response()));

describe("StartRunForm", () => {
  it("shows the server's default app URL and project folder as placeholders", async () => {
    stubFetch(() => new Response(JSON.stringify(config), { status: 200 }));
    render(<StartRunForm variant={{ kind: "quick-scan" }} />);

    expect(await screen.findByPlaceholderText("https://app.example.test")).toHaveValue("");
    expect(screen.getByPlaceholderText("/repos/example-app")).toHaveValue("");
  });

  it("falls back to example placeholders when the config can't be loaded", async () => {
    stubFetch(() => new Response("down", { status: 500 }));
    render(<StartRunForm variant={{ kind: "quick-scan" }} />);

    expect(await screen.findByPlaceholderText("https://my-app.example.com")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("/Users/you/Desktop/GitHub/my-project")).toBeInTheDocument();
  });

  it("requires a project folder for an agent when the server has no default", async () => {
    stubFetch(() => new Response(JSON.stringify({ ...config, app_repo_path: null }), { status: 200 }));
    render(<StartRunForm variant={{ kind: "agent", agent: "functionality-tester", needsRoute: false }} />);

    expect(await screen.findByText(/has no default folder/)).toBeInTheDocument();
    expect(screen.getByLabelText("Project folder")).toBeRequired();
  });

  it("keeps the folder optional for Quick Scan", async () => {
    stubFetch(() => new Response(JSON.stringify({ ...config, app_repo_path: null }), { status: 200 }));
    render(<StartRunForm variant={{ kind: "quick-scan" }} />);

    expect(await screen.findByLabelText("Project folder (optional)")).not.toBeRequired();
  });

  it("prefills the project last tested from this browser", async () => {
    window.localStorage.setItem(
      "qa.lastTarget",
      JSON.stringify({ appUrl: "https://app.zoqo.test", repoPath: "/repos/zoqo" }),
    );
    stubFetch(() => new Response(JSON.stringify(config), { status: 200 }));
    render(<StartRunForm variant={{ kind: "quick-scan" }} />);

    expect(await screen.findByDisplayValue("/repos/zoqo")).toBeInTheDocument();
    expect(screen.getByDisplayValue("https://app.zoqo.test")).toBeInTheDocument();
  });

  it("fills the project folder from the Mac folder picker", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) =>
      String(input).endsWith("/pick-folder")
        ? new Response(JSON.stringify({ path: "/Users/me/GitHub/zoqo-v2" }), { status: 200 })
        : new Response(JSON.stringify({ ...config, can_pick_folder: true }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<StartRunForm variant={{ kind: "quick-scan" }} />);

    fireEvent.click(await screen.findByRole("button", { name: /Browse/ }));

    expect(await screen.findByDisplayValue("/Users/me/GitHub/zoqo-v2")).toBeInTheDocument();
  });

  it("hides Browse when the backend can't open a picker", async () => {
    stubFetch(() => new Response(JSON.stringify({ ...config, can_pick_folder: false }), { status: 200 }));
    render(<StartRunForm variant={{ kind: "quick-scan" }} />);

    await screen.findByPlaceholderText("/repos/example-app");
    expect(screen.queryByRole("button", { name: /Browse/ })).not.toBeInTheDocument();
  });
});
