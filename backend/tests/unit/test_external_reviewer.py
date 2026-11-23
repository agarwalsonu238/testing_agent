import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.integrations.claude_code import AgentInvocation, ClaudeRunResult, ProgressFn
from app.integrations.external_reviewer import (
    ExternalReviewer,
    ReviewerError,
    extract_json_object,
)
from app.schemas.qa_config import QaConfig
from app.schemas.runs import RunParams
from app.services.agents import AgentDeps, PlannedCase
from app.services.findings import IgnoreList
from app.services.qa_lead import _review_cases
from app.services.run_manager import RunContext
from app.services.run_store import RunStore

QA_DIR = Path(__file__).resolve().parents[2] / "qa"
KEY = "sk-secret-do-not-leak"


def _reviewer(handler: Any) -> ExternalReviewer:
    return ExternalReviewer(
        provider="gemini",
        model="gemini-test",
        api_key=SecretStr(KEY),
        base_url="https://example.test/v1/",
        timeout_s=5,
        transport=httpx.MockTransport(handler),
    )


def _reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_json_is_found_in_fences_and_reasoning_blocks() -> None:
    assert extract_json_object('```json\n{"cases": []}\n```') == {"cases": []}
    assert extract_json_object('<think>maybe {x}</think>Sure: {"cases": [1]}') == {"cases": [1]}
    for bad in ("no json here", "{not json}", "[1, 2]"):
        with pytest.raises(ReviewerError):
            extract_json_object(bad)


async def test_complete_posts_to_the_chat_endpoint_with_the_key_and_model() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return _reply('{"cases": []}')

    text = await _reviewer(handler).complete("be strict", "review these")
    assert text == '{"cases": []}'
    assert seen["url"] == "https://example.test/v1/chat/completions"
    assert seen["auth"] == f"Bearer {KEY}"
    assert seen["body"]["model"] == "gemini-test"
    assert [m["role"] for m in seen["body"]["messages"]] == ["system", "user"]


async def test_provider_errors_never_leak_the_key() -> None:
    def denied(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid api key")

    with pytest.raises(ReviewerError) as denied_error:
        await _reviewer(denied).complete("s", "u")
    assert "401" in str(denied_error.value) and KEY not in str(denied_error.value)

    def broken(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    with pytest.raises(ReviewerError, match="unexpected shape"):
        await _reviewer(broken).complete("s", "u")

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(ReviewerError, match="didn't answer"):
        await _reviewer(unreachable).complete("s", "u")


def test_a_half_configured_reviewer_fails_at_startup_not_mid_run() -> None:
    assert Settings(reviewer_provider="claude").reviewer_provider == "claude"
    with pytest.raises(ValidationError, match="REVIEWER_MODEL, REVIEWER_API_KEY"):
        Settings(reviewer_provider="gemini")
    with pytest.raises(ValidationError, match="REVIEWER_BASE_URL"):
        Settings(reviewer_provider="custom", reviewer_model="m", reviewer_api_key=SecretStr("k"))
    ok = Settings(
        reviewer_provider="perplexity", reviewer_model="sonar", reviewer_api_key=SecretStr("k")
    )
    reviewer = ExternalReviewer.from_settings(ok)
    assert reviewer is not None and reviewer.label == "Perplexity (sonar)"
    assert ExternalReviewer.from_settings(Settings()) is None


class _FakeClaude:
    def __init__(self, structured: dict[str, Any] | None) -> None:
        self.structured = structured
        self.calls = 0

    def ensure_no_billed_credentials(self) -> None:
        return None

    async def run(
        self, inv: AgentInvocation, on_progress: ProgressFn, timeout_s: float | None = None
    ) -> ClaudeRunResult:
        self.calls += 1
        return ClaudeRunResult(ok=self.structured is not None, structured=self.structured)


def _ctx(tmp_path: Path) -> RunContext:
    store = RunStore(tmp_path, 20)
    record = store.create("check-change", "Check my change", RunParams())
    return RunContext(store, record, IgnoreList(tmp_path / "ignored.json"))


def _deps(tmp_path: Path, claude: _FakeClaude, reviewer: ExternalReviewer | None) -> AgentDeps:
    settings = Settings(qa_dir=QA_DIR, runs_dir=tmp_path)
    return AgentDeps(
        settings=settings,
        qa=QaConfig(),
        claude=claude,  # type: ignore[arg-type]  # a fake `claude` binary
        probe=None,  # type: ignore[arg-type]  # not used by the reviewer
        reviewer=reviewer,
    )


DRAFTS = [PlannedCase(title="Book", steps=["1. Book"], expected="Booked")]
REVIEWED = {
    "cases": [
        {
            "title": "Book",
            "agent": "functionality-tester",
            "steps": ["1. Book a stay"],
            "expected": "A booking appears",
            "review_status": "rewritten",
            "review_note": "Made it concrete",
        }
    ]
}


async def test_the_external_reviewer_reviews_and_claude_is_not_called(tmp_path: Path) -> None:
    prompts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        prompts.append(json.loads(request.content)["messages"][1]["content"])
        return _reply("```json\n" + json.dumps(REVIEWED) + "\n```")

    claude = _FakeClaude(None)
    ctx = _ctx(tmp_path)
    cases = await _review_cases(ctx, _deps(tmp_path, claude, _reviewer(handler)), "mocked", DRAFTS)

    assert cases[0].review_status == "rewritten" and cases[0].expected == "A booking appears"
    assert ctx.record.reviewer == "Gemini (gemini-test)"
    assert claude.calls == 0
    assert '"title": "Book"' in prompts[0]  # it saw the draft cases


async def test_claude_reviews_instead_when_the_external_reviewer_fails(tmp_path: Path) -> None:
    def down(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    claude = _FakeClaude(REVIEWED)
    ctx = _ctx(tmp_path)
    cases = await _review_cases(ctx, _deps(tmp_path, claude, _reviewer(down)), "mocked", DRAFTS)

    assert cases[0].review_status == "rewritten" and claude.calls == 1
    assert ctx.record.reviewer == "Claude (instead of Gemini)"
    events = [e.message for e in ctx.store.read_events(ctx.record.id, 0)]
    assert any("Gemini answered HTTP 500" in m for m in events)


async def test_a_reply_with_the_wrong_number_of_cases_is_not_trusted(tmp_path: Path) -> None:
    def too_many(_: httpx.Request) -> httpx.Response:
        return _reply(json.dumps({"cases": REVIEWED["cases"] * 2}))

    claude = _FakeClaude(REVIEWED)
    ctx = _ctx(tmp_path)
    await _review_cases(ctx, _deps(tmp_path, claude, _reviewer(too_many)), "mocked", DRAFTS)
    assert claude.calls == 1 and ctx.record.reviewer == "Claude (instead of Gemini)"


async def test_default_reviewer_is_claude_and_an_unreviewable_draft_is_marked_unreviewed(
    tmp_path: Path,
) -> None:
    ctx = _ctx(tmp_path)
    cases = await _review_cases(ctx, _deps(tmp_path, _FakeClaude(REVIEWED), None), "mocked", DRAFTS)
    assert ctx.record.reviewer == "Claude" and cases[0].reviewed

    ctx2 = _ctx(tmp_path / "second")
    cases2 = await _review_cases(ctx2, _deps(tmp_path, _FakeClaude(None), None), "mocked", DRAFTS)
    assert ctx2.record.reviewer is None and cases2[0].reviewed is False
