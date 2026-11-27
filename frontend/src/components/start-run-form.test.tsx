import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StartRunForm } from "./start-run-form";
import type { QaConfigSummary } from "@/lib/api";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

afterEach(() => vi.unstubAllGlobals());

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
});
