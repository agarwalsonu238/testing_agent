"""Claude Code in headless mode (`claude -p`) on the developer's own subscription login.

Rules enforced here:
- never `--bare` (bare mode ignores subscription logins);
- refuse to start while an API-billing credential is set, and strip those variables from the
  child env;
- stop a run whose `init` event reports any `apiKeySource` other than `none` (= subscription login).
"""

import asyncio
import contextlib
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import Settings, child_process_env
from app.integrations.process import ProcessError, run_process

logger = logging.getLogger(__name__)

SUBSCRIPTION_KEY_SOURCE = "none"
_STREAM_LIMIT = 64 * 1024 * 1024  # tool results can carry base64 screenshots
_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

ProgressFn = Callable[[str, str], None]  # (level, message)


class ClaudeCodeError(Exception):
    """Claude Code couldn't run, or ran on a billed credential."""


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]
    result_text: str = ""
    is_error: bool | None = None  # None until the result arrives


@dataclass
class ClaudeRunResult:
    ok: bool
    result_text: str = ""
    structured: dict[str, Any] | None = None
    api_key_source: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    error: str | None = None
    permission_denials: int = 0
    num_turns: int | None = None


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Find the JSON object in a reply: bare JSON, a ```json fence, or the outermost braces."""
    candidates = [text.strip()]
    candidates += [m.group(1) for m in _JSON_FENCE.finditer(text)]
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(value, dict):
            return value
    return None


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        ]
        return "\n".join(parts)
    return ""


def scrub_images(value: Any) -> Any:
    """Drop base64 image payloads before an event is written to the run's raw log."""
    if isinstance(value, dict):
        if value.get("type") == "image":
            return {"type": "image", "omitted": True}
        return {k: scrub_images(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub_images(v) for v in value]
    return value


def _short_tool(name: str) -> str:
    return name.split("__")[-1]


def _brief(data: dict[str, Any]) -> str:
    for key in ("url", "element", "text", "file_path", "pattern", "filename", "key"):
        if isinstance(data.get(key), str):
            return str(data[key])[:120]
    return ""


class StreamParser:
    """Turns `--output-format stream-json` events into tool calls, a result and progress lines."""

    def __init__(self) -> None:
        self.calls: dict[str, ToolCall] = {}
        self.api_key_source: str | None = None
        self.result: dict[str, Any] | None = None

    def feed(self, event: dict[str, Any]) -> list[tuple[str, str]]:
        kind = event.get("type")
        out: list[tuple[str, str]] = []
        if kind == "system" and event.get("subtype") == "init":
            self.api_key_source = str(event.get("apiKeySource"))
            servers = ", ".join(
                f"{s.get('name')}:{s.get('status')}" for s in event.get("mcp_servers") or []
            )
            out.append(
                (
                    "info",
                    f"Claude Code {event.get('claude_code_version', '?')} started"
                    f" (model {event.get('model', '?')}; MCP {servers or 'none'})",
                )
            )
        elif kind == "assistant":
            for block in (event.get("message") or {}).get("content") or []:
                if block.get("type") == "text" and block.get("text", "").strip():
                    out.append(("info", block["text"].strip()[:400]))
                elif block.get("type") == "tool_use":
                    call = ToolCall(
                        id=str(block.get("id")),
                        name=str(block.get("name")),
                        input=block.get("input") or {},
                    )
                    self.calls[call.id] = call
                    out.append(
                        ("info", f"→ {_short_tool(call.name)} {_brief(call.input)}".rstrip())
                    )
        elif kind == "user":
            for block in (event.get("message") or {}).get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                result_call = self.calls.get(str(block.get("tool_use_id")))
                if result_call is None:
                    continue
                result_call.result_text = _content_text(block.get("content"))
                result_call.is_error = bool(block.get("is_error"))
                if result_call.is_error:
                    msg = result_call.result_text.strip().splitlines()
                    detail = msg[0][:200] if msg else ""
                    out.append(("warn", f"✗ {_short_tool(result_call.name)} failed: {detail}"))
        elif kind == "result":
            self.result = event
        return out

    def finish(self) -> ClaudeRunResult:
        calls = list(self.calls.values())
        if self.result is None:
            return ClaudeRunResult(
                ok=False,
                error="Claude Code ended without a result",
                api_key_source=self.api_key_source,
                tool_calls=calls,
            )
        text = str(self.result.get("result") or "")
        structured = self.result.get("structured_output")
        if not isinstance(structured, dict):
            structured = extract_json_object(text)
        is_error = bool(self.result.get("is_error")) or self.result.get("subtype") != "success"
        return ClaudeRunResult(
            ok=not is_error,
            result_text=text,
            structured=structured,
            api_key_source=self.api_key_source,
            tool_calls=calls,
            error=(text or str(self.result.get("subtype"))) if is_error else None,
            permission_denials=len(self.result.get("permission_denials") or []),
            num_turns=self.result.get("num_turns"),
        )


@dataclass
class AgentInvocation:
    prompt: str
    cwd: Path
    agents_json: str
    agent: str
    allowed_tools: list[str]
    disallowed_tools: list[str]
    add_dirs: list[Path]
    mcp_config: Path | None
    json_schema: dict[str, Any] | None
    raw_log: Path


class ClaudeCode:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build_argv(self, inv: AgentInvocation) -> list[str]:
        s = self._settings
        argv = [
            s.claude_bin,
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "dontAsk",
            "--agents",
            inv.agents_json,
            "--agent",
            inv.agent,
            "--no-session-persistence",
        ]
        if s.claude_model:
            argv += ["--model", s.claude_model]
        if inv.mcp_config is not None:
            argv += ["--mcp-config", str(inv.mcp_config), "--strict-mcp-config"]
        if inv.json_schema is not None:
            argv += ["--json-schema", json.dumps(inv.json_schema)]
        # Variadic options take everything up to the next flag; the prompt goes through stdin.
        if inv.allowed_tools:
            argv += ["--allowedTools", *inv.allowed_tools]
        if inv.disallowed_tools:
            argv += ["--disallowedTools", *inv.disallowed_tools]
        if inv.add_dirs:
            argv += ["--add-dir", *[str(d) for d in inv.add_dirs]]
        assert "--bare" not in argv  # noqa: S101 - invariant: bare mode ignores subscription logins
        return argv

    def ensure_no_billed_credentials(self) -> None:
        found = self._settings.billed_credentials_set()
        if found:
            raise ClaudeCodeError(
                f"{', '.join(found)} is set. Claude Code would bill the API instead of your "
                "subscription, so agent runs are refused. Remove it from your shell profile "
                "and .env."
            )

    async def run(
        self, inv: AgentInvocation, on_progress: ProgressFn, timeout_s: float | None = None
    ) -> ClaudeRunResult:
        self.ensure_no_billed_credentials()
        argv = self.build_argv(inv)
        timeout = timeout_s or self._settings.claude_run_timeout_s
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=inv.cwd,
                env=child_process_env(self._settings),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=_STREAM_LIMIT,
            )
        except FileNotFoundError as exc:
            raise ClaudeCodeError(f"`{self._settings.claude_bin}` was not found on PATH") from exc

        assert proc.stdin and proc.stdout and proc.stderr  # noqa: S101 - pipes requested above
        proc.stdin.write(inv.prompt.encode())
        await proc.stdin.drain()
        proc.stdin.close()

        stderr_tail: list[str] = []

        async def drain_stderr() -> None:
            assert proc.stderr  # noqa: S101 - pipe requested above
            async for line in proc.stderr:
                stderr_tail.append(line.decode(errors="replace").rstrip())
                del stderr_tail[:-20]

        parser = StreamParser()
        stderr_task = asyncio.create_task(drain_stderr())
        stopped_reason: str | None = None
        try:
            async with asyncio.timeout(timeout):
                with inv.raw_log.open("a", encoding="utf-8") as raw:
                    async for line in proc.stdout:
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        raw.write(json.dumps(scrub_images(event)) + "\n")
                        for level, message in parser.feed(event):
                            on_progress(level, message)
                        source = parser.api_key_source
                        if source is not None and source != SUBSCRIPTION_KEY_SOURCE:
                            stopped_reason = (
                                f"Claude Code reported credential source '{source}' instead of "
                                "your "
                                "subscription login, so the run was stopped before any work."
                            )
                            break
            if stopped_reason:
                proc.kill()
            await proc.wait()
        except TimeoutError:
            proc.kill()
            await proc.wait()
            stopped_reason = f"Claude Code didn't finish within {timeout:.0f}s"
        except asyncio.CancelledError:
            proc.terminate()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(proc.wait(), 5)
            if proc.returncode is None:
                proc.kill()
            raise
        finally:
            stderr_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await stderr_task

        result = parser.finish()
        if stopped_reason:
            result.ok = False
            result.error = stopped_reason
        elif result.error and stderr_tail and parser.result is None:
            result.error = f"{result.error}: {' | '.join(stderr_tail[-3:])}"
        return result

    async def version(self) -> str | None:
        try:
            res = await run_process(
                [self._settings.claude_bin, "--version"],
                env=child_process_env(self._settings),
                timeout_s=20,
            )
        except ProcessError:
            return None
        match = re.search(r"\d+\.\d+\.\d+", res.stdout)
        return match.group(0) if res.ok and match else None

    async def auth_status(self) -> dict[str, Any] | None:
        """`claude auth status` (free; no model call). Only non-personal fields are kept."""
        try:
            res = await run_process(
                [self._settings.claude_bin, "auth", "status"],
                env=child_process_env(self._settings),
                timeout_s=20,
            )
        except ProcessError:
            return None
        data = extract_json_object(res.stdout)
        if data is None:
            return None
        keep = ("loggedIn", "authMethod", "apiProvider", "subscriptionType", "loginExpiresAt")
        return {k: data.get(k) for k in keep}

    async def smoke_test(self) -> tuple[bool, str]:
        """A one-line headless run on the developer's login (uses a little plan usage)."""
        self.ensure_no_billed_credentials()
        try:
            res = await run_process(
                [
                    self._settings.claude_bin,
                    "-p",
                    "--output-format",
                    "json",
                    "--no-session-persistence",
                    "--tools",
                    "",
                ],
                env=child_process_env(self._settings),
                timeout_s=90,
                stdin="Reply with the single word OK.",
            )
        except ProcessError as exc:
            return False, str(exc)
        data = extract_json_object(res.stdout)
        if not res.ok or data is None:
            tail = (res.stderr or res.stdout).strip().splitlines()[-1:] or ["no output"]
            return False, f"Exit code {res.code}: {tail[0][:200]}"
        if data.get("is_error"):
            return False, str(data.get("result"))[:200]
        return True, f"Reply: {str(data.get('result')).strip()[:40]}"
