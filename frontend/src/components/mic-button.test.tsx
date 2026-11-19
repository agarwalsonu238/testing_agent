import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MicButton } from "./mic-button";

describe("MicButton", () => {
  it("renders nothing when the browser has no speech recognition", () => {
    const { container } = render(<MicButton onText={() => {}} label="Dictate" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("starts listening on click when speech recognition is available", async () => {
    class FakeRecognition {
      continuous = false;
      interimResults = false;
      lang = "";
      onresult: unknown;
      onerror: unknown;
      onend: unknown;
      start = vi.fn();
      stop = vi.fn();
    }
    vi.stubGlobal("webkitSpeechRecognition", FakeRecognition);

    render(<MicButton onText={() => {}} label="Dictate" />);
    const button = screen.getByRole("button", { name: /dictate/i });
    button.click();
    expect(await screen.findByText("Listening…")).toBeInTheDocument();

    vi.unstubAllGlobals();
  });
});
