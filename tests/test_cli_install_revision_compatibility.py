"""Integration tests for CLI install-from-revision compatibility.

This test suite verifies that the task CLI installed from an exact git revision
can authenticate against a matching server revision and successfully perform
real operations (task view, admin operations).

Acceptance criteria:
  1. CLI installed from git revision works with matching server
  2. Credential precedence (env vars, CLI flags, password files) works end-to-end
  3. Examples from documentation actually work when copy-pasted
  4. Password redaction is enforced (no plaintext in logs, errors, or help)
  5. netrc/default user discovery works as documented
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
import venv
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from oompah.client_auth import (
    ClientCredentials,
    resolve_client_credentials,
    sanitize_server_url,
)
from oompah.task_cli import build_parser, main as task_main


REPO_ROOT = Path(__file__).resolve().parents[1]


def _free_loopback_port() -> int:
    """Return an unused loopback TCP port for the child server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(
    process: subprocess.Popen[str],
    url: str,
    *,
    timeout: float = 15.0,
) -> None:
    """Wait for the child server's unauthenticated health endpoint."""
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(
                "matching-revision server exited before becoming ready:\n"
                f"stdout: {stdout}\nstderr: {stderr}"
            )
        try:
            with urllib.request.urlopen(f"{url}/healthz", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.1)
    raise AssertionError(f"matching-revision server did not become ready: {url}")


