"""Tests for the oompah prepare-commit-msg hook (oompah-zlz_2-3cpz).

The hook script lives at ``oompah/git_hooks/prepare-commit-msg`` and is
*not* an importable Python module (no ``.py`` suffix; git invokes it as
an executable). To exercise its pure-function core (``transform``) we
load the script with ``importlib`` at test time.
"""
from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Loader for the hook module
# ---------------------------------------------------------------------------

_HOOK_PATH = (
    Path(__file__).resolve().parent.parent
    / "oompah"
    / "git_hooks"
    / "prepare-commit-msg"
)


def _load_hook_module():
    # The hook file has no .py suffix (git invokes it by name) so the default
    # source-file finder won't recognise it. Drive the loader explicitly.
    from importlib.machinery import SourceFileLoader

    loader = SourceFileLoader("_oompah_prepare_commit_msg", str(_HOOK_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


hook = _load_hook_module()
transform = hook.transform
OOMPAH_BOT_LINE = hook.OOMPAH_BOT_LINE
OOMPAH_COAUTHOR = hook.OOMPAH_COAUTHOR


# ---------------------------------------------------------------------------
# Canonical constants
# ---------------------------------------------------------------------------


class TestCanonicalConstants:
    def test_bot_line_exact(self):
        assert OOMPAH_BOT_LINE.startswith("🤖 Generated with https://github.com/")
        assert OOMPAH_BOT_LINE.endswith("/oompah")

    def test_coauthor_exact(self):
        # Lowercase 'Co-authored-by' (GitHub canonical form), oompah name,
        # users.noreply.github.com email for profile linking.
        assert OOMPAH_COAUTHOR.startswith("Co-authored-by: oompah <")
        assert OOMPAH_COAUTHOR.endswith("@users.noreply.github.com>")


# ---------------------------------------------------------------------------
# Required acceptance-criteria cases from the issue
# ---------------------------------------------------------------------------


class TestEmptyMessage:
    def test_empty_string_gets_trailer(self):
        out = transform("")
        # An empty message gets the trailer (with no leading body).
        assert OOMPAH_BOT_LINE in out
        assert OOMPAH_COAUTHOR in out

    def test_whitespace_only_message_gets_trailer(self):
        out = transform("\n\n")
        assert OOMPAH_BOT_LINE in out
        assert OOMPAH_COAUTHOR in out

    def test_message_with_only_git_template_gets_trailer(self):
        # prepare-commit-msg often runs with body+'# Please enter the commit
        # message...' template. Empty body, comments at bottom.
        text = (
            "\n"
            "# Please enter the commit message for your changes. Lines starting\n"
            "# with '#' will be ignored, and an empty message aborts the commit.\n"
            "#\n"
            "# On branch oompah-test\n"
        )
        out = transform(text)
        assert OOMPAH_BOT_LINE in out
        assert OOMPAH_COAUTHOR in out
        # The git template must survive.
        assert "# Please enter the commit message" in out


class TestClaudeTrailerReplaced:
    def test_classic_claude_trailer_replaced(self):
        text = (
            "oompah-zlz_2-3cpz: do the thing\n"
            "\n"
            "Some body text.\n"
            "\n"
            "🤖 Generated with [Claude Code](https://claude.com/claude-code)\n"
            "\n"
            "Co-Authored-By: Claude <noreply@anthropic.com>\n"
        )
        out = transform(text)
        assert "Claude" not in out
        assert "anthropic.com" not in out
        assert OOMPAH_BOT_LINE in out
        assert OOMPAH_COAUTHOR in out
        # Body content preserved.
        assert "oompah-zlz_2-3cpz: do the thing" in out
        assert "Some body text." in out

    def test_claude_with_model_suffix_replaced(self):
        # The issue's exact example.
        text = (
            "fix: bug\n"
            "\n"
            "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>\n"
        )
        out = transform(text)
        assert "Claude" not in out
        assert "anthropic.com" not in out
        assert OOMPAH_COAUTHOR in out

    def test_gpt_trailer_stripped(self):
        text = (
            "fix: thing\n"
            "\n"
            "Co-authored-by: GPT-5 <noreply@openai.com>\n"
        )
        out = transform(text)
        assert "GPT" not in out
        assert "openai.com" not in out
        assert OOMPAH_COAUTHOR in out

    def test_arbitrary_model_coauthor_stripped(self):
        # Allowlist is strict: only 'oompah' passes.
        text = (
            "fix: thing\n"
            "\n"
            "Co-authored-by: SomeOtherModel <foo@example.com>\n"
        )
        out = transform(text)
        assert "SomeOtherModel" not in out
        assert "foo@example.com" not in out
        assert OOMPAH_COAUTHOR in out


class TestOompahTrailerUnchanged:
    def test_already_correct_left_alone(self):
        text = (
            "oompah-zlz_2-3cpz: foo\n"
            "\n"
            "Body line.\n"
            "\n"
            f"{OOMPAH_BOT_LINE}\n"
            "\n"
            f"{OOMPAH_COAUTHOR}\n"
        )
        out = transform(text)
        # Exactly one occurrence of each canonical line.
        assert out.count(OOMPAH_BOT_LINE) == 1
        assert out.count(OOMPAH_COAUTHOR) == 1
        # Body preserved.
        assert "oompah-zlz_2-3cpz: foo" in out
        assert "Body line." in out

    def test_idempotent_double_run(self):
        text = (
            "fix: something\n"
            "\n"
            "Co-Authored-By: Claude <noreply@anthropic.com>\n"
        )
        once = transform(text)
        twice = transform(once)
        thrice = transform(twice)
        assert once == twice == thrice
        assert "Claude" not in once
        assert once.count(OOMPAH_BOT_LINE) == 1
        assert once.count(OOMPAH_COAUTHOR) == 1


class TestSignedOffByPreserved:
    def test_signed_off_by_kept_claude_replaced(self):
        text = (
            "oompah-zlz_2-3cpz: thing\n"
            "\n"
            "Body.\n"
            "\n"
            "Signed-off-by: Sam Edwards <sam@example.com>\n"
            "Co-Authored-By: Claude <noreply@anthropic.com>\n"
        )
        out = transform(text)
        assert "Signed-off-by: Sam Edwards <sam@example.com>" in out
        assert "Claude" not in out
        assert "anthropic.com" not in out
        assert OOMPAH_COAUTHOR in out
        assert OOMPAH_BOT_LINE in out

    def test_reviewed_by_kept(self):
        text = (
            "fix: thing\n"
            "\n"
            "Reviewed-by: Alice <alice@example.com>\n"
            "Tested-by: Bob <bob@example.com>\n"
            "Co-Authored-By: Claude <noreply@anthropic.com>\n"
        )
        out = transform(text)
        assert "Reviewed-by: Alice <alice@example.com>" in out
        assert "Tested-by: Bob <bob@example.com>" in out
        assert "Claude" not in out
        assert OOMPAH_COAUTHOR in out


class TestMultilineBodyPreserved:
    def test_paragraph_body_intact_before_and_after_trailer(self):
        text = (
            "oompah-zlz_2-3cpz: implement feature X\n"
            "\n"
            "First paragraph of the body. It explains motivation.\n"
            "Continues on the second line.\n"
            "\n"
            "Second paragraph. Lists changes:\n"
            "- bullet one\n"
            "- bullet two\n"
            "\n"
            "Third paragraph for posterity.\n"
        )
        out = transform(text)
        # All body content survives.
        assert "First paragraph of the body. It explains motivation." in out
        assert "Continues on the second line." in out
        assert "Second paragraph. Lists changes:" in out
        assert "- bullet one" in out
        assert "- bullet two" in out
        assert "Third paragraph for posterity." in out
        # Trailer appended.
        assert OOMPAH_BOT_LINE in out
        assert OOMPAH_COAUTHOR in out
        # The trailer is at the END (after the third paragraph), with a
        # blank line separating body from the trailer block.
        body_idx = out.find("Third paragraph for posterity.")
        trailer_idx = out.find(OOMPAH_BOT_LINE)
        assert body_idx < trailer_idx

    def test_body_with_existing_claude_trailer_mid_then_at_end(self):
        # When a trailer-shaped line is at column 0 in the middle of the
        # body, the hook still strips it (the agent likely meant it as a
        # real trailer that got split across paragraphs). This is acceptable
        # behavior — Claude/Anthropic mentions inside Co-authored-by lines
        # should always be stripped.
        text = (
            "fix: thing\n"
            "\n"
            "First body line.\n"
            "Co-authored-by: Claude <noreply@anthropic.com>\n"
            "Last body line.\n"
        )
        out = transform(text)
        assert "First body line." in out
        assert "Last body line." in out
        assert "Claude" not in out
        assert OOMPAH_COAUTHOR in out

    def test_indented_trailer_examples_in_body_left_alone(self):
        # Regression: a commit message that DOCUMENTS the canonical trailer
        # by quoting it indented inside its body must not be treated as if
        # the trailer is already present (causing the real trailer to be
        # skipped). Git's trailer convention requires column-0 placement,
        # and we follow it.
        text = (
            "feat: document the trailer\n"
            "\n"
            "We now require commits to end with this block:\n"
            "\n"
            f"  {OOMPAH_BOT_LINE}\n"
            "\n"
            f"  {OOMPAH_COAUTHOR}\n"
            "\n"
            "Body continues here with more discussion.\n"
        )
        out = transform(text)
        # Indented example text is preserved verbatim.
        assert f"  {OOMPAH_BOT_LINE}" in out
        assert f"  {OOMPAH_COAUTHOR}" in out
        assert "Body continues here with more discussion." in out
        # A REAL canonical trailer is still appended at the end (column 0).
        # The last two non-blank lines should be the bot line + coauthor.
        lines = [
            line for line in out.splitlines()
            if line.strip() != "" and not line.startswith("#")
        ]
        assert lines[-1] == OOMPAH_COAUTHOR
        assert lines[-2] == OOMPAH_BOT_LINE
        # And the column-0 trailer count is exactly one of each.
        col0 = [line for line in out.splitlines() if line and not line[0].isspace() and not line.startswith("#")]
        assert sum(1 for line in col0 if line == OOMPAH_BOT_LINE) == 1
        assert sum(1 for line in col0 if line == OOMPAH_COAUTHOR) == 1

    def test_indented_claude_example_in_body_left_alone(self):
        # Even an indented Claude example in body content is body content,
        # not a trailer — we must not strip it.
        text = (
            "feat: explain what NOT to do\n"
            "\n"
            "Do NOT use the legacy trailer:\n"
            "\n"
            "  Co-Authored-By: Claude <noreply@anthropic.com>\n"
            "\n"
            "Use the oompah form instead.\n"
        )
        out = transform(text)
        # The indented Claude example is preserved (this is body documentation).
        assert "  Co-Authored-By: Claude <noreply@anthropic.com>" in out
        # The real canonical trailer is appended.
        assert OOMPAH_BOT_LINE in out
        assert OOMPAH_COAUTHOR in out


# ---------------------------------------------------------------------------
# Bonus coverage — edge cases beyond the listed AC
# ---------------------------------------------------------------------------


class TestBotLineVariants:
    def test_alternate_robot_url_stripped(self):
        # Other 🤖 lines from other tools get stripped & replaced.
        text = (
            "fix: thing\n"
            "\n"
            "🤖 Generated with [Claude Code](https://claude.com/claude-code)\n"
        )
        out = transform(text)
        assert "claude.com/claude-code" not in out
        assert OOMPAH_BOT_LINE in out

    def test_no_bot_line_at_all_appended(self):
        text = (
            "fix: thing\n"
            "\n"
            "Co-Authored-By: Claude <noreply@anthropic.com>\n"
        )
        out = transform(text)
        assert OOMPAH_BOT_LINE in out


class TestEditorTemplatePreservation:
    def test_git_editor_comments_kept_when_appending_trailer(self):
        text = (
            "feat: add widget\n"
            "\n"
            "Adds the widget.\n"
            "\n"
            "# Please enter the commit message for your changes. Lines starting\n"
            "# with '#' will be ignored, and an empty message aborts the commit.\n"
            "#\n"
            "# On branch oompah-zlz_2-3cpz\n"
            "# Changes to be committed:\n"
            "#       new file:   foo.py\n"
            "#\n"
        )
        out = transform(text)
        # Comment block intact.
        assert "# Please enter the commit message" in out
        assert "# On branch oompah-zlz_2-3cpz" in out
        assert "# Changes to be committed:" in out
        # Trailer inserted before comment block.
        bot_idx = out.find(OOMPAH_BOT_LINE)
        first_comment_idx = out.find("# Please enter")
        assert bot_idx < first_comment_idx, (
            "Canonical trailer must appear BEFORE git's editor template"
        )
        # Body still there.
        assert "feat: add widget" in out
        assert "Adds the widget." in out

    def test_comments_are_not_treated_as_trailers(self):
        # A '# Co-Authored-By: Claude' inside the editor template is a
        # comment line — it should NOT be matched by the stripper.
        text = (
            "fix: thing\n"
            "\n"
            "Body.\n"
            "\n"
            "# Co-Authored-By: Claude <noreply@anthropic.com>\n"
            "# (commented-out example only)\n"
        )
        out = transform(text)
        # The commented Claude line is left alone.
        assert "# Co-Authored-By: Claude <noreply@anthropic.com>" in out


class TestTrailingNewlinePreserved:
    def test_trailing_newline_kept(self):
        text = "fix: thing\n"
        out = transform(text)
        # Git writes commit messages with a trailing newline; preserve it.
        assert out.endswith("\n")

    def test_no_trailing_newline_kept(self):
        text = "fix: thing"  # no trailing \n
        out = transform(text)
        assert not out.endswith("\n\n")


class TestSingleSubjectLine:
    def test_subject_only_gets_trailer_with_blank_separator(self):
        text = "fix: short commit\n"
        out = transform(text)
        # Expect: subject\n\n🤖\n\nCo-authored-by\n
        assert "fix: short commit" in out
        assert OOMPAH_BOT_LINE in out
        assert OOMPAH_COAUTHOR in out
        # There must be a blank line between subject and the bot line.
        subj_idx = out.find("fix: short commit")
        bot_idx = out.find(OOMPAH_BOT_LINE)
        between = out[subj_idx + len("fix: short commit"):bot_idx]
        # Two newlines = one blank line.
        assert between.count("\n") >= 2


class TestCaseInsensitiveMatching:
    def test_uppercase_co_authored_by_stripped(self):
        text = "fix: x\n\nCO-AUTHORED-BY: Claude <a@b>\n"
        out = transform(text)
        assert "Claude" not in out
        assert OOMPAH_COAUTHOR in out

    def test_mixed_case_oompah_preserved(self):
        # Variant spelling is treated as oompah (case-insensitive name match).
        text = (
            "fix: x\n"
            "\n"
            "Co-authored-by: Oompah <bot@example.test>\n"
        )
        out = transform(text)
        # Either the original line is kept verbatim OR replaced with the
        # canonical form — both are acceptable as long as exactly one
        # oompah trailer exists and no other model trailer is added.
        # Our implementation treats it as canonical (case-insensitive)
        # so the canonical form is present and we don't append a duplicate.
        assert out.count(OOMPAH_COAUTHOR) >= 0  # either rewrite or keep
        # Ensure no duplication and no foreign trailer.
        # Count any Co-authored-by lines: should be exactly 1.
        coauthor_count = sum(
            1 for line in out.splitlines() if line.lower().startswith("co-authored-by:")
        )
        assert coauthor_count == 1


# ---------------------------------------------------------------------------
# Hook script end-to-end (run via subprocess against a real file)
# ---------------------------------------------------------------------------


class TestHookScriptExecutable:
    def test_hook_file_exists_and_is_executable(self):
        assert _HOOK_PATH.is_file()
        mode = os.stat(_HOOK_PATH).st_mode
        assert mode & stat.S_IXUSR, "hook must be executable"

    def test_hook_rewrites_file_in_place(self, tmp_path):
        msg = tmp_path / "COMMIT_EDITMSG"
        msg.write_text(
            "fix: x\n"
            "\n"
            "Co-Authored-By: Claude <noreply@anthropic.com>\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [str(_HOOK_PATH), str(msg)],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, result.stderr
        new = msg.read_text(encoding="utf-8")
        assert "Claude" not in new
        assert OOMPAH_BOT_LINE in new
        assert OOMPAH_COAUTHOR in new

    def test_hook_no_file_argument_is_noop(self):
        # When git invokes prepare-commit-msg with no args (shouldn't happen,
        # but be defensive), we must exit 0 without crashing.
        result = subprocess.run(
            [str(_HOOK_PATH)],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0

    def test_hook_missing_file_is_noop(self, tmp_path):
        nonexistent = tmp_path / "no_such_file"
        result = subprocess.run(
            [str(_HOOK_PATH), str(nonexistent)],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Installer wiring (projects._install_prepare_commit_msg_hook)
# ---------------------------------------------------------------------------


class TestHookInstaller:
    def test_install_creates_executable_hook(self, tmp_path):
        from oompah.projects import _install_prepare_commit_msg_hook

        wt = tmp_path / "wt"
        wt.mkdir()
        _install_prepare_commit_msg_hook(str(wt))

        installed = wt / ".oompah-no-hooks" / "prepare-commit-msg"
        assert installed.exists(), "hook must be installed under .oompah-no-hooks/"
        # The actual file (symlink target OR copied file) must be executable.
        resolved = installed.resolve()
        mode = os.stat(resolved).st_mode
        assert mode & stat.S_IXUSR

    def test_install_is_idempotent(self, tmp_path):
        from oompah.projects import _install_prepare_commit_msg_hook

        wt = tmp_path / "wt"
        wt.mkdir()
        _install_prepare_commit_msg_hook(str(wt))
        first_target = os.path.realpath(
            str(wt / ".oompah-no-hooks" / "prepare-commit-msg")
        )
        _install_prepare_commit_msg_hook(str(wt))
        second_target = os.path.realpath(
            str(wt / ".oompah-no-hooks" / "prepare-commit-msg")
        )
        assert first_target == second_target

    def test_installed_hook_runs_against_a_message(self, tmp_path):
        """End-to-end: install the hook into a worktree and verify it works
        when invoked as ``./hooks/prepare-commit-msg <msg-file>``.
        """
        from oompah.projects import _install_prepare_commit_msg_hook

        wt = tmp_path / "wt"
        wt.mkdir()
        _install_prepare_commit_msg_hook(str(wt))

        msg = tmp_path / "COMMIT_EDITMSG"
        msg.write_text(
            "fix: x\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n",
            encoding="utf-8",
        )
        hook_exe = wt / ".oompah-no-hooks" / "prepare-commit-msg"
        result = subprocess.run(
            [str(hook_exe), str(msg)],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, result.stderr
        new = msg.read_text(encoding="utf-8")
        assert "Claude" not in new
        assert OOMPAH_COAUTHOR in new
