"""Tests for the completion verifier (oompah-zlz_2-y0ns).

Covers the four acceptance criteria from the bead:

1. Full match: AC mentions a file AND the agent's diff touches it →
   close allowed.
2. Partial match: AC mentions a file AND the diff doesn't touch it →
   close rejected (and re-opened with a diagnostic comment).
3. No AC: bead has no ``# Acceptance criteria`` section → verification
   skipped (close allowed).
4. LLM fail-open: stage 2 LLM call fails / times out → close allowed.

Plus:

* The trickle-icl regression fixture: AC says "push to existing
  branch trickle-rl5" and the diff has no commits to trickle-rl5 →
  verifier rejects.
* Symbol-level checks: AC mentions ``_yolo_retry_ci`` and the diff
  contains a real change to it → close allowed.
* Skip rules: epic / ci-fix / merge-conflict / escalating attempt.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from oompah.completion_verifier import (
    ExtractedReferences,
    Stage1Result,
    Stage2Result,
    VerifierResult,
    _file_present,
    _parse_stage2_response,
    _symbol_present,
    compute_added_files,
    compute_diff,
    detect_new_backlog_files,
    extract_acceptance_section,
    extract_references,
    run_stage1,
    run_stage2_sync,
    should_skip_verification,
    verify_completion,
)
from oompah.models import Issue


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _issue(
    *,
    identifier: str = "oompah-test-1",
    description: str = "",
    labels: list[str] | None = None,
    issue_type: str = "feature",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title="test",
        description=description,
        issue_type=issue_type,
        labels=list(labels or []),
    )


@pytest.fixture
def git_repo(tmp_path):
    """Create a tiny git repo with a base commit on ``main``.

    Yields ``(repo_path, base_branch)``.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@test",
           "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@test"}

    def run(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, env=env,
                       capture_output=True)

    run("init", "-b", "main")
    (repo / "README.md").write_text("hello\n")
    run("add", ".")
    run("commit", "-m", "initial")
    # Create branch ``feat`` that we'll commit to.
    run("checkout", "-b", "feat")
    return repo, "main"


def _commit_files(repo, files: dict[str, str], message: str = "edit"):
    env = {**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@test",
           "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@test"}
    for rel, body in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, env=env,
                   capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True,
                   env=env, capture_output=True)


# --------------------------------------------------------------------------- #
# extract_acceptance_section
# --------------------------------------------------------------------------- #


class TestExtractAcceptanceSection:
    def test_empty_description(self):
        assert extract_acceptance_section(None) == ""
        assert extract_acceptance_section("") == ""

    def test_no_acceptance_section(self):
        desc = "# Goal\nDo a thing\n\n# Implementation\nHere it is"
        assert extract_acceptance_section(desc) == ""

    def test_simple_section(self):
        desc = (
            "Some prose first.\n\n"
            "# Acceptance criteria\n\n"
            "- Item 1\n"
            "- Item 2\n\n"
            "# Out of scope\n\nNot this.\n"
        )
        section = extract_acceptance_section(desc)
        assert "Item 1" in section
        assert "Item 2" in section
        assert "Not this" not in section

    def test_case_insensitive_header(self):
        desc = "## ACCEPTANCE CRITERIA\nFoo\n## Bar\nBaz"
        assert "Foo" in extract_acceptance_section(desc)
        assert "Baz" not in extract_acceptance_section(desc)

    def test_section_at_end_of_doc(self):
        desc = "# Acceptance criteria\n\n- only item\n"
        assert "only item" in extract_acceptance_section(desc)


# --------------------------------------------------------------------------- #
# extract_references
# --------------------------------------------------------------------------- #


