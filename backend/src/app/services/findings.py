"""To review: fingerprints, the ignore list, and run verdicts derived from findings."""

import hashlib
import json
import re
import threading
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

from app.schemas.runs import AgentResult, Finding, Verdict

_DIGITS = re.compile(r"\d+")
_SPACE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _SPACE.sub(" ", _DIGITS.sub("#", text.lower())).strip()


def fingerprint(finding: Finding) -> str:
    """Stable across runs: numbers (line numbers, ports, timings) are ignored."""
    key = f"{finding.agent}|{_normalize(finding.location)}|{_normalize(finding.title)}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class IgnoredEntry(BaseModel):
    fingerprint: str
    reason: str
    agent: str
    title: str
    location: str


class IgnoreList:
    """`RUNS_DIR/ignored.json`. An ignored finding is skipped in later runs."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def _read(self) -> dict[str, IgnoredEntry]:
        if not self._path.is_file():
            return {}
        raw = json.loads(self._path.read_text() or "[]")
        return {e["fingerprint"]: IgnoredEntry.model_validate(e) for e in raw}

    def get(self, fp: str) -> IgnoredEntry | None:
        return self._read().get(fp)

    def add(self, finding: Finding, reason: str) -> None:
        with self._lock:
            entries = self._read()
            entries[finding.fingerprint] = IgnoredEntry(
                fingerprint=finding.fingerprint,
                reason=reason,
                agent=finding.agent,
                title=finding.title,
                location=finding.location,
            )
            self._path.write_text(json.dumps([e.model_dump() for e in entries.values()], indent=2))

    def apply(self, findings: Iterable[Finding]) -> None:
        """Fingerprint findings and mark previously ignored ones as ignored (old reason kept)."""
        entries = self._read()
        for finding in findings:
            finding.fingerprint = finding.fingerprint or fingerprint(finding)
            entry = entries.get(finding.fingerprint)
            if entry is not None and finding.status == "open":
                finding.status = "ignored"
                finding.ignore_reason = f"Ignored before: {entry.reason}"


def counts_against(finding: Finding) -> bool:
    return finding.status != "ignored" and finding.severity in ("High", "Medium")


def verdict_from_findings(findings: Iterable[Finding]) -> Verdict:
    """FAILING when a High or Medium finding isn't ignored; Warnings alone don't fail a run."""
    return "FAILING" if any(counts_against(f) for f in findings) else "PASS"


def combine_verdicts(results: Iterable[AgentResult]) -> Verdict | None:
    verdicts = [r.verdict for r in results]
    if not verdicts:
        return None
    if "FAILING" in verdicts:
        return "FAILING"
    if "BLOCKED" in verdicts:
        return "BLOCKED"
    return "PASS"
