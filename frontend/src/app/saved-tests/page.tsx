import type { Metadata } from "next";

import { SavedTestsList } from "@/components/saved-tests-list";

export const metadata: Metadata = { title: "Saved tests" };

export default function SavedTestsPage() {
  return (
    <section className="grid gap-4" aria-labelledby="saved-heading">
      <div>
        <h1 id="saved-heading" className="text-2xl font-semibold tracking-tight">
          Saved tests
        </h1>
        <p className="text-muted-foreground">
          From the app repo&apos;s test registry. Each one re-runs as a normal Playwright test, without AI.
        </p>
      </div>
      <SavedTestsList />
    </section>
  );
}
