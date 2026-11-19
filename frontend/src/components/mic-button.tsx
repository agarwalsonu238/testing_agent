"use client";

import { Mic, Square } from "lucide-react";

import { useSpeechToText } from "@/hooks/use-speech-to-text";
import { Button } from "@/components/ui/button";

/**
 * A small mic toggle next to a textarea: dictates instead of typing, appending each finished
 * sentence via `onText`. Renders nothing when the browser has no speech recognition.
 */
export function MicButton({ onText, label }: { onText: (text: string) => void; label: string }) {
  const { supported, listening, error, toggle } = useSpeechToText(onText);
  if (!supported) return null;

  return (
    <span className="inline-flex items-center gap-2">
      <Button
        type="button"
        size="sm"
        variant={listening ? "default" : "outline"}
        aria-pressed={listening}
        onClick={toggle}
      >
        {listening ? (
          <>
            <Square aria-hidden className="size-3.5" /> Stop
          </>
        ) : (
          <>
            <Mic aria-hidden className="size-3.5" /> {label}
          </>
        )}
      </Button>
      {listening && (
        <span role="status" className="text-xs text-muted-foreground">
          Listening…
        </span>
      )}
      {error && (
        <span role="alert" className="text-xs text-destructive">
          {error}
        </span>
      )}
    </span>
  );
}
