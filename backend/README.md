# backend

FastAPI service, managed with [uv](https://docs.astral.sh/uv/). Python 3.12.

```bash
cp .env.example .env
uv sync                                         # install deps (incl. dev group)
uv run uvicorn app.main:app --reload            # http://localhost:8000/docs
uv run qa-mcp-server                            # MCP server for Cursor/Antigravity/etc. (needs the above running)
uv run pytest                                   # tests
uv run ruff check . && uv run ruff format .     # lint + format
uv run mypy src tests                           # type check (strict)
```

## Layout

```
src/app/
  main.py            # create_app() factory, CORS, router mount
  mcp_server.py       # MCP server wrapping this API for other AI coding tools (see repo README)
  core/config.py     # pydantic-settings Settings (env / .env)
  api/router.py      # aggregates routers under /api/v1
  api/routes/        # one module per resource (health.py, ...)
tests/               # pytest + httpx AsyncClient against create_app()
```
