"""Reachability check for the app under test (shared `httpx.AsyncClient` created in lifespan)."""

import httpx

PROBE_TIMEOUT = httpx.Timeout(5.0)


class HttpProbe:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def reachable(self, url: str) -> tuple[bool, str]:
        """GET `url`. Any HTTP answer below 500 counts as reachable."""
        try:
            response = await self._client.get(url, timeout=PROBE_TIMEOUT, follow_redirects=True)
        except httpx.HTTPError as exc:
            return False, f"{type(exc).__name__}: no answer from {url}"
        return response.status_code < 500, f"HTTP {response.status_code} from {url}"
