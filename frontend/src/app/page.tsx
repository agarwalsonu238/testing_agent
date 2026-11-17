import { Suspense } from "react";

import { FindingsBoard } from "@/components/findings-board";

export default function ToReviewPage() {
  return (
    <Suspense fallback={<p className="text-muted-foreground">Loading findings…</p>}>
      <FindingsBoard />
    </Suspense>
  );
}
