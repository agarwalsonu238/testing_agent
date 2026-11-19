"""Saved tests: list them from the app repo's registry and re-run one with plain Playwright."""

from app.core.config import Settings
from app.core.errors import NotFoundError, PreconditionError
from app.schemas.qa_config import QaConfig
from app.schemas.runs import Evidence, Finding
from app.schemas.setup import SavedTest
from app.services.agents import AgentDeps
from app.services.run_manager import RunContext
from app.services.test_writer import read_registry, run_playwright_test


def list_saved_tests(settings: Settings, qa: QaConfig) -> list[SavedTest]:
    if settings.app_repo_path is None:
        raise PreconditionError("Set APP_REPO_PATH in .env to see the app's saved tests")
    entries, _ = read_registry(settings.app_repo_path / qa.tests.registry_path)
    tests = []
    for entry in entries:
        if entry.get("id") and entry.get("file"):
            tests.append(
                SavedTest(
                    id=str(entry["id"]),
                    title=str(entry.get("title", "")),
                    file=str(entry["file"]),
                    folder=entry.get("folder"),
                    created_at=entry.get("created_at"),
                    source_run_id=entry.get("source_run_id"),
                )
            )
    return tests


def find_saved_test(settings: Settings, qa: QaConfig, test_id: str) -> SavedTest:
    for test in list_saved_tests(settings, qa):
        if test.id == test_id:
            return test
    raise NotFoundError(f"No saved test {test_id} in the registry")


async def run_saved_test(ctx: RunContext, deps: AgentDeps, test: SavedTest) -> None:
    repo = deps.settings.app_repo_path
    assert repo is not None  # noqa: S101 - checked by find_saved_test
    ctx.event(f"Running {test.id}: {test.file}", source="saved-test")
    log = ctx.dir / "playwright-output.txt"
    passed, tail = await run_playwright_test(deps, repo, test.file, log)
    if log.is_file():
        ctx.add_artifact("Playwright output", log, "log")
    if passed:
        ctx.event(f"{test.id} passed", source="saved-test")
        return
    ctx.add_findings(
        [
            Finding(
                id="",
                agent="saved-test",
                title=f"Saved test {test.id} failed: {test.title}",
                severity="High",
                category="regression",
                location=test.file,
                expected="The saved flow passes",
                actual="Playwright reported a failure",
                evidence=[Evidence(kind="log", label="Playwright output", text=tail)],
            )
        ]
    )