class TestExtractReferences:
    def test_empty(self):
        refs = extract_references("")
        assert refs.files == []
        assert refs.symbols == []

    def test_files_with_directory(self):
        section = (
            "- A bead whose AC mentions `oompah/foo.py` AND the agent's "
            "diff doesn't touch `oompah/foo.py`.\n"
            "- Tests in `tests/test_completion_verifier.py`.\n"
        )
        refs = extract_references(section)
        assert "oompah/foo.py" in refs.files
        assert "tests/test_completion_verifier.py" in refs.files
        # Duplicates collapsed.
        assert refs.files.count("oompah/foo.py") == 1

    def test_symbols_dotted(self):
        section = "- The `ModelProvider.mode` field is required."
        refs = extract_references(section)
        assert "ModelProvider.mode" in refs.symbols

    def test_symbols_with_underscore(self):
        section = "- `_yolo_retry_ci` is called from the orchestrator."
        refs = extract_references(section)
        assert "_yolo_retry_ci" in refs.symbols

    def test_skip_url(self):
        section = "See `https://example.com/foo` for details."
        refs = extract_references(section)
        assert refs.files == []

    def test_skip_plain_word(self):
        section = "Just a `word` in code style."
        refs = extract_references(section)
        # "word" is neither a file (no /, no extension) nor a symbol
        # (no underscore, no dot).
        assert refs.files == []
        assert refs.symbols == []

    def test_skip_short_extension_only(self):
        section = "See `plan.md` for details."
        refs = extract_references(section)
        # Short file extension on a single-segment token with no
        # underscore is treated as a doc reference (skipped from
        # symbols), but accepted as a file because it has an
        # extension.
        assert "plan.md" in refs.files
        assert refs.symbols == []


# --------------------------------------------------------------------------- #
# _file_present, _symbol_present
# --------------------------------------------------------------------------- #


class TestFilePresent:
    def test_exact_match(self):
        assert _file_present("oompah/foo.py", ["oompah/foo.py", "tests/test_x.py"])

    def test_not_in_diff(self):
        assert not _file_present("oompah/foo.py", ["tests/test_x.py"])

    def test_glob_match(self):
        assert _file_present(
            "tests/test_*.py",
            ["tests/test_alpha.py", "oompah/foo.py"],
        )

    def test_suffix_match_for_subroot(self):
        # AC says "oompah/foo.py", diff (run from a subroot) has just
        # "foo.py" — still a match.
        assert _file_present("oompah/foo.py", ["foo.py"])


class TestSymbolPresent:
    def test_added_line_with_def(self):
        diff = "+def _yolo_retry_ci(self) -> None:"
        assert _symbol_present("_yolo_retry_ci", diff)

    def test_added_line_with_assignment(self):
        diff = "+    mode: str = \"api\""
        assert _symbol_present("ModelProvider.mode", diff)

    def test_context_line_does_not_count(self):
        diff = "    # comment mentioning _yolo_retry_ci as context\n"
        assert not _symbol_present("_yolo_retry_ci", diff)

    def test_empty_diff(self):
        assert not _symbol_present("_yolo_retry_ci", "")


# --------------------------------------------------------------------------- #
# compute_diff (against real git)
# --------------------------------------------------------------------------- #


class TestComputeDiff:
    def test_no_changes(self, git_repo):
        repo, base = git_repo
        files, body = compute_diff(str(repo), base)
        assert files == []

    def test_one_file_changed(self, git_repo):
        repo, base = git_repo
        _commit_files(repo, {"oompah/foo.py": "def hello():\n    pass\n"})
        files, body = compute_diff(str(repo), base)
        assert "oompah/foo.py" in files
        assert "def hello" in body

    def test_multiple_files(self, git_repo):
        repo, base = git_repo
        _commit_files(repo, {
            "oompah/a.py": "x = 1\n",
            "tests/test_a.py": "from oompah.a import x\n",
        })
        files, body = compute_diff(str(repo), base)
        assert set(files) == {"oompah/a.py", "tests/test_a.py"}

    def test_no_workspace(self, tmp_path):
        # Non-git directory: returns empty (no crash).
        files, body = compute_diff(str(tmp_path), "main")
        assert files == []
        assert body == ""


# --------------------------------------------------------------------------- #
# run_stage1
# --------------------------------------------------------------------------- #


