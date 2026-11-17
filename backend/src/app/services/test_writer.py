"""Save as test: a passing flow becomes a normal Playwright test with the next test ID.

Safety: the test is written in a separate git worktree on a new branch, so the developer's
uncommitted work is never touched. If the Test writer changes anything outside the test folder,
the branch is thrown away. Nothing pushes to main, force-pushes or merges.
"""

import asyncio
import contextlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import child_process_env
from app.core.errors import BlockedError, ConflictError, PreconditionError
from app.integrations import git
from app.integrations.process import ProcessError, run_process
from app.schemas.qa_config import TestsConfig
from app.schemas.runs import Evidence, Finding, RunRecord, SavedTestInfo, SaveTestRequest
from app.services.agents import (
    FUNCTIONALITY_TESTER,
    TEST_WRITER,
    TEST_WRITER_SCHEMA,
    AgentCall,
    AgentDeps,
    get_agent,
    invoke_agent,
)
from app.services.run_manager import RunContext

PLAYWRIGHT_TIMEOUT_S = 600


def next_test_id(existing: list[str], prefix: str, digits: int) -> str:
    """Next free ID after the highest existing one with the same prefix (QA-007 → QA-008)."""
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    numbers = [int(m.group(1)) for i in existing if (m := pattern.match(i))]
    return f"{prefix}{(max(numbers) + 1 if numbers else 1):0{digits}d}"


def slugify(text: str, limit: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit].strip("-") or "flow"


def read_registry(path: Path) -> tuple[list[dict[str, Any]], bool]:
    """Registry entries and whether the file wraps them as {"tests": [...]}."""
    if not path.is_file():
        return [], True
    data = json.loads(path.read_text() or "[]")
    if isinstance(data, dict):
        return list(data.get("tests", [])), True
    return list(data), False