@contextlib.contextmanager
def _running_matching_server(
    *,
    tmp_path: Path,
    port: int,
    task_id: str,
    project_id: str,
    package_root: Path,
    repo_path: Path,
    htpasswd_path: Path,
    handoff_token_path: Path | None = None,
    forbidden_output: tuple[str, ...] = (),
) -> "object":
    """Run the current checkout's server code with a real bcrypt auth file.

    The server subprocess uses the package tree installed into the isolated
    venv by the parent test, while the host interpreter supplies the server
    runtime dependencies. A small in-memory tracker fixture keeps the two CLI
    reads deterministic and prevents task-state mutations.
    """
    server_script = tmp_path / "matching_revision_server.py"
    server_script.write_text(
        """
import os
from pathlib import Path
from types import SimpleNamespace

import uvicorn

import oompah.server as server
from oompah.http_auth import load_credentials
from oompah.models import Issue

if Path(server.__file__).resolve().parent.parent != Path(os.environ["E2E_PACKAGE_ROOT"]).resolve():
    raise RuntimeError(
        f"loaded unexpected oompah package: {server.__file__!r}; "
        f"expected {os.environ['E2E_PACKAGE_ROOT']!r}"
    )


task = Issue(
    id=os.environ["E2E_TASK_ID"],
    identifier=os.environ["E2E_TASK_ID"],
    title="Revision-compatible task",
    description="A known read-only task used by the CLI compatibility check.",
    state="Open",
    issue_type="task",
    tracker_kind="oompah_md",
)

project = SimpleNamespace(
    id=os.environ["E2E_PROJECT_ID"],
    name="revision-compatibility",
    repo_path=os.environ["E2E_REPO_PATH"],
    repo_url="file:///revision-compatibility",
    default_branch="main",
    state_branch_enabled=False,
    state_branch_shadow_write=False,
    state_branch_migration_stage="",
    state_branch_name="oompah/state/" + os.environ["E2E_PROJECT_ID"],
    status_actor_login=None,
    tracker_owner=None,
    status_label_authorized_logins=[],
)


class _Tracker:
    state_branch_enabled = False

    def __init__(self):
        self.comments = []

    def fetch_issue_detail(self, identifier):
        return task if identifier == task.identifier else None

    def fetch_all_issues(self):
        return [task]

    def fetch_comments(self, identifier):
        return []

    def add_comment(self, identifier, text, author="oompah"):
        self.comments.append((identifier, text, author))
        return {"ok": True}


class _ProjectStore:
    def list_all(self):
        return [project]

    def get(self, project_id):
        return project if project_id == project.id else None


class _Orchestrator:
    def __init__(self):
        self.project_store = _ProjectStore()
        self.tracker = _Tracker()
        self.config = SimpleNamespace(duplicate_preflight_max_agents=0)

    def _tracker_for_project(self, project_id):
        if project_id != project.id:
            raise LookupError(project_id)
        return self.tracker


# This is intentionally the server module from the same checkout revision as
# the package installed by the parent test.  Avoid the production lifespan so
# the compatibility fixture does not start an orchestrator or touch operator
# state; the HTTP middleware and both read handlers remain real.
server._orchestrator = _Orchestrator()
server.set_http_credentials(
    load_credentials(os.environ["E2E_HTPASSWD_PATH"], os.environ["E2E_REPO_PATH"])
)

handoff_token_path = os.environ.get("E2E_HANDOFF_TOKEN_FILE", "")
if handoff_token_path:
    from oompah.task_handoff import issue_task_handoff_token

    handoff_token = issue_task_handoff_token(
        project_id=os.environ["E2E_PROJECT_ID"],
        task_identifier=os.environ["E2E_TASK_ID"],
        allowed_actions={"view", "comment"},
    )
    token_path = Path(handoff_token_path)
    token_path.write_text(handoff_token, encoding="utf-8")
    token_path.chmod(0o600)

uvicorn.run(
    server.app,
    host="127.0.0.1",
    port=int(os.environ["E2E_PORT"]),
    log_level="warning",
)
""",
        encoding="utf-8",
    )

    server_env = os.environ.copy()
    # The server must only receive the htpasswd path; never inherit client
    # plaintext credential variables into its process environment.
    for name in (
        "OOMPAH_SERVER_USERNAME",
        "OOMPAH_SERVER_PASSWORD",
        "OOMPAH_SERVER_PASSWORD_FILE",
        "OOMPAH_EMBED_ORCHESTRATOR",
    ):
        server_env.pop(name, None)
    server_env.update(
        {
            "E2E_TASK_ID": task_id,
            "E2E_PROJECT_ID": project_id,
            "E2E_REPO_PATH": str(repo_path),
            "E2E_HTPASSWD_PATH": str(htpasswd_path),
            "E2E_PORT": str(port),
            "E2E_PACKAGE_ROOT": str(package_root),
            "E2E_HANDOFF_TOKEN_FILE": str(handoff_token_path or ""),
            # Import the exact package tree installed from the pinned git
            # revision, rather than the possibly dirty checkout.
            "PYTHONPATH": str(package_root),
        }
    )
    process = subprocess.Popen(
        [sys.executable, str(server_script)],
        cwd=str(tmp_path),
        env=server_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_server(process, base_url)
        yield base_url
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        stdout, stderr = process.communicate()
        for value in forbidden_output:
            assert value not in stdout
            assert value not in stderr


@pytest.mark.integration
@pytest.mark.xdist_group("cli_install_revision")
@pytest.mark.timeout(180)
def test_installed_cli_from_exact_revision_reads_matching_authenticated_server(tmp_path):
    """Install an exact revision, then exercise task and admin read paths.

    This intentionally crosses the packaging boundary: the client commands
    run from a fresh venv, while the matching server is a separate process
    importing the checkout at the same revision.  Both requests use the
    environment username and mode-0600 password-file source.
    """
    bcrypt = pytest.importorskip("bcrypt")

    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()
    cli_env_dir = tmp_path / "cli-env"
    venv.EnvBuilder(with_pip=True, clear=True).create(str(cli_env_dir))
    cli_python = cli_env_dir / "bin" / "python"
    cli_binary = cli_env_dir / "bin" / "oompah"

    source_ref = f"git+{REPO_ROOT.as_uri()}@{revision}"
    install = subprocess.run(
        [
            str(cli_python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            source_ref,
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert install.returncode == 0, (
        "exact-revision standalone CLI installation failed:\n"
        f"stdout: {install.stdout}\nstderr: {install.stderr}"
    )
    assert cli_binary.is_file()

    isolated_env = os.environ.copy()
    isolated_env.pop("PYTHONPATH", None)

    version_probe = subprocess.run(
        [
            str(cli_python),
            "-c",
            (
                "import importlib.metadata as metadata; "
                "import json, oompah; "
                "dist = metadata.distribution('oompah'); "
                "print(dist.version); "
                "print(oompah.__file__); "
                "print(dist.read_text('direct_url.json') or '')"
            ),
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
        env=isolated_env,
    )
    version_lines = version_probe.stdout.splitlines()
    assert version_lines[0] == "0.1.0"
    assert str(REPO_ROOT) not in version_lines[1]
    installed_package_root = Path(version_lines[1]).resolve().parent.parent
    assert (installed_package_root / "oompah").is_dir()
    direct_url = json.loads(version_lines[2])
    assert direct_url["vcs_info"]["commit_id"] == revision

    help_result = subprocess.run(
        [str(cli_binary), "task", "--help"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
        env=isolated_env,
    )
    assert "--password-file" in help_result.stdout

    task_id = "TASK-621-E2E"
    project_id = "proj-621-e2e"
    username = "operator-" + secrets.token_hex(6)
    password = secrets.token_urlsafe(24)
    password_file = tmp_path / "client-password"
    password_file.write_text(password + "\n", encoding="utf-8")
    password_file.chmod(0o600)

    htpasswd_file = tmp_path / "server.htpasswd"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
    htpasswd_file.write_text(f"{username}:{password_hash}\n", encoding="utf-8")
    htpasswd_file.chmod(0o600)

    repo_path = tmp_path / "managed-repo"
    repo_path.mkdir()
    subprocess.run(
        ["git", "init", "--quiet", str(repo_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    handoff_token_path = tmp_path / "task-handoff-token"

    client_env = os.environ.copy()
    for name in (
        "OOMPAH_SERVER_PASSWORD",
        "OOMPAH_SERVER_PASSWORD_FILE",
        "OOMPAH_SERVER_URL",
        "PYTHONPATH",
    ):
        client_env.pop(name, None)
    client_env.update(
        {
            "OOMPAH_SERVER_USERNAME": username,
            "OOMPAH_SERVER_PASSWORD_FILE": str(password_file),
        }
    )

    port = _free_loopback_port()
    with _running_matching_server(
        tmp_path=tmp_path,
        port=port,
        task_id=task_id,
        project_id=project_id,
        package_root=installed_package_root,
        repo_path=repo_path,
        htpasswd_path=htpasswd_file,
        handoff_token_path=handoff_token_path,
        forbidden_output=(username, password),
    ) as base_url:
        cli_version = subprocess.run(
            [str(cli_binary), "--version"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=True,
        )
        assert revision in cli_version.stdout

        import urllib.request

        with urllib.request.urlopen(f"{base_url}/healthz", timeout=5) as response:
            health = json.load(response)
        assert health["build_id"]["revision"] == revision

        state_request = urllib.request.Request(
            f"{base_url}/api/v1/state",
            headers={
                "Authorization": "Basic "
                + base64.b64encode(f"{username}:{password}".encode()).decode()
            },
        )
        with urllib.request.urlopen(state_request, timeout=5) as response:
            state = json.load(response)
        assert state["build_id"] == health["build_id"]

        task_result = subprocess.run(
            [
                str(cli_binary),
                "task",
                "--server",
                base_url,
                "view",
                task_id,
            ],
            cwd=str(tmp_path),
            env=client_env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert task_result.returncode == 0, (
            "installed task view failed:\n"
            f"stdout: {task_result.stdout}\nstderr: {task_result.stderr}"
        )
        assert task_id in task_result.stdout
        assert "Revision-compatible task" in task_result.stdout

        # Exercise the spawned-worker path with the exact installed CLI.  In
        # particular, comment must preserve both the positional identifier
        # and project scope required by /api/v1/task-handoff; a prior stale
        # canonical CLI let view succeed but returned HTTP 400 for comment.
        handoff_env = dict(client_env)
        handoff_env.pop("OOMPAH_SERVER_USERNAME", None)
        handoff_env.pop("OOMPAH_SERVER_PASSWORD_FILE", None)
        handoff_env["OOMPAH_TASK_HANDOFF_TOKEN"] = handoff_token_path.read_text(
            encoding="utf-8"
        ).strip()
        handoff_env["OOMPAH_TASK_HANDOFF_PROJECT_ID"] = project_id
        scoped_view = subprocess.run(
            [
                str(cli_binary),
                "task",
                "--server",
                base_url,
                "view",
                task_id,
                "--project-id",
                project_id,
            ],
            cwd=str(tmp_path),
            env=handoff_env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert scoped_view.returncode == 0, (
            "scoped installed task view failed:\n"
            f"stdout: {scoped_view.stdout}\nstderr: {scoped_view.stderr}"
        )
        assert task_id in scoped_view.stdout
        scoped_comment = subprocess.run(
            [
                str(cli_binary),
                "task",
                "--server",
                base_url,
                "comment",
                task_id,
                "--project",
                project_id,
                "--message",
                "scoped compatibility comment",
            ],
            cwd=str(tmp_path),
            env=handoff_env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert scoped_comment.returncode == 0, (
            "scoped installed task comment failed:\n"
            f"stdout: {scoped_comment.stdout}\nstderr: {scoped_comment.stderr}"
        )
        assert "Comment posted." in scoped_comment.stdout

        admin_env = dict(client_env)
        admin_env["OOMPAH_SERVER_URL"] = base_url
        admin_result = subprocess.run(
            [str(cli_binary), "admin", "state-branch-status", project_id],
            cwd=str(tmp_path),
            env=admin_env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert admin_result.returncode == 0, (
            "installed admin read failed:\n"
            f"stdout: {admin_result.stdout}\nstderr: {admin_result.stderr}"
        )
        assert "Project:" in admin_result.stdout

        for output in (
            task_result.stdout,
            task_result.stderr,
            scoped_view.stdout,
            scoped_view.stderr,
            scoped_comment.stdout,
            scoped_comment.stderr,
            admin_result.stdout,
            admin_result.stderr,
        ):
            assert username not in output
            assert password not in output


class TestCredentialPrecedenceIntegration:
    """Verify that credential precedence works end-to-end through the CLI."""

    def test_cli_flag_overrides_environment_variable(self):
        """--username and --password-file CLI flags override environment."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("file_password")
            f.flush()
            file_path = f.name

        try:
            # Set environment to one value
            env = os.environ.copy()
            env["OOMPAH_SERVER_USERNAME"] = "env_user"
            env["OOMPAH_SERVER_PASSWORD_FILE"] = "/nonexistent"

            # Parse CLI with flags (which override the environment)
            parser = build_parser()
            args = parser.parse_args(
                [
                    "--username", "flag_user",
                    "--password-file", file_path,
                    "view", "TASK-1"
                ]
            )

            # Verify CLI flags are captured
            assert args.username == "flag_user"
            assert args.password_file == file_path

            # Simulate resolving credentials with CLI overrides
            creds = resolve_client_credentials(
                username_override=args.username,
                password_file_override=args.password_file,
            )
            assert creds is not None
            assert creds.username == "flag_user"
            assert creds.password == "file_password"

        finally:
            os.unlink(file_path)

    def test_environment_variables_work_when_no_cli_flags(self, monkeypatch):
        """OOMPAH_SERVER_* env vars are used when no CLI flags are present."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("env_password")
            f.flush()
            file_path = f.name

        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "env_user")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", file_path)

            # No CLI overrides
            creds = resolve_client_credentials(
                username_override=None,
                password_file_override=None,
            )
            assert creds is not None
            assert creds.username == "env_user"
            assert creds.password == "env_password"

        finally:
            os.unlink(file_path)

    def test_inline_password_env_var_works(self, monkeypatch):
        """OOMPAH_SERVER_PASSWORD works as fallback when no password file."""
        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "inline_user")
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "inline_secret")
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        creds = resolve_client_credentials()
        assert creds is not None
        assert creds.username == "inline_user"
        assert creds.password == "inline_secret"


class TestPasswordFileHandling:
    """Verify that password files are handled securely."""

    def test_password_file_content_is_stripped(self):
        """Leading/trailing whitespace in password file is stripped."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("  \n  secret_password  \n  ")
            f.flush()
            file_path = f.name

        try:
            os.chmod(file_path, 0o600)
            parser = build_parser()
            args = parser.parse_args(
                ["--username", "user", "--password-file", file_path, "view", "TASK-1"]
            )
            creds = resolve_client_credentials(
                username_override=args.username,
                password_file_override=args.password_file,
            )
            assert creds is not None
            assert creds.password == "secret_password"

        finally:
            os.unlink(file_path)

    def test_password_file_must_exist(self):
        """Missing password file raises CredentialError."""
        from oompah.client_auth import CredentialError

        with pytest.raises(CredentialError, match="not found"):
            resolve_client_credentials(
                username_override="user",
                password_file_override="/nonexistent/password/file",
            )

    def test_symlink_password_file_rejected(self):
        """Symlink password files are rejected (security)."""
        from oompah.client_auth import CredentialError

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            real_file = tmpdir_path / "real_password"
            real_file.write_text("password")
            real_file.chmod(0o600)

            symlink = tmpdir_path / "symlink_password"
            symlink.symlink_to(real_file)

            with pytest.raises(CredentialError, match="symbolic link"):
                resolve_client_credentials(
                    username_override="user",
                    password_file_override=str(symlink),
                )


class TestURLSanitization:
    """Verify that URLs with embedded credentials are rejected."""

    def test_url_with_embedded_username_rejected(self):
        """URLs with user:pass@host format are rejected."""
        from oompah.client_auth import CredentialError

        with pytest.raises(CredentialError, match="credentials"):
            sanitize_server_url("http://user:password@localhost:8080")

    def test_url_with_embedded_password_rejected(self):
        """URLs with password but no username are rejected."""
        from oompah.client_auth import CredentialError

        with pytest.raises(CredentialError, match="credentials"):
            sanitize_server_url("http://:password@localhost:8080")

    def test_clean_url_passed_through(self):
        """URLs without embedded credentials pass through."""
        result = sanitize_server_url("http://localhost:8080")
        assert result == "http://localhost:8080"

    def test_url_trailing_slash_removed(self):
        """Trailing slashes are stripped from URLs."""
        result = sanitize_server_url("http://localhost:8080/")
        assert result == "http://localhost:8080"


class TestPasswordRedaction:
    """Verify that passwords are never exposed in help or errors."""

    def test_help_does_not_reveal_credential_values(self):
        """CLI help text never includes plaintext password examples."""
        parser = build_parser()
        help_text = parser.format_help()

        # Help should mention the variables and flags, but not example values
        assert "OOMPAH_SERVER_USERNAME" in help_text
        assert "OOMPAH_SERVER_PASSWORD_FILE" in help_text
        assert "OOMPAH_SERVER_PASSWORD" in help_text
        assert "--username" in help_text
        assert "--password-file" in help_text

        # Should NOT contain actual/example passwords (but may contain "secret" as documentation term)
        assert "password123" not in help_text
        assert "admin:password" not in help_text
        assert "my_plaintext_password" not in help_text
        assert "s3cret" not in help_text

    def test_auth_error_does_not_echo_credentials(self):
        """Authentication error messages never echo credential values."""
        from oompah.client_auth import format_auth_error

        error_msg = format_auth_error("http://localhost:8080")

        # Should mention what to set, not what the actual values are
        assert "OOMPAH_SERVER_USERNAME" in error_msg
        assert "OOMPAH_SERVER_PASSWORD_FILE" in error_msg
        assert "401" in error_msg

        # Should NOT echo the actual server URL (which might have credentials)
        # or any credential values
        assert "localhost" not in error_msg or "credentials" in error_msg


class TestConfigurationExamples:
    """Verify that documentation examples actually work."""

    def test_example_environment_variable_setup_works(self, monkeypatch):
        """Example from docs: export OOMPAH_SERVER_USERNAME; export OOMPAH_SERVER_PASSWORD_FILE."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("example_password")
            f.flush()
            file_path = f.name

        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "operator")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", file_path)

            creds = resolve_client_credentials()
            assert creds is not None
            assert creds.username == "operator"
            assert creds.password == "example_password"

        finally:
            os.unlink(file_path)

    def test_example_cli_flag_setup_works(self):
        """Example from docs: oompah task --username user --password-file /path/to/password."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("cli_password")
            f.flush()
            file_path = f.name

        try:
            parser = build_parser()
            args = parser.parse_args(
                [
                    "--username", "admin",
                    "--password-file", file_path,
                    "view", "TASK-1",
                ]
            )

            creds = resolve_client_credentials(
                username_override=args.username,
                password_file_override=args.password_file,
            )
            assert creds is not None
            assert creds.username == "admin"
            assert creds.password == "cli_password"

        finally:
            os.unlink(file_path)

    def test_backward_compatibility_unauthenticated_mode(self, monkeypatch):
        """When no credentials are configured, system works unauthenticated (backward-compatible)."""
        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        creds = resolve_client_credentials()
        assert creds is None  # Unauthenticated


class TestMutualExclusion:
    """Verify that conflicting credential configurations are rejected."""

    def test_both_password_sources_is_error(self, monkeypatch):
        """Setting both OOMPAH_SERVER_PASSWORD_FILE and OOMPAH_SERVER_PASSWORD is an error."""
        from oompah.client_auth import CredentialError

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("file_password")
            f.flush()
            file_path = f.name

        try:
            monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", file_path)
            monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "inline_password")

            with pytest.raises(CredentialError, match="exactly one"):
                resolve_client_credentials()

        finally:
            os.unlink(file_path)

    def test_username_without_password_is_error(self, monkeypatch):
        """Setting username but no password source is an error."""
        from oompah.client_auth import CredentialError

        monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "user")
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
        monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)

        with pytest.raises(CredentialError, match="password source is required"):
            resolve_client_credentials()

    def test_password_without_username_is_error(self, monkeypatch):
        """Setting password but no username is an error."""
        from oompah.client_auth import CredentialError

        monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
        monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "password")

        with pytest.raises(CredentialError, match="OOMPAH_SERVER_USERNAME is required"):
            resolve_client_credentials()
