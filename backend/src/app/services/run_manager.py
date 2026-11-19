"""Runs one job at a time as an in-process asyncio task (a local single-developer tool: no queue).

The run folder is the job's visibility: events stream to `events.jsonl`, and a run that can't
finish ends as BLOCKED with a reason. Runs cut off by a restart are marked BLOCKED at startup.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal

from app.core.errors import BlockedError, ConflictError, NotFoundError, PreconditionError
from app.schemas.runs import (
    AgentResult,
    Artifact,
    EvidenceKind,
    Finding,
    RunEvent,
    RunKind,
    RunParams,
    RunRecord,
)
from app.services.findings import (
    IgnoreList,
    combine_verdicts,
    fingerprint,
    verdict_from_findings,
)
from app.services.run_store import RunStore, now

logger = logging.getLogger(__name__)

Level = Literal["info", "warn", "error"]


class RunContext:
    """What a job uses to report progress and results. Writes go straight to the run folder."""

    def __init__(self, store: RunStore, record: RunRecord, ignore: IgnoreList) -> None:
        self.store = store
        self.record = record
        self.ignore = ignore
        self.dir: Path = store.run_dir(record.id).resolve()
        self._seq = len(store.read_events(record.id, 0))

    def event(self, message: str, level: Level = "info", source: str = "run") -> None:
        self._seq += 1
        self.store.append_event(
            self.record.id,
            RunEvent(seq=self._seq, at=now(), level=level, source=source, message=message),
        )

    def add_findings(self, findings: list[Finding]) -> None:
        start = len(self.record.findings)
        for offset, finding in enumerate(findings, start=1):
            finding.id = f"f{start + offset}"
        self.ignore.apply(findings)
        self.record.findings.extend(findings)
        self.save()

    def add_agent_result(self, result: AgentResult) -> None:
        self.record.agents.append(result)
        self.save()

    def add_artifact(self, label: str, path: Path, kind: EvidenceKind) -> None:
        self.record.artifacts.append(Artifact(label=label, path=self.rel(path), kind=kind))
        self.save()

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.dir).as_posix()

    def save(self) -> None:
        self.store.save(self.record)

    def finish(self, blocked_reason: str | None = None) -> None:
        record = self.record
        if blocked_reason:
            record.verdict = "BLOCKED"
            record.blocked_reason = blocked_reason
            self.event(f"BLOCKED: {blocked_reason}", level="error")
        elif record.verdict is None:
            if record.agents:
                combined = combine_verdicts(record.agents) or "PASS"
                # Findings outside agent results (e.g. a saved test) still count.
                if combined == "PASS" and verdict_from_findings(record.findings) == "FAILING":
                    combined = "FAILING"
                record.verdict = combined
            else:
                record.verdict = verdict_from_findings(record.findings)
        record.status = "finished"
        record.finished_at = now()
        self.save()
        self.event(f"Finished: {record.verdict}")


Job = Callable[[RunContext], Awaitable[None]]


class RunManager:
    def __init__(self, store: RunStore, ignore: IgnoreList) -> None:
        self.store = store
        self.ignore = ignore
        self._task: asyncio.Task[None] | None = None
        self._run_id: str | None = None

    @property
    def active_run_id(self) -> str | None:
        return self._run_id if self._task and not self._task.done() else None

    async def start(self, kind: RunKind, title: str, params: RunParams, job: Job) -> RunRecord:
        """Create the run folder and start `job` in the background.

        Raises ConflictError when another run is still active.
        """
        if self.active_run_id:
            raise ConflictError(
                f"Another run is in progress ({self.active_run_id}). Wait or cancel it."
            )
        record = await asyncio.to_thread(self.store.create, kind, title, params)
        ctx = RunContext(self.store, record, self.ignore)
        ctx.event(f"Started {title}")
        self._run_id = record.id
        self._task = asyncio.create_task(self._execute(ctx, job), name=f"run-{record.id}")
        return record

    async def _execute(self, ctx: RunContext, job: Job) -> None:
        reason: str | None = None
        try:
            await job(ctx)
        except asyncio.CancelledError:
            self._finalize(ctx, "Cancelled by the developer")
            raise
        except (BlockedError, PreconditionError) as exc:
            reason = str(exc)
        except Exception:
            logger.exception("Run %s failed unexpectedly", ctx.record.id)
            reason = "Unexpected error in the QA agent backend (see the backend log)"
        self._finalize(ctx, reason)

    def _finalize(self, ctx: RunContext, reason: str | None) -> None:
        try:
            ctx.finish(reason)
            self.store.prune()
        except Exception:
            logger.exception("Could not finalize run %s", ctx.record.id)

    async def cancel(self, run_id: str) -> None:
        record = await self.get(run_id)
        if record.status != "running" or self.active_run_id != run_id or self._task is None:
            raise ConflictError("This run isn't running")
        self._task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(self._task), 15)
        except (TimeoutError, asyncio.CancelledError):
            logger.warning("Run %s is slow to stop after cancel", run_id)

    async def wait(self) -> None:
        """Wait for the active run (tests and shutdown)."""
        if self._task is not None:
            await asyncio.gather(self._task, return_exceptions=True)

    async def shutdown(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            await self.wait()

    async def get(self, run_id: str) -> RunRecord:
        return await asyncio.to_thread(self.store.load, run_id)

    async def all_runs(self) -> list[RunRecord]:
        return await asyncio.to_thread(self.store.all_runs)

    async def events(self, run_id: str, after: int) -> list[RunEvent]:
        return await asyncio.to_thread(self.store.read_events, run_id, after)

    async def file(self, run_id: str, rel: str) -> Path:
        return await asyncio.to_thread(self.store.file_path, run_id, rel)

    async def decide(
        self, run_id: str, finding_id: str, accept: bool, reason: str | None
    ) -> Finding:
        """Accept (a bug to fix) or ignore (with a reason, remembered for later runs) a finding."""
        record = await self.get(run_id)
        if record.status == "running":
            raise ConflictError("Wait until the run finishes before deciding on its findings")
        finding = next((f for f in record.findings if f.id == finding_id), None)
        if finding is None:
            raise NotFoundError("Finding not found")
        finding.fingerprint = finding.fingerprint or fingerprint(finding)
        if accept:
            finding.status, finding.ignore_reason = "accepted", None
        else:
            finding.status, finding.ignore_reason = "ignored", reason
            await asyncio.to_thread(self.ignore.add, finding, reason or "")
        await asyncio.to_thread(self.store.save, record)
        return finding
