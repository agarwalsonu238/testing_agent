from pathlib import Path

import pytest

from app.integrations.process import ProcessError, run_process


async def test_run_process_missing_cwd_names_the_folder(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(ProcessError, match=r"Working folder .* doesn't exist"):
        await run_process(["true"], cwd=missing)


async def test_run_process_missing_binary_names_path(tmp_path: Path) -> None:
    with pytest.raises(ProcessError, match="not found on PATH"):
        await run_process(["definitely-not-a-real-binary-xyz"], cwd=tmp_path)
