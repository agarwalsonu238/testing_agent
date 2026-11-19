"use client";

import type { RunMode } from "@/lib/api";

const OPTIONS: { value: RunMode; label: string; hint: string }[] = [
  { value: "mocked", label: "Mocked API", hint: "Same mocks as the isolated tests (default)" },
  { value: "real", label: "Real backend", hint: "Shared test account; risky endpoints blocked" },
];

export function ModePicker({
  value,
  onChange,
  disabled,
}: {
  value: RunMode;
  onChange: (mode: RunMode) => void;
  disabled?: boolean;
}) {
  return (
    <fieldset className="grid gap-2" disabled={disabled}>
      <legend className="mb-1 text-sm font-medium">Run mode</legend>
      {OPTIONS.map((option) => (
        <label
          key={option.value}
          className="flex cursor-pointer items-start gap-2 rounded-lg border p-2.5 text-sm has-checked:border-ring has-checked:bg-muted"
        >
          <input
            type="radio"
            name="run-mode"
            value={option.value}
            checked={value === option.value}
            onChange={() => onChange(option.value)}
            className="mt-0.5 accent-primary"
          />
          <span>
            <span className="font-medium">{option.label}</span>
            <span className="block text-muted-foreground">{option.hint}</span>
          </span>
        </label>
      ))}
    </fieldset>
  );
}
