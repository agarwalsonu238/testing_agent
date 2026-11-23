"""An optional second opinion on the test cases from a different AI provider.

The test case reviewer reads only the draft cases, so it needs no browser, repo or tools: it is
plain text in, JSON out. That makes it a good place for a model that is not Claude (Gemini,
Perplexity, OpenAI, or anything that speaks the OpenAI chat-completions API).

Opt-in via REVIEWER_PROVIDER. What is sent: the agent's review instructions and the draft test
cases (title, agent, steps, expected), never the diff or the flow text. A code-review case can
quote a changed line, so those lines do reach the provider you choose. The API key is read from
settings and is never logged or returned.
"""

import json
import re
from dataclasses import dataclass

import httpx
from pydantic import SecretStr

from app.core.config import Settings


class ReviewerError(Exception):
    """The external reviewer gave no usable answer (the caller falls back to Claude)."""


@dataclass(frozen=True)
class Preset:
    label: str
    base_url: str | None


PRESETS: dict[str, Preset] = {
    "gemini": Preset("Gemini", "https://generativelanguage.googleapis.com/v1beta/openai"),
    "perplexity": Preset("Perplexity", "https://api.perplexity.ai"),
    "openai": Preset("OpenAI", "https://api.openai.com/v1"),
    "custom": Preset("Custom", None),
}

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def extract_json_object(text: str) -> dict[str, object]:
    """The JSON object in a model reply, tolerating code fences and reasoning blocks."""
    cleaned = _FENCE.sub("", _THINK.sub("", text).strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ReviewerError("the reply had no JSON object")
    try:
        value = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ReviewerError("the reply wasn't valid JSON") from exc
    if not isinstance(value, dict):
        raise ReviewerError("the reply wasn't a JSON object")
    return value


class ExternalReviewer:
    def __init__(
        self,
        *,
        provider: str,
        model: str,
        api_key: SecretStr,
        base_url: str,
        timeout_s: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self._key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_s
        self._transport = transport

    @classmethod
    def from_settings(cls, settings: Settings) -> "ExternalReviewer | None":
        """None when the reviewer is Claude (the default). Settings already validated the rest."""
        if settings.reviewer_provider == "claude":
            return None
        preset = PRESETS[settings.reviewer_provider]
        base_url = settings.reviewer_base_url or preset.base_url
        if not (base_url and settings.reviewer_model and settings.reviewer_api_key):
            raise ValueError("REVIEWER_* settings are incomplete")  # Settings validates this
        return cls(
            provider=settings.reviewer_provider,
            model=settings.reviewer_model,
            api_key=settings.reviewer_api_key,
            base_url=base_url,
            timeout_s=settings.reviewer_timeout_s,
        )

    @property
    def name(self) -> str:
        return PRESETS[self.provider].label

    @property
    def label(self) -> str:
        return f"{self.name} ({self.model})"

    async def complete(self, system: str, user: str) -> str:
        """One chat-completion call; returns the model's text. Raises ReviewerError."""
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._key.get_secret_value()}"},
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    },
                )
        except httpx.HTTPError as exc:
            raise ReviewerError(f"{self.name} didn't answer ({type(exc).__name__})") from exc
        if response.status_code >= 400:
            raise ReviewerError(
                f"{self.name} answered HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ReviewerError(f"{self.name} sent a reply in an unexpected shape") from exc
        if not isinstance(content, str) or not content.strip():
            raise ReviewerError(f"{self.name} sent an empty reply")
        return content