class TestRunStage1:
    def test_full_match_files(self, git_repo):
        repo, base = git_repo
        _commit_files(repo, {"oompah/foo.py": "def bar():\n    pass\n"})
        issue = _issue(description=(
            "# Acceptance criteria\n"
            "- A bead whose AC mentions `oompah/foo.py` ...\n"
        ))
        result = run_stage1(issue, str(repo), base)
        assert result.missing_files == []
        assert not result.has_gaps

    def test_missing_file(self, git_repo):
        repo, base = git_repo
        _commit_files(repo, {"unrelated.py": "noop = 0\n"})
        issue = _issue(description=(
            "# Acceptance criteria\n"
            "- `oompah/foo.py` must exist with the new field.\n"
        ))
        result = run_stage1(issue, str(repo), base)
        assert "oompah/foo.py" in result.missing_files
        assert result.has_gaps

    def test_symbol_present(self, git_repo):
        repo, base = git_repo
        _commit_files(repo, {
            "oompah/o.py": "def _yolo_retry_ci(self):\n    pass\n",
        })
        issue = _issue(description=(
            "# Acceptance criteria\n"
            "- The `_yolo_retry_ci` helper is added.\n"
        ))
        result = run_stage1(issue, str(repo), base)
        assert result.missing_symbols == []

    def test_symbol_missing(self, git_repo):
        repo, base = git_repo
        _commit_files(repo, {"oompah/o.py": "x = 1\n"})
        issue = _issue(description=(
            "# Acceptance criteria\n"
            "- The `_yolo_retry_ci` helper is added.\n"
        ))
        result = run_stage1(issue, str(repo), base)
        assert "_yolo_retry_ci" in result.missing_symbols

    def test_no_ac_section(self, git_repo):
        repo, base = git_repo
        _commit_files(repo, {"x.py": "x = 1\n"})
        issue = _issue(description="No AC here, just prose.")
        result = run_stage1(issue, str(repo), base)
        assert result.references.files == []
        assert not result.has_gaps


# --------------------------------------------------------------------------- #
# _parse_stage2_response
# --------------------------------------------------------------------------- #


class TestParseStage2Response:
    def test_yes(self):
        v, r = _parse_stage2_response("VERDICT: YES — the diff matches.")
        assert v == "yes"
        assert "match" in r.lower()

    def test_no(self):
        v, r = _parse_stage2_response("VERDICT: NO — missing the field.")
        assert v == "no"
        assert "missing" in r.lower()

    def test_unparseable_fallback(self):
        v, r = _parse_stage2_response("I don't know.")
        assert v is None

    def test_bare_yes(self):
        v, r = _parse_stage2_response("YES the diff looks right.")
        assert v == "yes"

    def test_empty(self):
        v, r = _parse_stage2_response("")
        assert v is None


# --------------------------------------------------------------------------- #
# run_stage2_sync (LLM call, mocked)
# --------------------------------------------------------------------------- #


class TestRunStage2:
    def _provider(self, *, base_url="https://api.example.com", model="gpt-4o-mini"):
        p = MagicMock()
        p.base_url = base_url
        p.api_key = "sk-test"
        p.model_roles = {"fast": model}
        p.default_model = "default-model"
        p.models = []
        return p

    @patch("oompah.api_agent._http_post")
    def test_yes_verdict_means_pass(self, mock_post):
        mock_post.return_value = {
            "choices": [{"message": {"content": "VERDICT: YES — matches."}}]
        }
        result = run_stage2_sync("AC text", "diff text", self._provider())
        assert result.called
        assert result.verdict == "yes"
        assert result.is_fail_open  # caller treats as pass

    @patch("oompah.api_agent._http_post")
    def test_no_verdict_means_reject(self, mock_post):
        mock_post.return_value = {
            "choices": [{"message": {"content": "VERDICT: NO — gap detected."}}]
        }
        result = run_stage2_sync("AC text", "diff text", self._provider())
        assert result.says_no
        assert not result.is_fail_open

    @patch("oompah.api_agent._http_post")
    def test_http_error_fails_open(self, mock_post):
        mock_post.side_effect = RuntimeError("network down")
        result = run_stage2_sync("AC text", "diff text", self._provider())
        assert result.called
        assert result.verdict is None
        assert "network down" in result.error
        # ``is_fail_open`` returns True when called=True and verdict
        # is not "no" — error / unparseable → allow close.
        assert result.is_fail_open

    @patch("oompah.api_agent._http_post")
    def test_malformed_response_fails_open(self, mock_post):
        mock_post.return_value = {"weird": "shape"}
        result = run_stage2_sync("AC text", "diff text", self._provider())
        assert result.verdict is None
        assert result.is_fail_open

    def test_no_provider(self):
        result = run_stage2_sync("AC", "diff", None)
        assert result.called
        assert "no provider" in result.error.lower()
        assert result.is_fail_open

    def test_no_base_url(self):
        provider = self._provider(base_url="")
        result = run_stage2_sync("AC", "diff", provider)
        assert "base_url" in result.error.lower()
        assert result.is_fail_open


