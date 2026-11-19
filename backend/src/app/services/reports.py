"""Report views of a run: list summary, detail, and the Markdown summary for a PR description."""

from app.schemas.runs import RunCounts, RunDetail, RunRecord, RunSummary
from app.services.test_writer import passing_flow

KIND_LABELS = {
    "quick-scan": "Quick Scan",
    "check-change": "Check my change",
    "agent": "Agent run",
    "save-test": "Save as test",
    "saved-test": "Saved test",
}


def counts(record: RunRecord) -> RunCounts:
    return RunCounts(
        open=sum(1 for f in record.findings if f.status == "open"), total=len(record.findings)
    )


def to_summary(record: RunRecord) -> RunSummary:
    return RunSummary(
        id=record.id,
        kind=record.kind,
        title=record.title,
        status=record.status,
        verdict=record.verdict,
        started_at=record.started_at,
        finished_at=record.finished_at,
        mode=record.params.mode,
        counts=counts(record),
    )


def report_markdown(record: RunRecord) -> str:
    """Verdict and open findings, ready to paste into a PR description."""
    verdict = record.verdict or "RUNNING"
    lines = [
        f"**QA agent: {verdict}** · {KIND_LABELS[record.kind]} · "
        f"{record.started_at:%Y-%m-%d %H:%M} UTC · {record.params.mode} mode",
    ]
    if record.blocked_reason:
        lines.append(f"\nBlocked: {record.blocked_reason}")
    if record.agents:
        lines += ["", "| Agent | Verdict | Summary |", "|---|---|---|"]
        for result in record.agents:
            summary = (result.blocked_reason or result.summary or "").replace("\n", " ")[:160]
            lines.append(f"| {result.agent} | {result.verdict} | {summary} |")
    open_findings = [f for f in record.findings if f.status != "ignored"]
    if open_findings:
        lines += ["", f"Open findings ({len(open_findings)}):"]
        for f in open_findings[:20]:
            accepted = " (accepted)" if f.status == "accepted" else ""
            lines.append(f"- [{f.severity} · {f.category}] {f.title} — {f.location}{accepted}")
        if len(open_findings) > 20:
            lines.append(f"- … {len(open_findings) - 20} more")
    else:
        lines += ["", "No open findings."]
    ignored = len(record.findings) - len(open_findings)
    if ignored:
        lines.append(f"\nIgnored with a reason: {ignored}")
    return "\n".join(lines)


def to_detail(record: RunRecord) -> RunDetail:
    return RunDetail(
        **record.model_dump(),
        counts=counts(record),
        report_summary=report_markdown(record),
        can_save_as_test=passing_flow(record) is not None and record.kind != "save-test",
    )
