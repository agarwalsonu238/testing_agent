import type { Metadata } from "next";

import { StartRunForm } from "@/components/start-run-form";

export const metadata: Metadata = { title: "Quick Scan" };

export default function QuickScanPage() {
  return (
    <section className="grid gap-6" aria-labelledby="scan-heading">
      <div className="grid gap-1">
        <h1 id="scan-heading" className="text-2xl font-semibold tracking-tight">
          Quick Scan
        </h1>
        <p className="max-w-2xl text-muted-foreground">
          No AI. Opens every page the project lists (or, with none listed, the pages it finds by following links
          from the home page) at desktop and mobile size, scrolls to the bottom, and reports console errors, failed
          or slow API calls, broken images and links, and pages wider than the screen.
        </p>
      </div>
      <StartRunForm variant={{ kind: "quick-scan" }} />
    </section>
  );
}
