"""Noninteractive git subprocess helpers (OOMPAH-647).

Every server-generated git call that may trigger a commit-message edit
(rebase --continue, cherry-pick --continue, merge --continue) MUST use the
environment provided by this module so that no interactive editor can block
an agent slot.

Design decisions
----------------
* ``GIT_EDITOR=true`` and ``GIT_SEQUENCE_EDITOR=true`` cause git to invoke
  the POSIX ``true`` binary instead of an editor.  ``true`` immediately exits
  0, leaving the commit message exactly as git prepared it in COMMIT_EDITMSG.
  This preserves the original message (including oompah attribution trailers)
  without any human or editor intervention.

* ``GIT_TERMINAL_PROMPT=0`` prevents git from opening interactive prompts for
  missing credentials or unknown host keys.

* ``GIT_ASKPASS=true`` routes password-prompt callbacks to ``true``, which
  returns an empty string and exit 0 — git fails the auth attempt instead of
  blocking.

* ``GIT_SSH_COMMAND="ssh -oBatchMode=yes"`` prevents SSH from asking for
  passphrases or accepting unknown host keys interactively.

* The environment is *merged* with the current process environment so that
  existing PATH, HOME, and git configuration variables are preserved.
  Only the above overrides are forced in.

* ``run_rebase_continue`` wraps ``git rebase --continue`` with a hard process
  timeout plus a kill of the entire process group.  If the process exceeds
  the timeout (e.g. because an editor was somehow started anyway), we:
    1. Send SIGTERM to the process group.
    2. Wait ``kill_timeout`` seconds.
    3. Send SIGKILL to any survivors.
    4. Return a failure result that preserves the rebase state — the staged
       resolution is already in the index and ``REBASE_HEAD`` is still on
       disk, so the caller can inspect the state and retry.

Usage
-----
Server-side git subprocess calls:

    from oompah.git_noninteractive import NONINTERACTIVE_GIT_ENV, run_git_noninteractive

    result = run_git_noninteractive(repo_path, "rebase", expected_sha, timeout=600)

For rebase continuation specifically:

    from oompah.git_noninteractive import run_rebase_continue

    result = run_rebase_continue(repo_path, timeout=120)
    if not result.success:
        # rebase state is still on disk — staged resolution is preserved
        log.warning("rebase --continue timed out or failed: %s", result.message)

Agent-side instructions (focus.py must_do):
    Always use ``GIT_EDITOR=true GIT_SEQUENCE_EDITOR=true git rebase --continue``
    or ``git -c core.editor=true rebase --continue`` to prevent git from
    spawning an interactive editor for the commit message.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical noninteractive environment overrides
# ---------------------------------------------------------------------------

#: Environment variable overrides that prevent git from spawning any
#: interactive editor, password prompt, or SSH confirmation dialog.
#: Merge this over ``os.environ`` before running any git subprocess that
#: might open COMMIT_EDITMSG (rebase --continue, cherry-pick --continue,
#: merge --continue, commit --amend, etc.).
NONINTERACTIVE_GIT_ENV: dict[str, str] = {
    # Use the POSIX 'true' binary as the editor — it exits 0 immediately
    # without reading or writing anything, leaving COMMIT_EDITMSG unchanged.
    "GIT_EDITOR": "true",
    # Same treatment for interactive rebase sequence editing.
    "GIT_SEQUENCE_EDITOR": "true",
    # Disable git's built-in terminal prompt for credentials / server info.
    "GIT_TERMINAL_PROMPT": "0",
    # Route git's ask-pass callbacks to 'true' (returns empty string, exit 0).
    "GIT_ASKPASS": "true",
    # Prevent SSH from asking for passphrases or accepting unknown host keys.
    "GIT_SSH_COMMAND": "ssh -oBatchMode=yes",
}


def _make_env(extra_env: dict[str, str] | None = None) -> dict[str, str]:
    """Return a subprocess environment with noninteractive overrides applied.

    Starts from the current process environment so PATH, HOME, and git
    configuration are preserved.  Forces in :data:`NONINTERACTIVE_GIT_ENV`
    last so they cannot be overridden by the caller's ``extra_env``.
    """
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    # Force noninteractive overrides last — they must never be skipped.
    env.update(NONINTERACTIVE_GIT_ENV)
    return env


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GitResult:
    """Result of a noninteractive git subprocess call."""

    success: bool
    returncode: int
    stdout: str
    stderr: str
    message: str = ""
    timed_out: bool = False
    rebase_state_preserved: bool = False


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def run_git_noninteractive(
    repo_path: str,
    *args: str,
    timeout: int = 60,
    extra_env: dict[str, str] | None = None,
) -> GitResult:
    """Run a git command in *repo_path* with the noninteractive environment.

    This is the server-safe replacement for bare ``subprocess.run(['git', ...])``.
    The caller must never rely on any interactive editor or terminal prompt
    being available.

    Parameters
    ----------
    repo_path:
        Absolute path to the git repository or worktree.
    *args:
        Arguments passed to git after ``git -C <repo_path>``.
    timeout:
        Hard timeout in seconds.  The process is killed if it exceeds this.
    extra_env:
        Additional environment variables to set.  These are applied before
        the noninteractive overrides, so they cannot override safety vars.

    Returns
    -------
    GitResult
        Always returns a result; never raises on git failure.
    """
    env = _make_env(extra_env)
    try:
        proc = subprocess.run(
            ["git", "-C", repo_path, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return GitResult(
            success=proc.returncode == 0,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = (exc.stderr or b"").decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return GitResult(
            success=False,
            returncode=-1,
            stdout=stdout,
            stderr=stderr,
            message=f"git {' '.join(args)} timed out after {timeout}s",
            timed_out=True,
        )
    except OSError as exc:
        return GitResult(
            success=False,
            returncode=-1,
            stdout="",
            stderr="",
            message=f"git {' '.join(args)} failed to start: {exc}",
        )


def _is_rebase_in_progress(repo_path: str) -> bool:
    """Return True when a rebase is in progress in *repo_path*.

    Checks for the ``REBASE_HEAD`` file that git creates at the start of a
    rebase and removes only on successful completion or explicit abort.
    """
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "--git-dir"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False
        git_dir = result.stdout.strip()
        if not os.path.isabs(git_dir):
            git_dir = os.path.join(repo_path, git_dir)
        return os.path.exists(os.path.join(git_dir, "REBASE_HEAD"))
    except Exception:  # noqa: BLE001
        return False


def run_rebase_continue(
    repo_path: str,
    timeout: int = 120,
    kill_timeout: int = 10,
    extra_env: dict[str, str] | None = None,
) -> GitResult:
    """Run ``git rebase --continue`` with bounded timeout and kill-on-hang.

    This is the safe server-side entry point for advancing a paused rebase
    after conflicts have been staged.  It guarantees:

    * Git will not spawn an interactive editor for the commit message.
    * If the process exceeds *timeout* (e.g. due to an unexpected prompt or
      a frozen child process), the entire process group is killed.
    * After a timeout kill, the rebase state is preserved on disk so the
      caller can inspect the staged index and retry.

    Parameters
    ----------
    repo_path:
        Absolute path to the git repository or worktree.
    timeout:
        Seconds to wait before force-killing the process.
    kill_timeout:
        Seconds to wait between SIGTERM and SIGKILL.
    extra_env:
        Additional environment variables (applied before noninteractive overrides).

    Returns
    -------
    GitResult
        ``success=True`` on a clean exit 0.  On timeout, ``timed_out=True``
        and ``rebase_state_preserved=True`` when REBASE_HEAD is still present.
    """
    env = _make_env(extra_env)

    try:
        proc = subprocess.Popen(
            ["git", "-C", repo_path, "rebase", "--continue"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=True,  # create a new process group for clean kill
        )
    except OSError as exc:
        return GitResult(
            success=False,
            returncode=-1,
            stdout="",
            stderr="",
            message=f"git rebase --continue failed to start: {exc}",
        )

    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        returncode = proc.returncode
        return GitResult(
            success=returncode == 0,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    except subprocess.TimeoutExpired:
        logger.warning(
            "git rebase --continue timed out after %ss in %s — killing process group",
            timeout,
            repo_path,
        )
        pgid = None
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            proc.terminate()

        try:
            proc.wait(timeout=kill_timeout)
        except subprocess.TimeoutExpired:
            logger.warning(
                "git rebase --continue did not exit after SIGTERM — sending SIGKILL"
            )
            try:
                if pgid is not None:
                    os.killpg(pgid, signal.SIGKILL)
                else:
                    proc.kill()
            except (ProcessLookupError, OSError):
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass

        # Drain any remaining output without blocking.
        try:
            stdout_raw, stderr_raw = proc.communicate(timeout=2)
        except (subprocess.TimeoutExpired, ValueError):
            stdout_raw, stderr_raw = "", ""

        state_preserved = _is_rebase_in_progress(repo_path)
        message = (
            f"git rebase --continue timed out after {timeout}s and was killed; "
            + ("rebase state preserved on disk (REBASE_HEAD exists)" if state_preserved
               else "WARNING: rebase state may have been lost")
        )
        logger.warning(message)
        return GitResult(
            success=False,
            returncode=-1,
            stdout=stdout_raw or "",
            stderr=stderr_raw or "",
            message=message,
            timed_out=True,
            rebase_state_preserved=state_preserved,
        )