# --------------------------------------------------------------------------- #
# should_skip_verification
# --------------------------------------------------------------------------- #


class TestShouldSkip:
    def test_skip_epic(self):
        issue = _issue(issue_type="epic", description="# Acceptance criteria\n- x")
        skip, reason = should_skip_verification(issue)
        assert skip
        assert "epic" in reason

    def test_skip_ci_fix(self):
        issue = _issue(labels=["ci-fix"], description="# Acceptance criteria\n- x")
        skip, reason = should_skip_verification(issue)
        assert skip
        assert "ci-fix" in reason

    def test_skip_merge_conflict(self):
        issue = _issue(labels=["merge-conflict"], description="# Acceptance criteria\n- x")
        skip, _ = should_skip_verification(issue)
        assert skip

    def test_skip_escalating_attempt(self):
        issue = _issue(description="# Acceptance criteria\n- x")
        # When attempt >= escalate_after_attempts we let the close
        # stick so escalation can clear the runaway.
        skip, _ = should_skip_verification(
            issue, attempt=2, escalate_after_attempts=1,
        )
        assert skip

    def test_skip_no_ac(self):
        issue = _issue(description="No AC anywhere.")
        skip, reason = should_skip_verification(issue)
        assert skip
        assert "no acceptance" in reason.lower()

    def test_no_skip_normal_feature(self):
        issue = _issue(description="# Acceptance criteria\n- `oompah/foo.py` updated\n")
        skip, _ = should_skip_verification(issue)
        assert not skip


# --------------------------------------------------------------------------- #
# verify_completion — full integration scenarios
# --------------------------------------------------------------------------- #


