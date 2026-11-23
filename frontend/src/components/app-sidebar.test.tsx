import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppSidebar } from "./app-sidebar";
import type { QaConfigSummary } from "@/lib/api";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));

afterEach(() => vi.unstubAllGlobals());

const config: QaConfigSummary = {
  app_url: "http://localhost:3000",
  app_repo_path: null,
  pages: [],
  viewports: [],
  designs: [],
  agents: [
    { name: "functionality-tester", description: "", standalone: true },
    { name: "code-reviewer", description: "", standalone: true },
    { name: "qa-lead", description: "", standalone: false },
    { name: "test-case-reviewer", description: "", standalone: false },
    { name: "qa-reporter", description: "", standalone: false },
    { name: "test-writer", description: "", standalone: false },
  ],
};

describe("AppSidebar", () => {
  it("lists only the agents you can run on their own", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => new Response(JSON.stringify(url.includes("qa-config") ? config : []), { status: 200 })),
    );
    render(<AppSidebar />);

    expect(await screen.findByRole("link", { name: "Functionality tester" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Code reviewer" })).toBeInTheDocument();
    for (const hidden of ["QA Lead", "qa-reporter", "test-case-reviewer", "Test writer"]) {
      expect(screen.queryByRole("link", { name: hidden })).not.toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: "Check my change" })).toBeInTheDocument();
  });
});
