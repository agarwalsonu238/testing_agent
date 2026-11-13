import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BackendStatus } from "./backend-status";

afterEach(() => vi.unstubAllGlobals());

describe("BackendStatus", () => {
  it("shows the backend health when the API responds", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "ok", environment: "local" }), { status: 200 }),
      ),
    );

    render(<BackendStatus />);

    expect(await screen.findByText(/ok \(local\)/)).toBeInTheDocument();
  });

  it("shows an error when the API fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 503 })));

    render(<BackendStatus />);

    expect(await screen.findByText(/failed with 503/)).toBeInTheDocument();
  });
});