class TestVerifyCompletion:
    def test_no_ac_skipped(self, git_repo):
        repo, base = git_repo
        _commit_files(repo, {"x.py": "x = 1\n"})
        issue = _issue(description="Just prose.")
        result = verify_completion(issue, str(repo), base, provider=None)
        assert result.passed
        assert result.skipped

    def test_full_file_match_allowed(self, git_repo):
        repo, base = git_repo
        _commit_files(repo, {"oompah/foo.py": "x = 1\n"})
        issue = _issue(description=(
            "# Acceptance criteria\n"
            "- `oompah/foo.py` is updated.\n"
        ))
        result = verify_completion(issue, str(repo), base, provider=None)
        assert result.passed
        assert not result.skipped

    def test_partial_match_rejected_without_llm(self, git_repo):
        """The first AC from the bead body — file mentioned, diff
        doesn't touch it → rejected even when stage 2 is disabled."""
        repo, base = git_repo
        _commit_files(repo, {"unrelated.py": "x = 1\n"})
        issue = _issue(description=(
            "# Acceptance criteria\n"
            "- A bead whose AC mentions `oompah/foo.py` AND the agent's "
            "diff doesn't touch `oompah/foo.py` → close rejected.\n"
        ))
        result = verify_completion(
            issue, str(repo), base, provider=None, enable_stage2=False,
        )
        assert not result.passed
        assert "oompah/foo.py" in result.stage1.missing_files

    def test_partial_match_stage2_says_yes_allowed(self, git_repo):
        """File missing in stage 1, but stage 2 LLM says YES → close
        allowed (fail-open principle: when LLM accepts, we accept)."""
        repo, base = git_repo
        _commit_files(repo, {"unrelated.py": "x = 1\n"})
        issue = _issue(description=(
            "# Acceptance criteria\n"
            "- `oompah/foo.py` updated\n"
        ))
        provider = MagicMock()
        provider.base_url = "https://api.example.com"
        provider.api_key = "sk-test"
        provider.model_roles = {"fast": "gpt-4o-mini"}
        provider.default_model = "default"
        provider.models = []
        with patch("oompah.api_agent._http_post") as mock_post:
            mock_post.return_value = {
                "choices": [
                    {"message": {"content": "VERDICT: YES — diff fine."}},
                ]
            }
            result = verify_completion(issue, str(repo), base, provider=provider)
        assert result.passed
        assert result.stage2 is not None
        assert result.stage2.verdict == "yes"

    def test_partial_match_stage2_says_no_rejected(self, git_repo):
        repo, base = git_repo
        _commit_files(repo, {"unrelated.py": "x = 1\n"})
        issue = _issue(description=(
            "# Acceptance criteria\n"
            "- `oompah/foo.py` updated\n"
        ))
        provider = MagicMock()
        provider.base_url = "https://api.example.com"
        provider.api_key = "sk-test"
        provider.model_roles = {"fast": "gpt-4o-mini"}
        provider.default_model = "default"
        provider.models = []
        with patch("oompah.api_agent._http_post") as mock_post:
            mock_post.return_value = {
                "choices": [
                    {"message": {"content": "VERDICT: NO — missing file."}},
                ]
            }
            result = verify_completion(issue, str(repo), base, provider=provider)
        assert not result.passed
        # Rejection comment includes both stage 1 + stage 2 diagnostics.
        comment = result.render_rejection_comment()
        assert "oompah/foo.py" in comment
        assert "missing file" in comment.lower()

    def test_stage2_timeout_fails_open(self, git_repo):
        repo, base = git_repo
        _commit_files(repo, {"unrelated.py": "x = 1\n"})
        issue = _issue(description=(
            "# Acceptance criteria\n"
            "- `oompah/foo.py` updated\n"
        ))
        provider = MagicMock()
        provider.base_url = "https://api.example.com"
        provider.api_key = "sk-test"
        provider.model_roles = {"fast": "gpt-4o-mini"}
        provider.default_model = "default"
        provider.models = []
        with patch("oompah.api_agent._http_post") as mock_post:
            mock_post.side_effect = TimeoutError("timed out")
            result = verify_completion(issue, str(repo), base, provider=provider)
        # LLM error → fail open → close allowed.
        assert result.passed
        assert result.stage2 is not None
        assert result.stage2.error

    def test_meaningful_symbol_change_allowed(self, git_repo):
        """AC mentions ``_yolo_retry_ci`` and the diff contains a real
        change to it → close allowed."""
        repo, base = git_repo
        _commit_files(repo, {
            "oompah/orchestrator.py": "def _yolo_retry_ci(self):\n    return 42\n",
        })
        issue = _issue(description=(
            "# Acceptance criteria\n"
            "- The `_yolo_retry_ci` helper handles the ci-fix case.\n"
        ))
        result = verify_completion(issue, str(repo), base, provider=None)
        assert result.passed


# --------------------------------------------------------------------------- #
# trickle-icl regression fixture
# --------------------------------------------------------------------------- #


class TestTrickleIclRegression:
    """Live verification: the trickle-icl scenario.

    Bead AC says "push to existing branch trickle-rl5". The agent
    instead created a new branch and pushed there. The diff against
    main contains the right code (it's the same fix) but the AC
    explicitly references the wrong branch name, so the verifier
    should reject.

    Since branch names aren't paths/symbols (we can't easily detect
    "did you push to branch X?" from a diff), we approximate the
    test: the AC mentions the file ``trickle-rl5-fix.rs`` which the
    agent didn't touch.
    """

    def test_branch_misroute_rejected(self, git_repo):
        repo, base = git_repo
        # Agent committed to a *new* branch under the wrong name —
        # but the diff against main only shows their (new) work, NOT
        # the file the AC said to update.
        _commit_files(repo, {
            "new_branch_work.rs": "fn unrelated() {}\n",
        })
        issue = _issue(
            identifier="trickle-icl-fixture",
            description=(
                "Re-fix CI on PR #23.\n\n"
                "# Acceptance criteria\n\n"
                "- Push to existing branch trickle-rl5.\n"
                "- `trickle-rl5-fix.rs` is updated with the lint fix.\n"
                "- Do not open a new PR.\n"
            ),
        )
        # No LLM (stage 2 disabled) — pure stage-1 check.
        result = verify_completion(
            issue, str(repo), base, provider=None, enable_stage2=False,
        )
        assert not result.passed
        assert "trickle-rl5-fix.rs" in result.stage1.missing_files
        comment = result.render_rejection_comment()
        assert "trickle-rl5-fix.rs" in comment


