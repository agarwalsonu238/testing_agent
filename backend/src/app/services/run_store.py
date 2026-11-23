"""One folder per run under RUNS_DIR: `run.json`, `events.jsonl` and the run's evidence files.

There is no database: the folder is the record. Only the newest `keep` runs are kept.
"""

import json
import re
import secrets
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path

from app.core.errors import NotFoundError
from app.schemas.runs import RunEvent, RunKind, RunParams, RunRecord

RUN_ID_PATTERN = re.compile(r"^\d{8}-\d{6}-[a-z-]+-[0-9a-f]{6}$")


def now() -> datetime:
    return datetime.now(UTC)


class RunStore:
    def __init__(self, root: Path, keep: int) -> None:
        self.root = root
        self.keep = keep
        self._lock = threading.Lock()
        self.root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        if not RUN_ID_PATTERN.match(run_id):
            raise NotFoundError("Run not found")
        return self.root / run_id

    def create(self, kind: RunKind, title: str, params: RunParams) -> RunRecord:
        started = now()
        run_id = f"{started:%Y%m%d-%H%M%S}-{kind}-{secrets.token_hex(3)}"
        (self.root / run_id).mkdir(parents=True)
        record = RunRecord(id=run_id, kind=kind, title=title, started_at=started, params=params)
        self.save(record)
        return record

    def save(self, record: RunRecord) -> None:
        path = self.run_dir(record.id) / "run.json"
        tmp = path.with_suffix(".json.tmp")
        with self._lock:
            tmp.write_text(record.model_dump_json(indent=2))
            tmp.replace(path)

    def load(self, run_id: str) -> RunRecord:
        path = self.run_dir(run_id) / "run.json"
        if not path.is_file():
            raise NotFoundError("Run not found")
        return RunRecord.model_validate_json(path.read_text())

    def all_runs(self) -> list[RunRecord]:
        records = []
        for folder in sorted(self.root.iterdir(), reverse=True):
            if folder.is_dir() and RUN_ID_PATTERN.match(folder.name):
                try:
                    records.append(self.load(folder.name))
                except (NotFoundError, ValueError):
                    continue  # half-written or foreign folder
        return records

    def append_event(self, run_id: str, event: RunEvent) -> None:
        with self._lock, (self.run_dir(run_id) / "events.jsonl").open("a") as fh:
            fh.write(event.model_dump_json() + "\n")

    def read_events(self, run_id: str, after: int) -> list[RunEvent]:
        path = self.run_dir(run_id) / "events.jsonl"
        if not path.is_file():
            if not (self.run_dir(run_id) / "run.json").is_file():
                raise NotFoundError("Run not found")
            return []
        events = []
        for line in path.read_text().splitlines():
            if line.strip():
                event = RunEvent.model_validate(json.loads(line))
                if event.seq > after:
                    events.append(event)
        return events

    def file_path(self, run_id: str, rel: str) -> Path:
        """Resolve a file inside a run folder; anything outside it is 'not found'."""
        base = self.run_dir(run_id).resolve()
        target = (base / rel).resolve()
        if not target.is_relative_to(base) or not target.is_file():
            raise NotFoundError("File not found")
        return target

    def prune(self) -> None:
        records = self.all_runs()
        for old in records[self.keep :]:
            if old.status != "running":
                shutil.rmtree(self.root / old.id, ignore_errors=True)

    def mark_interrupted(self) -> None:
        """Runs still 'running' at startup were cut off by a backend restart."""
        for record in self.all_runs():
            if record.status == "running":
                record.status = "finished"
                record.verdict = "BLOCKED"
                record.blocked_reason = "Interrupted: the QA agent backend restarted during the run"
                record.finished_at = now()
                record.awaiting_approval = False
                record.activity = None
                if record.stage is not None:
                    record.stage = "done"
                self.save(record)
