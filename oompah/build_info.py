"""Build identity shared by the standalone CLI and the HTTP server.

The service is commonly run from a checkout while the operator-facing task
CLI is installed into a UV tool environment.  A source checkout has Git
metadata available, but an installed wheel does not.  PEP 610 preserves the
VCS commit in ``direct_url.json`` for installs made directly from Git, so use
that metadata as the installed-package fallback.
"""

from __future__ import annotations

import importlib.metadata
import json
import re
import subprocess
from pathlib import Path
from typing import Any


PACKAGE_NAME = "oompah"
PACKAGE_VERSION = "0.1.0"
_REVISION_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")


def _package_version() -> str:
    try:
        return importlib.metadata.version(PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        return PACKAGE_VERSION


def _git_revision(start: Path) -> str | None:
    """Return the checkout revision containing *start*, if any."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(start),
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    revision = result.stdout.strip()
    return revision if result.returncode == 0 and _REVISION_RE.fullmatch(revision) else None


def _direct_url_revision() -> str | None:
    """Return the VCS commit recorded for a direct Git installation."""
    try:
        direct_url = importlib.metadata.distribution(PACKAGE_NAME).read_text(
            "direct_url.json"
        )
    except (importlib.metadata.PackageNotFoundError, OSError):
        return None
    if not direct_url:
        return None
    try:
        data: Any = json.loads(direct_url)
    except (TypeError, ValueError):
        return None
    revision = data.get("vcs_info", {}).get("commit_id")
    return revision if isinstance(revision, str) and _REVISION_RE.fullmatch(revision) else None


def source_revision() -> str:
    """Return the best available full source revision, or ``unknown``.

    Prefer checkout metadata so an editable source install follows the
    currently running checkout rather than a stale install record.  The
    package metadata fallback is what makes a standalone Git installation
    report the exact revision after its source checkout has been removed.
    """
    package_dir = Path(__file__).resolve().parent
    revision = _git_revision(package_dir)
    if revision:
        return revision
    return _direct_url_revision() or "unknown"


def build_identity() -> dict[str, str]:
    """Return the machine-readable identity exposed by CLI and server."""
    return {
        "name": PACKAGE_NAME,
        "version": _package_version(),
        "revision": source_revision(),
    }


def version_text() -> str:
    """Return the human-readable output for ``oompah --version``."""
    identity = build_identity()
    return f"{identity['name']} {identity['version']} (revision {identity['revision']})"
