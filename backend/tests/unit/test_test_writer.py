from datetime import UTC, datetime

from app.schemas.runs import AgentResult, RunRecord
from app.services.test_writer import ensure_can_save, passing_flow, passing_flow_result


def _run(*agents: AgentResult) -> RunRecord:
    return RunRecord(
        id="20260101-000000-check-change-abcdef",
        kind="check-change",
        title="Check my change",
        status="finished",
        started_at=datetime.now(UTC),
        agents=list(agents),
    )


def test_passing_flow_picks_the_first_passing_scenario_not_the_first_call() -> None:
    """A Check my change run can test several scenarios; saving must use the one that passed,
    including the evidence folder it actually wrote to — not always the first call's."""
    failing = AgentResult(
        agent="functionality-tester",
        task="Test case scenario 1 of 2:\n...",
        verdict="FAILING",
        work_dir="agent-output/functionality-tester-1",
    )
    passing = AgentResult(
        agent="functionality-tester",
        task="Test case scenario 2 of 2:\n...",
        verdict="PASS",
        work_dir="agent-output/functionality-tester-2",
    )
    run = _run(failing, passing)

    result = passing_flow_result(run)
    assert result is not None
    assert result.work_dir == "agent-output/functionality-tester-2"
    assert passing_flow(run) == passing.task
    assert ensure_can_save(run) is result


def test_passing_flow_is_none_without_a_passing_functionality_result() -> None:
    assert passing_flow(_run()) is None
    assert (
        passing_flow(_run(AgentResult(agent="functionality-tester", task="x", verdict="FAILING")))
        is None
    )
    assert passing_flow(_run(AgentResult(agent="code-reviewer", task="x", verdict="PASS"))) is None


def test_old_runs_without_a_work_dir_still_resolve_a_flow() -> None:
    """Runs made before per-scenario evidence folders existed have no `work_dir`; callers must
    fall back to the single fixed `agent-output/functionality-tester` path."""
    legacy = AgentResult(agent="functionality-tester", task="1. Open /", verdict="PASS")
    assert legacy.work_dir == ""
    assert passing_flow(_run(legacy)) == "1. Open /"
