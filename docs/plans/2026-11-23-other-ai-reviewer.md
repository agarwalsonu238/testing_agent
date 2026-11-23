# Plan: Let another AI review the test cases

- **Date:** 2026-11-23
- **Status:** approved by the developer ("review by another agent: Gemini, Perplexity… I give an example")
- **Sides:** backend (config, integration, orchestration) + frontend (one line on the Review tab)

## Decision
Only the **review** stage can move to another provider. Plan needs the diff, run needs the browser and
repo, report needs the executor's evidence folder: all Claude Code. The reviewer reads only the draft
cases and has no tools, so it is plain text in, JSON out.

One small OpenAI-compatible chat-completions client (`integrations/external_reviewer.py`, `httpx`, already
a dependency) covers Gemini, Perplexity, OpenAI and any other compatible API (`custom` + base URL). No new
dependency. Presets only supply the base URL; the model name is required from the developer so a stale
default can never be used.

## Behaviour
- `REVIEWER_PROVIDER` (default `claude`), `REVIEWER_MODEL`, `REVIEWER_API_KEY`, `REVIEWER_BASE_URL`
  (custom), `REVIEWER_TIMEOUT_S`. A half-configured provider fails at startup.
- External reply is parsed leniently (fences, reasoning blocks), validated, and must contain one case per
  draft. Anything else is not trusted.
- On any failure Claude reviews instead; if that fails too the drafts go on **unreviewed** (no longer
  mislabelled "approved"). `RunRecord.reviewer` records who really reviewed.
- Setup check shows the reviewer; Review tab shows "Reviewed by …".

## Risks
- Privacy: draft cases leave the machine (code-review cases may quote changed lines). Opt-in, documented in
  `.env.example`, the README and the Setup check.
- Cost: billed to the provider key, not the Claude plan.
- Provider response shapes differ slightly; hence the lenient parser and the Claude fallback.

## Test plan
- Unit: JSON extraction, request shape and key handling, error mapping without leaking the key, settings
  validation, external success / failure-fallback / wrong-count / both-fail paths.
- Not run: a live call to a real provider (needs the developer's key).
