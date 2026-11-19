"""Run a local command with a timeout. Used by every CLI integration (git, gh, claude, npx)."""

import asyncio
from dataclasses import dataclass
from pathlib import Path


class ProcessError(Exception):
    """The command couldn't run (not installed) or didn't finish in time."""


@dataclass(frozen=True)
class ProcessResult:
    code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.code == 0


async def run_process(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout_s: float = 60.0,
    stdin: str | None = None,
) -> ProcessResult:
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise ProcessError(f"`{argv[0]}` was not found on PATH") from exc
    try:
        out, err = await asyncio.wait_for(
            proc.communicate(stdin.encode() if stdin is not None else None), timeout_s
        )
    except TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise ProcessError(f"`{argv[0]}` didn't finish within {timeout_s:.0f}s") from exc
    except asyncio.CancelledError:
        proc.kill()
        await proc.wait()
        raise
    return ProcessResult(
        code=proc.returncode if proc.returncode is not None else -1,
        stdout=out.decode(errors="replace"),
        stderr=err.decode(errors="replace"),
    )
