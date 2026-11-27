"""The Mac's own "Choose folder" window, so the dashboard can fill in a project folder.

A web page can't learn a folder's full path, but this backend runs on the developer's Mac, so it
can open the native picker itself (`osascript`) and hand the chosen path back.
"""

import shutil
import sys
from pathlib import Path

from app.integrations.process import ProcessError, run_process

# The window waits for the developer; give them time, but don't hold a request forever.
_PICK_TIMEOUT_S = 300.0
_USER_CANCELED = "-128"  # AppleScript's error number for Cancel


class FolderPickerError(Exception):
    """The picker couldn't open or didn't return a folder in time."""


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


class FolderPicker:
    def available(self) -> bool:
        """True on a Mac with osascript: the only place a native picker can open."""
        return sys.platform == "darwin" and shutil.which("osascript") is not None

    async def pick(self, start: Path | None = None) -> Path | None:
        """Open the picker and return the chosen folder, or None when the developer cancels.

        Raises FolderPickerError when it can't open or times out.
        """
        choose = 'choose folder with prompt "Choose the project to test"'
        if start is not None:
            choose += f" default location (POSIX file {_quote(str(start))})"
        argv = [
            "osascript",
            # Bring the window to the front; a background server's dialog opens behind the browser.
            "-e",
            "tell me to activate",
            "-e",
            f"POSIX path of ({choose})",
        ]
        try:
            result = await run_process(argv, timeout_s=_PICK_TIMEOUT_S)
        except ProcessError as exc:
            raise FolderPickerError(str(exc)) from exc
        if not result.ok:
            if _USER_CANCELED in result.stderr:
                return None
            raise FolderPickerError(result.stderr.strip() or "The folder picker failed")
        path = result.stdout.strip()
        return Path(path.rstrip("/") or "/") if path else None
