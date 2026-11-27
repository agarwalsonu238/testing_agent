from pathlib import Path

from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import SecretStr

from app.api.deps import get_folder_picker
from app.core.config import Settings, get_settings
from app.integrations.folder_picker import FolderPicker, FolderPickerError


class FakePicker(FolderPicker):
    def __init__(self, result: Path | None = None, *, mac: bool = True, fail: bool = False):
        self.result, self.mac, self.fail = result, mac, fail
        self.started_at: Path | None = None

    def available(self) -> bool:
        return self.mac

    async def pick(self, start: Path | None = None) -> Path | None:
        self.started_at = start
        if self.fail:
            raise FolderPickerError("osascript blew up")
        return self.result


def _use(app: FastAPI, picker: FakePicker) -> None:
    app.dependency_overrides[get_folder_picker] = lambda: picker


async def test_pick_folder_returns_the_chosen_path(
    client: AsyncClient, app: FastAPI, tmp_path: Path
) -> None:
    _use(app, FakePicker(tmp_path))
    response = await client.post("/api/v1/pick-folder")
    assert response.status_code == 200
    assert response.json() == {"path": str(tmp_path)}


async def test_pick_folder_cancel_returns_no_path(client: AsyncClient, app: FastAPI) -> None:
    _use(app, FakePicker(None))
    assert (await client.post("/api/v1/pick-folder")).json() == {"path": None}


async def test_pick_folder_starts_in_the_default_repo_when_it_exists(
    client: AsyncClient, app: FastAPI, settings: Settings, tmp_path: Path
) -> None:
    picker = FakePicker(tmp_path)
    _use(app, picker)
    with_repo = settings.model_copy(update={"app_repo_path": tmp_path})
    app.dependency_overrides[get_settings] = lambda: with_repo
    await client.post("/api/v1/pick-folder")
    assert picker.started_at == tmp_path


async def test_pick_folder_is_409_off_a_mac(client: AsyncClient, app: FastAPI) -> None:
    _use(app, FakePicker(mac=False))
    assert (await client.post("/api/v1/pick-folder")).status_code == 409
    assert (await client.get("/api/v1/qa-config")).json()["can_pick_folder"] is False


async def test_pick_folder_is_409_on_a_deployed_backend(
    client: AsyncClient, app: FastAPI, settings: Settings
) -> None:
    _use(app, FakePicker())
    deployed = settings.model_copy(update={"api_auth_token": SecretStr("k")})
    app.dependency_overrides[get_settings] = lambda: deployed
    headers = {"X-API-Key": "k"}
    assert (await client.post("/api/v1/pick-folder", headers=headers)).status_code == 409
    config = (await client.get("/api/v1/qa-config", headers=headers)).json()
    assert config["can_pick_folder"] is False


async def test_pick_folder_failure_is_502(client: AsyncClient, app: FastAPI) -> None:
    _use(app, FakePicker(fail=True))
    response = await client.post("/api/v1/pick-folder")
    assert response.status_code == 502
    assert "Couldn't open the folder picker" in response.json()["detail"]


async def test_qa_config_offers_the_picker_on_a_local_mac(
    client: AsyncClient, app: FastAPI
) -> None:
    _use(app, FakePicker())
    assert (await client.get("/api/v1/qa-config")).json()["can_pick_folder"] is True
