---
description: Guide the setup and use of pre-commit hooks, linting, formatting, type-checking, and test gates in the FastAPI backend (`backend/`).
paths:
  - "backend/**"
---
# Pre-Commit Quality Gates

Guide the setup and use of pre-commit hooks, linting, formatting, type-checking, and test gates in the FastAPI backend (`backend/`).

Use this rule during the Build, Test, and Ship stages.

Before committing or pushing any code, ensure you have run the local checks. Do not rely solely on CI to catch basic errors.

## AI Responsibilities

- Run the project's pre-commit checks before proposing a commit.
- Confirm that linting, formatting, and type-check pass on changed files.
- Do not bypass hooks (`--no-verify`) unless explicitly instructed and the reason is documented.
- When adding a new package or changing config, verify that the pre-commit suite still passes.
- For backend projects, also confirm that affected unit tests pass before committing.

## AI Must Avoid

- Committing files that fail the linter or formatter.
- Suggesting `git commit --no-verify` as a routine workaround for hook failures.
- Introducing lint rule exceptions (`# noqa`, `# type: ignore`) without a named justification.
- Skipping type-check on files that interact with external API contracts or database schemas.

## Stack-Specific Guidance

### The Gates
Run from `backend/` before every commit; all must pass:

```bash
uv run ruff format --check .   # formatting
uv run ruff check .            # lint (incl. isort, bugbear, bandit rules)
uv run mypy src tests          # strict type check
uv run pytest                  # tests
```

### Fix-First Heuristic
- `uv run ruff check --fix . && uv run ruff format .` resolves most lint/format issues; review the diff after.
- Fix type errors properly — add precise types rather than `Any`.

### Suppressions
- `# noqa: <CODE>` and `# type: ignore[<code>]` must name the specific code and carry a one-line reason.
- Never add blanket per-file ignores in `pyproject.toml` without approval.

## Acceptance Criteria

- All changed files pass the linter and formatter before commit.
- Type-check passes on changed modules, especially those touching API contracts or data models.
- Pre-commit hooks are not bypassed without documented reason.