# --------------------------------------------------------------------------- #
# detect_new_backlog_files (unit)
# --------------------------------------------------------------------------- #


class TestDetectNewBacklogFiles:
    """Unit tests for the backlog-file path filter."""

    def test_task_file_detected(self):
        files = ["backlog/tasks/task-99.md", "oompah/foo.py"]
        result = detect_new_backlog_files(files)
        assert result == ["backlog/tasks/task-99.md"]

    def test_completed_file_detected(self):
        files = ["backlog/completed/task-100.md"]
        result = detect_new_backlog_files(files)
        assert result == ["backlog/completed/task-100.md"]

    def test_normal_files_not_flagged(self):
        files = ["oompah/foo.py", "tests/test_foo.py", "README.md"]
        assert detect_new_backlog_files(files) == []

    def test_empty_list(self):
        assert detect_new_backlog_files([]) == []

    def test_multiple_backlog_files(self):
        files = [
            "backlog/tasks/task-1.md",
            "backlog/completed/task-2.md",
            "oompah/server.py",
        ]
        result = detect_new_backlog_files(files)
        assert set(result) == {"backlog/tasks/task-1.md", "backlog/completed/task-2.md"}

    def test_partial_prefix_not_flagged(self):
        # "backlog/" alone or other subdirs must not be matched.
        files = ["backlog/config.yml", "backlog/docs/guide.md"]
        assert detect_new_backlog_files(files) == []


# --------------------------------------------------------------------------- #
# compute_added_files (git integration)
# --------------------------------------------------------------------------- #


class TestComputeAddedFiles:
    def test_new_file_appears(self, git_repo):
        repo, base = git_repo
        _commit_files(repo, {"newfile.txt": "hello\n"})
        added = compute_added_files(str(repo), base)
        assert "newfile.txt" in added

    def test_modified_file_excluded(self, git_repo):
        """Modified (not new) files must not appear — only added ones."""
        repo, base = git_repo
        # README.md was already committed in the fixture; modify it.
        _commit_files(repo, {"README.md": "modified\n"})
        added = compute_added_files(str(repo), base)
        assert "README.md" not in added

    def test_no_changes_returns_empty(self, git_repo):
        repo, base = git_repo
        added = compute_added_files(str(repo), base)
        assert added == []

    def test_non_git_dir_returns_empty(self, tmp_path):
        added = compute_added_files(str(tmp_path), "main")
        assert added == []


# --------------------------------------------------------------------------- #
# New backlog-file guard — full verify_completion integration
# --------------------------------------------------------------------------- #


def _issue_github(
    *,
    identifier: str = "owner/repo#42",
    description: str = "# Acceptance criteria\n\n- Something done.\n",
    labels: list[str] | None = None,
    issue_type: str = "task",
) -> Issue:
    """Return an Issue configured as a GitHub-backed task."""
    return Issue(
        id=identifier,
        identifier=identifier,
        title="test github task",
        description=description,
        issue_type=issue_type,
        labels=list(labels or []),
        tracker_kind="github_issues",
        tracker_owner="owner",
        tracker_repo="repo",
    )


def _issue_native(
    *,
    identifier: str = "OVA-42",
    description: str = "# Acceptance criteria\n\n- Something done.\n",
) -> Issue:
    """Return an Issue configured as a native oompah Markdown task."""
    return Issue(
        id=identifier,
        identifier=identifier,
        title="test native task",
        description=description,
        issue_type="task",
        labels=[],
        tracker_kind="oompah_md",
    )


