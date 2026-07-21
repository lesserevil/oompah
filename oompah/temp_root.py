"""Private temporary-directory management for the Oompah service.

The system ``/tmp`` is commonly a quota-limited tmpfs. Oompah launches
long-lived agents and build tools, so it uses an operator-owned directory.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


class TempRootError(RuntimeError):
    """Raised when Oompah cannot safely use its configured temp root."""


def default_temp_root() -> str:
    """Return Oompah's private, user-scoped temporary directory."""
    return str(Path.home() / ".oompah" / "tmp")


def default_workspace_root() -> str:
    """Return the default location for disposable agent workspaces."""
    return str(Path.home() / ".oompah" / "workspaces")


def resolve_temp_root(value: str | None = None) -> Path:
    """Resolve a configured temp root, rejecting relative paths."""
    raw = value or default_temp_root()
    expanded = Path(raw).expanduser()
    if not expanded.is_absolute():
        raise TempRootError("OOMPAH_TEMP_ROOT must be an absolute path or start with '~'")
    return expanded.resolve()


def configure_temp_root(value: str | None = None) -> str:
    """Create, validate, and export Oompah's process-wide temp root."""
    root = resolve_temp_root(value)
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        root.chmod(0o700)
        with tempfile.NamedTemporaryFile(dir=root):
            pass
    except OSError as exc:
        raise TempRootError(f"Cannot create or write OOMPAH_TEMP_ROOT {root}: {exc}") from exc

    root_text = str(root)
    os.environ.update({"TMPDIR": root_text, "TMP": root_text, "TEMP": root_text})
    tempfile.tempdir = root_text
    return root_text
