FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.10 /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Node.js (for `npx` — the agents' Playwright MCP server — and the Claude Code CLI, which is a
# Node package) plus git (Check my change / the API checker need a real checkout to diff).
# This is the heavy part of the image: expect ~1GB+ and a real RAM budget once Chromium is
# added below — a free-tier instance (e.g. Render's) may need to go to a paid tier for agent
# runs to be reliable. Quick Scan alone is lighter but still needs the browser.
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates git gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Pinned to CLAUDE_CODE_VERSION in .env.example — re-check headless subscription login
# (CLAUDE_CODE_OAUTH_TOKEN, from `claude setup-token` run locally) after bumping either.
RUN npm install -g @anthropic-ai/claude-code@2.1.328

# Install dependencies first (cached layer), then the project itself
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY qa ./qa
COPY README.md ./
RUN uv sync --frozen --no-dev

# Playwright's own Chromium + its OS-level deps (Quick Scan and every agent's Playwright MCP
# call need a real browser; there's no running this headless-only).
RUN uv run playwright install --with-deps chromium

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