class TestNewBacklogFilesGuard:
    """TASK-460.4: Backlog-file guard for non-Backlog oompah-managed tasks.

    AC#1 — GitHub-backed tasks fail verification if they add Backlog
    task files.
    AC#2 — The guard does not block legacy Backlog task updates.
    """

    # ----------------------------------------------------------------
    # AC#1: GitHub-backed tasks are rejected
    # ----------------------------------------------------------------

    def test_github_adds_backlog_task_file_rejected(self, git_repo):
        """AC#1: adding backlog/tasks/*.md rejects the close."""
        repo, base = git_repo
        _commit_files(repo, {"backlog/tasks/task-99.md": "# rogue task\n"})
        issue = _issue_github(identifier="owner/repo#1")
        result = verify_completion(issue, str(repo), base, provider=None)
        assert not result.passed
        assert "backlog/tasks/task-99.md" in result.new_backlog_files

    def test_native_adds_backlog_task_file_rejected(self, git_repo):
        """Native oompah Markdown tasks also reject new Backlog task files."""
        repo, base = git_repo
        _commit_files(repo, {"backlog/tasks/task-99.md": "# rogue task\n"})
        issue = _issue_native(identifier="OVA-1")
        result = verify_completion(issue, str(repo), base, provider=None)
        assert not result.passed
        assert "backlog/tasks/task-99.md" in result.new_backlog_files

    def test_github_adds_backlog_completed_file_rejected(self, git_repo):
        """AC#1: adding backlog/completed/*.md also rejects the close."""
        repo, base = git_repo
        _commit_files(repo, {"backlog/completed/task-100.md": "# done\n"})
        issue = _issue_github(identifier="owner/repo#2")
        result = verify_completion(issue, str(repo), base, provider=None)
        assert not result.passed
        assert "backlog/completed/task-100.md" in result.new_backlog_files

    def test_github_adds_multiple_backlog_files_all_reported(self, git_repo):
        """All newly-added backlog files are listed in the result."""
        repo, base = git_repo
        _commit_files(repo, {
            "backlog/tasks/task-1.md": "# t1\n",
            "backlog/tasks/task-2.md": "# t2\n",
        })
        issue = _issue_github(identifier="owner/repo#3")
        result = verify_completion(issue, str(repo), base, provider=None)
        assert not result.passed
        assert "backlog/tasks/task-1.md" in result.new_backlog_files
        assert "backlog/tasks/task-2.md" in result.new_backlog_files

    def test_github_no_backlog_files_passes(self, git_repo):
        """GitHub-backed task with only normal files is not blocked."""
        repo, base = git_repo
        _commit_files(repo, {"oompah/foo.py": "x = 1\n"})
        issue = _issue_github(
            identifier="owner/repo#4",
            description="# Acceptance criteria\n\n- `oompah/foo.py` updated.\n",
        )
        result = verify_completion(issue, str(repo), base, provider=None)
        assert result.passed

    def test_guard_fires_before_skip_rules_epic(self, git_repo):
        """AC#1: guard fires even for epics (not bypassed by skip rules)."""
        repo, base = git_repo
        _commit_files(repo, {"backlog/tasks/task-99.md": "# epic child\n"})
        issue = _issue_github(identifier="owner/repo#5", issue_type="epic")
        result = verify_completion(issue, str(repo), base, provider=None)
        assert not result.passed
        assert "backlog/tasks/task-99.md" in result.new_backlog_files

    def test_guard_fires_before_skip_rules_ci_fix_label(self, git_repo):
        """AC#1: guard fires even when ci-fix label is present."""
        repo, base = git_repo
        _commit_files(repo, {"backlog/tasks/task-99.md": "# ci fix task\n"})
        issue = _issue_github(identifier="owner/repo#6", labels=["ci-fix"])
        result = verify_completion(issue, str(repo), base, provider=None)
        assert not result.passed
        assert "backlog/tasks/task-99.md" in result.new_backlog_files

    # ----------------------------------------------------------------
    # AC#2: legacy Backlog tasks are not blocked
    # ----------------------------------------------------------------

    def test_legacy_backlog_task_none_tracker_kind_not_blocked(self, git_repo):
        """AC#2: tracker_kind=None (legacy) does not trigger the guard."""
        repo, base = git_repo
        _commit_files(repo, {"backlog/tasks/task-99.md": "# legacy task\n"})
        # Default _issue() has no tracker_kind (None → legacy mode).
        issue = _issue(description="No AC here.")
        result = verify_completion(issue, str(repo), base, provider=None)
        # Skips (no AC section), but most importantly does NOT reject for
        # backlog files.
        assert result.passed
        assert result.new_backlog_files == []

    def test_legacy_backlog_md_tracker_kind_not_blocked(self, git_repo):
        """AC#2: tracker_kind=backlog_md explicitly legacy → not blocked."""
        repo, base = git_repo
        _commit_files(repo, {"backlog/tasks/task-99.md": "# task\n"})
        issue = _issue(description="No AC.")
        issue.tracker_kind = "backlog_md"
        result = verify_completion(issue, str(repo), base, provider=None)
        assert result.passed
        assert result.new_backlog_files == []

    def test_legacy_backlog_tracker_kind_with_ac_not_blocked(self, git_repo):
        """AC#2: legacy task with an AC section still not blocked."""
        repo, base = git_repo
        _commit_files(repo, {
            "backlog/tasks/task-99.md": "# updated task\n",
            "oompah/foo.py": "x = 1\n",
        })
        issue = _issue(description=(
            "# Acceptance criteria\n"
            "- `oompah/foo.py` is updated.\n"
        ))
        # tracker_kind=None → legacy; guard must not fire.
        result = verify_completion(issue, str(repo), base, provider=None)
        assert result.passed
        assert result.new_backlog_files == []

    # ----------------------------------------------------------------
    # Rejection comment
    # ----------------------------------------------------------------

    def test_rejection_comment_mentions_backlog_files(self, git_repo):
        repo, base = git_repo
        _commit_files(repo, {"backlog/tasks/task-99.md": "# rogue\n"})
        issue = _issue_github(identifier="owner/repo#7")
        result = verify_completion(issue, str(repo), base, provider=None)
        assert not result.passed
        comment = result.render_rejection_comment()
        assert "backlog/tasks/task-99.md" in comment
        assert "oompah task" in comment.lower()

    def test_rejection_comment_includes_oompah_task_guidance(self, git_repo):
        repo, base = git_repo
        _commit_files(repo, {"backlog/completed/done-1.md": "# done\n"})
        issue = _issue_github(identifier="owner/repo#8")
        result = verify_completion(issue, str(repo), base, provider=None)
        comment = result.render_rejection_comment()
        assert "backlog/completed/done-1.md" in comment
        # Must guide the agent to use oompah task create instead.
        assert "oompah task create" in comment

    def test_rejection_comment_standalone_backlog_guard(self):
        """render_rejection_comment works for a guard-only rejection."""
        r = VerifierResult(
            passed=False,
            new_backlog_files=["backlog/tasks/task-1.md", "backlog/tasks/task-2.md"],
        )
        comment = r.render_rejection_comment()
        assert "backlog/tasks/task-1.md" in comment
        assert "backlog/tasks/task-2.md" in comment
        assert "GitHub-backed" in comment
        assert "oompah task create" in comment


# --------------------------------------------------------------------------- #
# Rejection comment rendering
# --------------------------------------------------------------------------- #


class TestRejectionComment:
    def test_files_only(self):
        r = VerifierResult(
            passed=False,
            stage1=Stage1Result(
                references=ExtractedReferences(),
                missing_files=["oompah/foo.py", "tests/test_x.py"],
            ),
        )
        comment = r.render_rejection_comment()
        assert "oompah/foo.py" in comment
        assert "tests/test_x.py" in comment
        assert "completion verifier" in comment.lower()

    def test_with_llm_reasoning(self):
        r = VerifierResult(
            passed=False,
            stage1=Stage1Result(
                references=ExtractedReferences(),
                missing_files=["oompah/foo.py"],
            ),
            stage2=Stage2Result(
                called=True,
                verdict="no",
                reasoning="diff only updates CSS, not the dataclass field",
            ),
        )
        comment = r.render_rejection_comment()
        assert "diff only updates CSS" in comment
