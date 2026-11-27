import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.errors import PreconditionError
from app.services.qa_config import design_files, designs_dir, load_qa_config, merge_qa_config

QA_DIR = Path(__file__).resolve().parents[2] / "qa"


def _settings(tmp_path: Path, repo: Path | None) -> Settings:
    return Settings(qa_dir=QA_DIR, designs_dir=tmp_path / "tool-designs", app_repo_path=repo)


def _project(tmp_path: Path, config: object) -> Path:
    repo = tmp_path / "repo"
    (repo / ".qa").mkdir(parents=True)
    (repo / ".qa" / "qa.config.json").write_text(json.dumps(config))
    return repo


def test_merge_concatenates_safety_lists_overlays_objects_and_replaces_the_rest() -> None:
    base = {
        "noise_filter": ["a"],
        "risky_endpoints": [{"url": "*/pay*"}],
        "limits": {"slow_api_ms": 2000, "max_pages": 15},
        "pages": [{"path": "/", "name": "Home"}],
    }
    project = {
        "noise_filter": ["b"],
        "risky_endpoints": [{"url": "*/bank*"}],
        "limits": {"max_pages": 5},
        "pages": [{"path": "/pricing", "name": "Pricing"}],
    }
    merged = merge_qa_config(base, project)
    assert merged["noise_filter"] == ["a", "b"]
    assert merged["risky_endpoints"] == [{"url": "*/pay*"}, {"url": "*/bank*"}]
    assert merged["limits"] == {"slow_api_ms": 2000, "max_pages": 5}
    assert merged["pages"] == [{"path": "/pricing", "name": "Pricing"}]
    assert base["noise_filter"] == ["a"]  # inputs are not mutated


def test_tool_defaults_are_generic_and_discover_pages(tmp_path: Path) -> None:
    qa = load_qa_config(_settings(tmp_path, repo=None))
    assert qa.pages == []
    assert qa.limits.max_pages == 15
    assert qa.tests.pr_base == "main"
    assert any(r.url == "*/api/*" and r.method == "DELETE" for r in qa.risky_endpoints)


def test_project_config_is_layered_over_the_defaults(tmp_path: Path) -> None:
    repo = _project(
        tmp_path,
        {
            "pages": [{"path": "/pricing", "name": "Pricing"}],
            "risky_endpoints": [{"url": "*/api/billing/*", "method": "POST"}],
            "tests": {"pr_base": "dev"},
        },
    )
    qa = load_qa_config(_settings(tmp_path, repo))
    assert [p.path for p in qa.pages] == ["/pricing"]
    urls = [r.url for r in qa.risky_endpoints]
    assert "*/api/billing/*" in urls and "*/api/*payment*" in urls  # tool rule kept
    assert qa.tests.pr_base == "dev"
    assert qa.tests.isolated_dir == "tests/e2e/isolated"  # untouched field keeps its default


def test_a_repo_without_a_qa_folder_gets_the_defaults(tmp_path: Path) -> None:
    repo = tmp_path / "plain-repo"
    repo.mkdir()
    assert load_qa_config(_settings(tmp_path, repo)).pages == []


@pytest.mark.parametrize("content", ["{not json", "[]", '{"pages": [{"path": "no-slash"}]}'])
def test_an_invalid_project_config_names_the_project_file(tmp_path: Path, content: str) -> None:
    repo = tmp_path / "repo"
    (repo / ".qa").mkdir(parents=True)
    (repo / ".qa" / "qa.config.json").write_text(content)
    with pytest.raises(PreconditionError, match=r"\.qa/qa\.config\.json"):
        load_qa_config(_settings(tmp_path, repo))


def test_designs_come_from_the_project_when_it_has_them(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    settings = _settings(tmp_path, repo)
    assert designs_dir(settings) == tmp_path / "tool-designs"

    (repo / ".qa" / "designs").mkdir(parents=True)
    (repo / ".qa" / "designs" / "pricing.desktop.png").write_bytes(b"png")
    assert designs_dir(settings) == repo / ".qa" / "designs"
    assert set(design_files(settings, "/pricing")) == {"desktop"}
