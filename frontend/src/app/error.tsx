"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";

export default function RouteError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Dashboard page crashed", { message: error.message, digest: error.digest });
  }, [error]);

  return (
    <div role="alert" className="grid gap-3">
      <h1 className="text-2xl font-semibold">This page hit an error</h1>
      <p className="text-muted-foreground">{error.message}</p>
      <div>
        <Button onClick={reset}>Try again</Button>
      </div>
    </div>
  );
}
