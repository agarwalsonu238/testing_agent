from httpx import AsyncClient
from pydantic import SecretStr

from app.core.config import Settings


async def test_no_auth_is_required_by_default(client: AsyncClient) -> None:
    """The local-only default: 127.0.0.1 binding is the boundary, not a key."""
    assert (await client.get("/api/v1/health")).status_code == 200


async def test_a_configured_key_is_required_and_checked(
    client: AsyncClient, settings: Settings
) -> None:
    settings.api_auth_token = SecretStr("secret-key")

    missing = await client.get("/api/v1/health")
    assert missing.status_code == 401

    wrong = await client.get("/api/v1/health", headers={"X-API-Key": "nope"})
    assert wrong.status_code == 401

    right = await client.get("/api/v1/health", headers={"X-API-Key": "secret-key"})
    assert right.status_code == 200


async def test_the_key_also_works_as_a_query_param_for_img_tags(
    client: AsyncClient, settings: Settings
) -> None:
    settings.api_auth_token = SecretStr("secret-key")

    assert (await client.get("/api/v1/health?key=secret-key")).status_code == 200
    assert (await client.get("/api/v1/health?key=wrong")).status_code == 401