def write_registry(path: Path, entries: list[dict[str, Any]], wrapped: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: Any = {"tests": entries} if wrapped else entries
    path.write_text(json.dumps(payload, indent=2) + "\n")


def passing_flow(source: RunRecord) -> str | None:
    """The flow text of a passing Functionality tester result, if the run has one."""
    if source.status != "finished":
        return None
    for result in source.agents:
        if result.agent == FUNCTIONALITY_TESTER and result.verdict == "PASS":
            return result.task
    return None


def ensure_can_save(source: RunRecord) -> str:
    flow = passing_flow(source)
    if flow is None:
        raise ConflictError(
            "Only a finished run with a passing Functionality tester flow can be saved"
        )
    return flow


async def run_playwright_test(
    deps: AgentDeps, root: Path, test_file: str, log_path: Path
) -> tuple[bool, str]:
    """Run one test file with the repo's own Playwright (no AI). Returns (passed, output tail)."""
    tests: TestsConfig = deps.qa.tests
    cwd = root / tests.playwright_cwd
    rel = Path(test_file)
    with contextlib.suppress(ValueError):
        rel = (root / test_file).resolve().relative_to(cwd.resolve())
    try:
        res = await run_process(
            [*tests.playwright_command, rel.as_posix()],
            cwd=cwd,
            env=child_process_env(deps.settings),
            timeout_s=PLAYWRIGHT_TIMEOUT_S,
        )
    except ProcessError as exc:
        return False, str(exc)
    output = (res.stdout + "\n" + res.stderr).strip()
    await asyncio.to_thread(log_path.write_text, output)
    return res.ok, "\n".join(output.splitlines()[-30:])


async def save_as_test(
    ctx: RunContext, deps: AgentDeps, source: RunRecord, request: SaveTestRequest
) -> None:
    s, tests = deps.settings, deps.qa.tests
    repo = s.app_repo_path
    if repo is None or not await git.is_repo(repo):
        raise PreconditionError("APP_REPO_PATH must point at the app's git repository")
    flow = ensure_can_save(source)
    source_dir = ctx.store.run_dir(source.id)
    code_path = source_dir / "agent-output" / FUNCTIONALITY_TESTER / "playwright-code.json"
    recorded = code_path.read_text() if code_path.is_file() else "[]"
    steps = next(r.steps for r in source.agents if r.agent == FUNCTIONALITY_TESTER)

    entries, wrapped = read_registry(repo / tests.registry_path)
    test_id = next_test_id(
        [str(e.get("id", "")) for e in entries], tests.id_prefix, tests.id_digits
    )
    title = (request.title or flow.splitlines()[0]).strip()[:120]
    folder = request.folder or tests.default_folder
    tests_dir = (tests.isolated_dir if folder == "isolated" else tests.live_dir).strip("/")
    test_file = f"{tests_dir}/{test_id.lower()}-{slugify(title)}.spec.ts"
    branch = f"{tests.branch_prefix}{test_id.lower()}-{slugify(title, 30)}"
    ctx.record.params.test_id = test_id
    ctx.record.saved_test = SavedTestInfo(test_id=test_id, file=test_file, branch=branch)
    ctx.save()

    worktree = ctx.dir / "worktree"
    ctx.event(f"Creating branch {branch} in a separate worktree", source=TEST_WRITER)
    await git.worktree_add(repo, worktree, branch)
    keep_branch = False
    try:
        run = await invoke_agent(
            ctx,
            deps,
            AgentCall(
                agent=get_agent(s, TEST_WRITER),
                task=(
                    f"Write the Playwright test {test_id} ('{title}') at `{test_file}` from this "
                    f"passing flow:\n{flow}"
                ),
                mode=source.params.mode,
                cwd=worktree,
                tests_dir=tests_dir,
                schema=TEST_WRITER_SCHEMA,
                context=[
                    "",
                    "## Recorded flow",
                    "Steps: " + json.dumps([st.model_dump() for st in steps]),
                    "Playwright code that ran for each action (in order):",
                    recorded,
                    "",
                    f"Write only inside `{tests_dir}/`. The backend adds the registry entry.",
                ],
            ),
        )
        if not run.result.ok:
            raise BlockedError(f"Test writer failed: {run.result.error}")

        changed = await git.status_paths(worktree)
        outside = [p for p in changed if not p.startswith(f"{tests_dir}/")]
        if outside:
            raise BlockedError(
                f"Test writer changed files outside {tests_dir}/: {', '.join(outside[:5])}"
            )
        if test_file not in changed:
            raise BlockedError(f"Test writer didn't create {test_file}")

        entries.append(
            {
                "id": test_id,
                "title": title,
                "file": test_file,
                "folder": folder,
                "created_at": datetime.now(UTC).date().isoformat(),
                "source_run_id": source.id,
            }
        )
        write_registry(worktree / tests.registry_path, entries, wrapped)

        passed, tail = await _verify(ctx, deps, repo, worktree, test_file)
        sha = await git.commit(
            worktree, [*changed, tests.registry_path], f"test: add {test_id} {title}"
        )
        keep_branch = True
        info = ctx.record.saved_test
        info.commit = sha
        ctx.event(f"Committed {sha[:8]} on {branch}", source=TEST_WRITER)
        if not passed:
            ctx.add_findings([_first_run_failed(test_id, test_file, tail)])
            ctx.event("Not pushed: the new test failed its first run", level="warn")
            return
        if s.test_writer_open_pr:
            await _push_and_open_pr(ctx, worktree, branch, tests.pr_base, test_id, title, source.id)
    finally:
        with contextlib.suppress(git.GitError):
            await git.worktree_remove(repo, worktree)
        if not keep_branch:
            with contextlib.suppress(git.GitError):
                await git.branch_delete(repo, branch)


async def _verify(
    ctx: RunContext, deps: AgentDeps, repo: Path, worktree: Path, test_file: str
) -> tuple[bool, str]:
    """Run the new test once in the worktree, borrowing the repo's node_modules."""
    cwd_rel = deps.qa.tests.playwright_cwd
    modules = repo / cwd_rel / "node_modules"
    link = worktree / cwd_rel / "node_modules"
    if modules.is_dir() and not link.exists():
        link.symlink_to(modules, target_is_directory=True)
    ctx.event(f"Running {test_file} once (plain Playwright, no AI)", source=TEST_WRITER)
    try:
        passed, tail = await run_playwright_test(
            deps, worktree, test_file, ctx.dir / "first-run.txt"
        )
    finally:
        if link.is_symlink():
            link.unlink()
    if (ctx.dir / "first-run.txt").is_file():
        ctx.add_artifact("First run output", ctx.dir / "first-run.txt", "log")
    ctx.event(f"First run {'passed' if passed else 'failed'}", level="info" if passed else "warn")
    return passed, tail


def _first_run_failed(test_id: str, test_file: str, tail: str) -> Finding:
    return Finding(
        id="",
        agent=TEST_WRITER,
        title=f"Saved test {test_id} fails on its first run",
        severity="High",
        category="automation issue",
        location=test_file,
        expected="The new test passes against the app it was recorded on",
        actual="Playwright reported a failure",
        evidence=[Evidence(kind="log", label="Playwright output", text=tail)],
    )


async def _push_and_open_pr(
    ctx: RunContext,
    worktree: Path,
    branch: str,
    base: str,
    test_id: str,
    title: str,
    source_id: str,
) -> None:
    info = ctx.record.saved_test
    assert info is not None  # noqa: S101 - set before the worktree is created
    try:
        await git.push_branch(worktree, branch)
        info.pushed = True
        ctx.save()
        ctx.event(f"Pushed {branch}", source=TEST_WRITER)
        info.pr_url = await git.gh_create_pr(
            worktree,
            base=base,
            head=branch,
            title=f"test: add {test_id} {title}",
            body=(
                f"Saved by the QA testing agent from run `{source_id}`.\n\n"
                f"- Test: `{info.file}`\n- Registry entry: `{test_id}`\n\n"
                "The test passed its first run locally. Review before merging; "
                "nothing merges automatically."
            ),
        )
        ctx.save()
        ctx.event(f"Opened {info.pr_url}", source=TEST_WRITER)
    except git.GitError as exc:
        ctx.event(f"Branch kept locally; push/PR failed: {exc}", level="warn", source=TEST_WRITER)
