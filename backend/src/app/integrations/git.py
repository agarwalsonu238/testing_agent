"""git and GitHub CLI (`gh`) calls against the app repo. Read-only except the
Save-as-test worktree."""

import re
from pathlib import Path

from app.integrations.process import ProcessError, ProcessResult, run_process


class GitError(Exception):
    pass


async def git(
    repo: Path, *args: str, timeout_s: float = 60, env: dict[str, str] | None = None
) -> str:
    try:
        res = await run_process(["git", "-C", str(repo), *args], timeout_s=timeout_s, env=env)
    except ProcessError as exc:
        raise GitError(str(exc)) from exc
    if not res.ok:
        detail = (res.stderr or res.stdout).strip().splitlines()
        raise GitError(f"git {args[0]} failed: {detail[-1] if detail else res.code}")
    return res.stdout


async def is_repo(path: Path) -> bool:
    try:
        return (await git(path, "rev-parse", "--is-inside-work-tree")).strip() == "true"
    except GitError:
        return False


async def merge_base(repo: Path, base_ref: str) -> str | None:
    """Merge-base of `base_ref` and HEAD, or None when the ref doesn't exist."""
    try:
        return (await git(repo, "merge-base", base_ref, "HEAD")).strip() or None
    except GitError:
        return None


async def changed_files(repo: Path, since: str) -> list[str]:
    """Files changed since `since` (committed + staged + unstaged) plus untracked files."""
    tracked = (await git(repo, "diff", "--name-only", since)).splitlines()
    untracked = (await git(repo, "ls-files", "--others", "--exclude-standard")).splitlines()
    return sorted({p for p in tracked + untracked if p.strip()})


async def diff(repo: Path, since: str) -> str:
    return await git(repo, "diff", "--no-color", "--stat", "--patch", since, timeout_s=60)


async def head_sha(repo: Path) -> str:
    return (await git(repo, "rev-parse", "HEAD")).strip()


async def worktree_add(repo: Path, path: Path, branch: str, start: str = "HEAD") -> None:
    await git(repo, "worktree", "add", "-b", branch, str(path), start, timeout_s=120)


async def worktree_remove(repo: Path, path: Path) -> None:
    await git(repo, "worktree", "remove", "--force", str(path))


async def status_paths(cwd: Path) -> list[str]:
    """Paths with changes in a work tree (untracked included)."""
    out = await git(cwd, "status", "--porcelain", "--untracked-files=all")
    return [line[3:].strip().strip('"') for line in out.splitlines() if line.strip()]


async def branch_delete(repo: Path, branch: str) -> None:
    await git(repo, "branch", "-D", branch)


async def commit(cwd: Path, paths: list[str], message: str) -> str:
    await git(cwd, "add", "--", *paths)
    await git(cwd, "commit", "-m", message, timeout_s=120)
    return await head_sha(cwd)


async def push_branch(cwd: Path, branch: str, remote: str = "origin") -> None:
    if branch in ("main", "master"):
        raise GitError("Refusing to push to main")
    await git(cwd, "push", "-u", remote, branch, timeout_s=180)


async def gh_create_pr(cwd: Path, *, base: str, head: str, title: str, body: str) -> str:
    """Open a PR with the GitHub CLI and return its URL. Never merges."""
    try:
        res: ProcessResult = await run_process(
            [
                "gh",
                "pr",
                "create",
                "--base",
                base,
                "--head",
                head,
                "--title",
                title,
                "--body",
                body,
            ],
            cwd=cwd,
            timeout_s=120,
        )
    except ProcessError as exc:
        raise GitError(str(exc)) from exc
    if not res.ok:
        detail = (res.stderr or res.stdout).strip().splitlines()
        raise GitError(f"gh pr create failed: {detail[-1] if detail else res.code}")
    match = re.search(r"https://\S+", res.stdout)
    return match.group(0) if match else res.stdout.strip()
