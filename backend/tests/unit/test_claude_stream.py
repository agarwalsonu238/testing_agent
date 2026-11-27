from pathlib import Path

import pytest

from app.core.config import Settings, child_process_env
from app.integrations.claude_code import (
    AgentInvocation,
    ClaudeCode,
    StreamParser,
    extract_json_object,
    scrub_images,
)


def test_extract_json_from_fence_bare_and_prose() -> None:
    assert extract_json_object('{"a": 1}') == {"a": 1}
    assert extract_json_object('Done.\n```json\n{"a": 2}\n```') == {"a": 2}
    assert extract_json_object('Here: {"a": {"b": 3}} thanks') == {"a": {"b": 3}}
    assert extract_json_object("no json here") is None


def _events() -> list[dict[str, object]]:
    return [
        {
            "type": "system",
            "subtype": "init",
            "apiKeySource": "none",
            "claude_code_version": "2.1.328",
        },
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Opening the page"},
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "mcp__playwright__browser_wait_for",
                        "input": {"text": "Yearly"},
                    },
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "is_error": True,
                        "content": [{"type": "text", "text": "Timed out waiting for text"}],
                    }
                ]
            },
        },
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": '```json\n{"summary": "ok", "findings": []}\n```',
            "num_turns": 3,
            "permission_denials": [{"tool_name": "Write"}],
        },
    ]


def test_stream_parser_collects_calls_result_and_progress() -> None:
    parser = StreamParser()
    progress = [msg for event in _events() for msg in parser.feed(event)]
    result = parser.finish()

    assert result.ok
    assert result.api_key_source == "none"
    assert result.structured == {"summary": "ok", "findings": []}
    assert result.permission_denials == 1
    assert result.tool_calls[0].is_error is True
    assert ("warn", "✗ browser_wait_for failed: Timed out waiting for text") in progress


def test_stream_without_result_is_an_error() -> None:
    parser = StreamParser()
    parser.feed(_events()[0])
    assert parser.finish().ok is False


def test_scrub_images_drops_base64() -> None:
    event = {
        "content": [{"type": "image", "source": {"data": "AAAA"}}, {"type": "text", "text": "x"}]
    }
    assert scrub_images(event) == {
        "content": [{"type": "image", "omitted": True}, {"type": "text", "text": "x"}]
    }


def test_argv_never_bare_and_prompt_not_in_argv(tmp_path: Path) -> None:
    argv = ClaudeCode(Settings()).build_argv(
        AgentInvocation(
            prompt="SECRET PROMPT",
            cwd=tmp_path,
            agents_json="{}",
            agent="code-reviewer",
            allowed_tools=["Read"],
            disallowed_tools=["Write"],
            add_dirs=[tmp_path],
            mcp_config=tmp_path / "mcp.json",
            json_schema={"type": "object"},
            raw_log=tmp_path / "raw.jsonl",
        )
    )
    assert "--bare" not in argv
    assert "SECRET PROMPT" not in argv
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
    assert argv[argv.index("--agent") + 1] == "code-reviewer"


def test_child_env_strips_billing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "tok")
    env = child_process_env(Settings(claude_code_oauth_token=None))
    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env


def test_child_env_makes_agents_wait_for_mcp_servers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_CONNECTION_NONBLOCKING", "true")
    env = child_process_env(Settings(claude_code_oauth_token=None))
    assert env["MCP_CONNECTION_NONBLOCKING"] == "false"


def test_settings_report_billed_credentials_without_values() -> None:
    settings = Settings(anthropic_api_key="sk-live-123", anthropic_auth_token=None)
    assert settings.billed_credentials_set() == ["ANTHROPIC_API_KEY"]
