"""Workspace manager for oompah: per-issue isolated workspaces."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess

from oompah.models import Workspace

logger = logging.getLogger(__name__)

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")


class WorkspaceError(Exception):
    """Raised when workspace operations fail."""


def sanitize_identifier(identifier: str) -> str:
    """Replace any character not in [A-Za-z0-9._-] with underscore."""
    return _SAFE_CHARS.sub("_", identifier)


class WorkspaceManager:
    """Manages per-issue workspace directories with lifecycle hooks."""

    def __init__(
        self,
        workspace_root: str,
        hooks: dict[str, str | None],
        hooks_timeout_ms: int = 60000,
    ):
        self.root = os.path.abspath(os.path.expanduser(workspace_root))
        self.hooks = hooks
        self.hooks_timeout_ms = hooks_timeout_ms

    def workspace_path_for(self, identifier: str) -> str:
        """Compute the workspace path for an issue identifier."""
        key = sanitize_identifier(identifier)
        return os.path.join(self.root, key)

    def create_for_issue(self, identifier: str) -> Workspace:
        """Create or reuse a workspace for an issue.

        Returns a Workspace with created_now=True if newly created.
        Raises WorkspaceError on failure.
        """
        key = sanitize_identifier(identifier)
        path = os.path.join(self.root, key)

        # Safety: path must be under root
        abs_path = os.path.abspath(path)
        abs_root = os.path.abspath(self.root)
        if not abs_path.startswith(abs_root + os.sep) and abs_path != abs_root:
            raise WorkspaceError(
                f"Workspace path {abs_path} is outside root {abs_root}"
            )

        # Handle existing non-directory at path
        if os.path.exists(path) and not os.path.isdir(path):
            raise WorkspaceError(
                f"Path exists but is not a directory: {path}"
            )

        created_now = False
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
                created_now = True
            except OSError as exc:
                raise WorkspaceError(f"Failed to create workspace: {exc}")

        # Run after_create hook only on new workspaces
        if created_now and self.hooks.get("after_create"):
            try:
                self._run_hook("after_create", self.hooks["after_create"], path)
            except WorkspaceError:
                # after_create failure is fatal to workspace creation
                try:
                    shutil.rmtree(path)
                except OSError:
                    pass
                raise

        workspace = Workspace(path=abs_path, workspace_key=key, created_now=created_now)
        logger.info(
            "Workspace ready path=%s created_now=%s",
            abs_path,
            created_now,
        )
        return workspace

    def run_before_run(self, workspace_path: str) -> None:
        """Run before_run hook. Failure aborts the current attempt."""
        script = self.hooks.get("before_run")
        if script:
            self._run_hook("before_run", script, workspace_path)

    def run_after_run(self, workspace_path: str) -> None:
        """Run after_run hook. Failure is logged but not raised."""
        script = self.hooks.get("after_run")
        if script:
            try:
                self._run_hook("after_run", script, workspace_path)
            except WorkspaceError as exc:
                logger.warning("after_run hook failed (ignored): %s", exc)

    def remove_workspace(self, identifier: str) -> None:
        """Remove a workspace directory, running before_remove hook first."""
        key = sanitize_identifier(identifier)
        path = os.path.join(self.root, key)

        if not os.path.isdir(path):
            return

        # Run before_remove hook (best-effort)
        script = self.hooks.get("before_remove")
        if script:
            try:
                self._run_hook("before_remove", script, path)
            except WorkspaceError as exc:
                logger.warning("before_remove hook failed (ignored): %s", exc)

        try:
            shutil.rmtree(path)
            logger.info("Workspace removed path=%s", path)
        except OSError as exc:
            logger.warning("Failed to remove workspace path=%s error=%s", path, exc)

    def _run_hook(self, name: str, script: str, cwd: str) -> None:
        """Execute a hook script in the workspace directory."""
        timeout = max(self.hooks_timeout_ms, 1000) / 1000.0
        logger.info("Running hook=%s cwd=%s", name, cwd)

        try:
            result = subprocess.run(
                ["bash", "-lc", script],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise WorkspaceError(
                f"Hook '{name}' timed out after {timeout:.0f}s"
            )
        except OSError as exc:
            raise WorkspaceError(f"Hook '{name}' failed to execute: {exc}")

        if result.returncode != 0:
            stderr = result.stderr.strip()[:500]
            raise WorkspaceError(
                f"Hook '{name}' exited with code {result.returncode}: {stderr}"
            )

        logger.info("Hook completed hook=%s exit_code=0", name)
