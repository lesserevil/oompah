"""Tests for oompah.prompt."""

import pytest

from oompah.models import Issue
from oompah.prompt import PromptError, build_continuation_prompt, render_prompt


def _make_issue(**kwargs):
    defaults = dict(id="1", identifier="tasks-001", title="Fix the bug", state="open")
    defaults.update(kwargs)
    return Issue(**defaults)


class TestRenderPrompt:
    def test_basic_render(self):
        issue = _make_issue()
        template = "Working on {{ issue.identifier }}: {{ issue.title }}"
        result = render_prompt(template, issue)
        assert "tasks-001" in result
        assert "Fix the bug" in result

    def test_empty_template_fallback(self):
        issue = _make_issue()
        result = render_prompt("  ", issue)
        assert "tasks-001" in result
        assert "Fix the bug" in result

    def test_with_attempt(self):
        issue = _make_issue()
        template = "{% if attempt %}Attempt #{{ attempt }}{% endif %}"
        result = render_prompt(template, issue, attempt=3)
        assert "Attempt #3" in result

    def test_without_attempt(self):
        issue = _make_issue()
        template = "{% if attempt %}Attempt #{{ attempt }}{% else %}First run{% endif %}"
        result = render_prompt(template, issue, attempt=None)
        assert "First run" in result

    def test_with_comments(self):
        issue = _make_issue()
        template = "{% for c in comments %}- {{ c.author }}: {{ c.text }}\n{% endfor %}"
        comments = [
            {"author": "alice", "text": "found the bug", "created_at": "2025-01-01"},
        ]
        result = render_prompt(template, issue, comments=comments)
        assert "alice" in result
        assert "found the bug" in result

    def test_with_focus(self):
        issue = _make_issue()
        template = "{% if focus != blank %}{{ focus }}{% endif %}"
        result = render_prompt(template, issue, focus_text="## Your Role: Bug Fixer")
        assert "Bug Fixer" in result

    def test_issue_labels(self):
        issue = _make_issue(labels=["urgent", "backend"])
        template = "Labels: {{ issue.labels | join: ', ' }}"
        result = render_prompt(template, issue)
        assert "urgent" in result
        assert "backend" in result

    def test_invalid_template(self):
        issue = _make_issue()
        with pytest.raises(PromptError):
            render_prompt("{% invalid liquid %}", issue)


class TestBuildContinuationPrompt:
    def test_contains_info(self):
        issue = _make_issue()
        result = build_continuation_prompt(issue, 5, 20)
        assert "tasks-001" in result
        assert "turn 5" in result
        assert "20" in result
        assert "open" in result


# ---------------------------------------------------------------------------
# RenderedPrompt + multimodal content (oompah-zlz.4)
# ---------------------------------------------------------------------------

import os as _os

from oompah.prompt import RenderedPrompt


def _png_bytes(n: int = 64) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * max(0, n - 8)


class TestRenderedPromptLegacy:
    def test_no_attachments_arg_returns_string(self):
        # Backward-compat: if attachments is not passed, return a plain str.
        out = render_prompt("Hi {{ issue.identifier }}", _make_issue(identifier="x"))
        assert isinstance(out, str)
        assert "Hi x" in out

    def test_explicit_empty_attachments_returns_rendered_prompt(self):
        out = render_prompt(
            "Hi {{ issue.identifier }}", _make_issue(identifier="x"),
            attachments=[], capabilities=["text"],
        )
        assert isinstance(out, RenderedPrompt)
        assert out.parts is None  # no embeds
        assert "Hi x" in out.text


class TestRenderedPromptMultimodal:
    def test_image_embedded_when_capability_supports_it(self, tmp_path):
        # Lay out an attachment under .oompah/attachments/.
        adir = tmp_path / ".oompah" / "attachments" / "foo-1"
        adir.mkdir(parents=True)
        png = adir / "abc-shot.png"
        png.write_bytes(_png_bytes(100))
        rel = ".oompah/attachments/foo-1/abc-shot.png"

        out = render_prompt(
            "Hi {{ issue.identifier }}", _make_issue(identifier="foo-1"),
            attachments=[rel],
            capabilities=["text", "image"],
            project_root=str(tmp_path),
        )
        assert isinstance(out, RenderedPrompt)
        assert out.parts is not None
        assert out.parts[0]["type"] == "text"
        # Embedded image part with a data URL.
        img_part = out.parts[1]
        assert img_part["type"] == "image_url"
        assert img_part["image_url"]["url"].startswith("data:image/png;base64,")
        # No "not sent" note for an embedded image.
        assert "not sent" not in out.text

    def test_image_falls_back_to_text_only_when_no_image_cap(self, tmp_path):
        adir = tmp_path / ".oompah" / "attachments" / "foo-1"
        adir.mkdir(parents=True)
        png = adir / "abc-shot.png"
        png.write_bytes(_png_bytes(100))
        rel = ".oompah/attachments/foo-1/abc-shot.png"

        out = render_prompt(
            "Hi {{ issue.identifier }}", _make_issue(identifier="foo-1"),
            attachments=[rel],
            capabilities=["text"],
            project_root=str(tmp_path),
        )
        assert isinstance(out, RenderedPrompt)
        assert out.parts is None
        assert "not sent" in out.text
        assert rel in out.text

    def test_audio_uses_input_audio_part(self, tmp_path):
        adir = tmp_path / ".oompah" / "attachments" / "foo-1"
        adir.mkdir(parents=True)
        wav = adir / "abc-clip.wav"
        wav.write_bytes(b"RIFF" + b"\x00" * 100)
        rel = ".oompah/attachments/foo-1/abc-clip.wav"

        out = render_prompt(
            "Hi", _make_issue(identifier="foo-1"),
            attachments=[rel],
            capabilities=["text", "audio"],
            project_root=str(tmp_path),
        )
        assert out.parts is not None
        assert out.parts[1]["type"] == "input_audio"
        assert out.parts[1]["input_audio"]["format"] == "wav"

    def test_oversize_attachment_is_text_only(self, tmp_path, monkeypatch):
        # Tighten cap so a small file overflows.
        monkeypatch.setattr("oompah.prompt._PER_ATTACHMENT_BYTE_CAP", 50)
        adir = tmp_path / ".oompah" / "attachments" / "foo-1"
        adir.mkdir(parents=True)
        png = adir / "x.png"
        png.write_bytes(_png_bytes(200))
        rel = ".oompah/attachments/foo-1/x.png"

        out = render_prompt(
            "Hi", _make_issue(identifier="foo-1"),
            attachments=[rel],
            capabilities=["text", "image"],
            project_root=str(tmp_path),
        )
        assert out.parts is None
        assert "exceeds per-attachment cap" in out.text

    def test_per_prompt_cap_elides_overflow(self, tmp_path, monkeypatch):
        # First attachment fits; second pushes us over the prompt cap.
        monkeypatch.setattr("oompah.prompt._PER_PROMPT_BYTE_CAP", 150)
        adir = tmp_path / ".oompah" / "attachments" / "foo-1"
        adir.mkdir(parents=True)
        a = adir / "a.png"
        b = adir / "b.png"
        a.write_bytes(_png_bytes(100))
        b.write_bytes(_png_bytes(100))

        out = render_prompt(
            "Hi", _make_issue(identifier="foo-1"),
            attachments=[
                ".oompah/attachments/foo-1/a.png",
                ".oompah/attachments/foo-1/b.png",
            ],
            capabilities=["text", "image"],
            project_root=str(tmp_path),
        )
        # First one was embedded, second one elided.
        assert out.parts is not None
        assert len(out.parts) == 2  # text + a.png only
        assert ".oompah/attachments/foo-1/b.png" in out.elided
        assert "elided to fit prompt size cap" in out.text

    def test_missing_file_falls_back_to_text(self, tmp_path):
        rel = ".oompah/attachments/foo-1/missing.png"
        out = render_prompt(
            "Hi", _make_issue(identifier="foo-1"),
            attachments=[rel],
            capabilities=["text", "image"],
            project_root=str(tmp_path),
        )
        assert out.parts is None
        assert "not found" in out.text


class TestAttachmentsExposedToTemplate:
    def test_template_can_iterate_attachments(self, tmp_path):
        adir = tmp_path / ".oompah" / "attachments" / "foo-1"
        adir.mkdir(parents=True)
        (adir / "abc-shot.png").write_bytes(_png_bytes(64))
        out = render_prompt(
            "Files: {% for a in attachments %}{{ a.path }}({{ a.embedded }}){% endfor %}",
            _make_issue(identifier="foo-1"),
            attachments=[".oompah/attachments/foo-1/abc-shot.png"],
            capabilities=["text", "image"],
            project_root=str(tmp_path),
        )
        assert ".oompah/attachments/foo-1/abc-shot.png(true)" in out.text


# ---------------------------------------------------------------------------
# Phase 2 integration: capability fallback end-to-end (oompah-zlz.7)
# ---------------------------------------------------------------------------


class TestCapabilityFallbackIntegration:
    """End-to-end check that an issue with image attachments behaves
    correctly under both text-only and multimodal models."""

    def _setup(self, tmp_path):
        adir = tmp_path / ".oompah" / "attachments" / "foo-1"
        adir.mkdir(parents=True)
        (adir / "abc-shot.png").write_bytes(_png_bytes(100))
        (adir / "def-mock.png").write_bytes(_png_bytes(80))
        return [
            ".oompah/attachments/foo-1/abc-shot.png",
            ".oompah/attachments/foo-1/def-mock.png",
        ]

    def test_text_only_model_lists_paths_with_not_sent_notes(self, tmp_path):
        paths = self._setup(tmp_path)
        out = render_prompt(
            "Issue: {{ issue.identifier }}",
            _make_issue(identifier="foo-1"),
            attachments=paths,
            capabilities=["text"],
            project_root=str(tmp_path),
        )
        # No content array — pure text.
        assert out.parts is None
        # Both paths show up in the body with the "not sent" reason.
        for p in paths:
            assert p in out.text
        assert "not sent: model lacks image" in out.text
        # No API failure path is exercised here — the renderer is the
        # boundary, and it succeeded with a string-shaped prompt.

    def test_multimodal_model_embeds_each_attachment(self, tmp_path):
        paths = self._setup(tmp_path)
        out = render_prompt(
            "Issue: {{ issue.identifier }}",
            _make_issue(identifier="foo-1"),
            attachments=paths,
            capabilities=["text", "image"],
            project_root=str(tmp_path),
        )
        assert out.parts is not None
        # First part is text, then one image_url per attachment.
        types = [p["type"] for p in out.parts]
        assert types == ["text", "image_url", "image_url"]
        assert all(
            p["image_url"]["url"].startswith("data:image/png;base64,")
            for p in out.parts[1:]
        )
        # No "not sent" note when everything embedded.
        assert "not sent" not in out.text


class TestRenderPromptProjectArg:
    """Tests for render_prompt(project=) and the project.* template var."""

    def _make_project(self, **kwargs):
        from oompah.models import Project
        defaults = dict(id="p", name="myproj", repo_url="u",
                        repo_path="/tmp/x", branch="main")
        defaults.update(kwargs)
        return Project(**defaults)

    def test_template_sees_project_test_command(self):
        issue = _make_issue()
        project = self._make_project(test_command="cargo test --workspace --lib")
        template = "cmd={{ project.test_command }} name={{ project.name }}"
        out = render_prompt(template, issue, project=project)
        assert "cmd=cargo test --workspace --lib" in out
        assert "name=myproj" in out

    def test_template_test_command_empty_when_unset(self):
        issue = _make_issue()
        project = self._make_project()
        template = "cmd=[{{ project.test_command }}]"
        out = render_prompt(template, issue, project=project)
        assert "cmd=[]" in out

    def test_template_when_no_project_arg(self):
        """Without a project arg, project.* still resolves to empty values."""
        issue = _make_issue()
        template = "cmd=[{{ project.test_command }}] name=[{{ project.name }}]"
        out = render_prompt(template, issue)
        assert "cmd=[]" in out
        assert "name=[]" in out

    def test_workflow_template_test_command_block(self):
        """Mimics the WORKFLOW.md conditional block to ensure the template
        includes the project.test_command when set."""
        issue = _make_issue()
        project = self._make_project(test_command="make test")
        template = (
            '{% if project.test_command != "" %}'
            'CMD: `{{ project.test_command }}`'
            '{% endif %}'
        )
        out = render_prompt(template, issue, project=project)
        assert "CMD: `make test`" in out

    def test_workflow_template_test_command_block_omitted(self):
        issue = _make_issue()
        project = self._make_project()  # no test_command
        template = (
            '{% if project.test_command != "" %}'
            'CMD: `{{ project.test_command }}`'
            '{% endif %}'
            'tail'
        )
        out = render_prompt(template, issue, project=project)
        assert "CMD" not in out
        assert "tail" in out

    def test_test_skip_paths_iterable_in_template(self):
        issue = _make_issue()
        project = self._make_project(
            test_skip_paths=["tests/hw/*", "tests/integration/*"],
        )
        template = "skip:{% for p in project.test_skip_paths %}[{{ p }}]{% endfor %}"
        out = render_prompt(template, issue, project=project)
        assert "skip:[tests/hw/*][tests/integration/*]" in out


# ---------------------------------------------------------------------------
# Tracker identity template vars (TASK-460.2)
# ---------------------------------------------------------------------------


class TestTrackerIdentityTemplateVars:
    """Tests for tracker_kind / provider_url / display_identifier / project_id
    being exposed to Liquid templates."""

    def test_tracker_kind_empty_when_not_set(self):
        issue = _make_issue()  # no tracker_kind set
        template = "kind=[{{ issue.tracker_kind }}]"
        out = render_prompt(template, issue)
        assert "kind=[]" in out

    def test_tracker_kind_github_issues(self):
        issue = _make_issue(tracker_kind="github_issues")
        template = "kind=[{{ issue.tracker_kind }}]"
        out = render_prompt(template, issue)
        assert "kind=[github_issues]" in out

    def test_provider_url_exposed(self):
        issue = _make_issue(provider_url="https://github.com/owner/repo/issues/42")
        template = "url=[{{ issue.provider_url }}]"
        out = render_prompt(template, issue)
        assert "url=[https://github.com/owner/repo/issues/42]" in out

    def test_provider_url_empty_when_none(self):
        issue = _make_issue()  # no provider_url
        template = "url=[{{ issue.provider_url }}]"
        out = render_prompt(template, issue)
        assert "url=[]" in out

    def test_display_identifier_exposed(self):
        issue = _make_issue(display_identifier="#42")
        template = "disp=[{{ issue.display_identifier }}]"
        out = render_prompt(template, issue)
        assert "disp=[#42]" in out

    def test_project_id_exposed(self):
        issue = _make_issue(project_id="proj-abc")
        template = "proj=[{{ issue.project_id }}]"
        out = render_prompt(template, issue)
        assert "proj=[proj-abc]" in out

    def test_project_id_empty_when_none(self):
        issue = _make_issue()  # no project_id
        template = "proj=[{{ issue.project_id }}]"
        out = render_prompt(template, issue)
        assert "proj=[]" in out


class TestTrackerSpecificConditionalRendering:
    """Verify WORKFLOW.md-style conditional blocks render correctly for
    each supported tracker kind."""

    # Minimal mock of the WORKFLOW.md conditional quick-reference section.
    _TRACKER_SECTION_TEMPLATE = """\
## oompah Task Reference
view: `oompah task view {{ issue.identifier }}`
comment: `oompah task comment {{ issue.identifier }} --message "..." --author oompah`
create: `oompah task create --project {{ issue.project_id }} --title "..."`
close: `oompah task set-status {{ issue.identifier }} Done --summary "..."`
{% if issue.provider_url != "" %}GitHub Issue: {{ issue.provider_url }}{% endif %}
"""

    def test_github_backed_shows_oompah_commands(self):
        issue = _make_issue(
            identifier="owner/repo#42",
            tracker_kind="github_issues",
            project_id="proj-gh",
            provider_url="https://github.com/owner/repo/issues/42",
        )
        out = render_prompt(self._TRACKER_SECTION_TEMPLATE, issue)
        # oompah commands present
        assert "oompah task view" in out
        assert "oompah task comment" in out
        assert "oompah task create --project proj-gh" in out
        assert "oompah task set-status" in out
        assert "GitHub Issue: https://github.com/owner/repo/issues/42" in out

    def test_native_oompah_markdown_shows_oompah_commands(self):
        issue = _make_issue(
            identifier="OVA-12",
            tracker_kind="oompah_md",
            project_id="proj-ova",
        )
        out = render_prompt(self._TRACKER_SECTION_TEMPLATE, issue)
        assert "oompah task view OVA-12" in out
        assert "oompah task comment OVA-12" in out
        assert "oompah task create --project proj-ova" in out
        assert "oompah task set-status OVA-12" in out

    def test_github_backed_omits_provider_url_when_empty(self):
        issue = _make_issue(
            identifier="owner/repo#5",
            tracker_kind="github_issues",
            project_id="p",
            provider_url=None,  # no URL available
        )
        out = render_prompt(self._TRACKER_SECTION_TEMPLATE, issue)
        assert "oompah task view" in out
        assert "GitHub Issue:" not in out

    def test_workflow_md_renders_for_github_issue(self):
        """End-to-end: the actual WORKFLOW.md template renders without error
        for a GitHub-backed issue and includes oompah commands."""
        import os
        workflow_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "WORKFLOW.md"
        )
        if not os.path.isfile(workflow_path):
            pytest.skip("WORKFLOW.md not found")
        with open(workflow_path) as f:
            raw = f.read()
        # Strip YAML front-matter (--- ... ---) to get the Liquid template body.
        parts = raw.split("---", 2)
        template_source = parts[2].strip() if len(parts) == 3 else raw

        issue = _make_issue(
            identifier="owner/repo#99",
            title="My GitHub issue",
            tracker_kind="github_issues",
            project_id="proj-x",
            provider_url="https://github.com/owner/repo/issues/99",
            branch_name="TASK-99",
        )
        out = render_prompt(template_source, issue)
        assert isinstance(out, str)
        # Should include GitHub section headers and oompah commands
        assert "oompah Task Reference" in out
        assert "oompah task view" in out
        assert "oompah task set-status" in out

    def test_workflow_md_renders_for_native_oompah_markdown_issue(self):
        """End-to-end: native Markdown tracker tasks use oompah task commands."""
        import os
        workflow_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "WORKFLOW.md"
        )
        if not os.path.isfile(workflow_path):
            pytest.skip("WORKFLOW.md not found")
        with open(workflow_path) as f:
            raw = f.read()
        parts = raw.split("---", 2)
        template_source = parts[2].strip() if len(parts) == 3 else raw

        issue = _make_issue(
            identifier="OVA-12",
            title="Native Markdown issue",
            tracker_kind="oompah_md",
            project_id="proj-ova",
            branch_name="OVA-12",
        )
        out = render_prompt(template_source, issue)
        assert isinstance(out, str)
        assert "oompah Task Reference" in out
        assert "oompah task view OVA-12" in out
        assert "oompah task set-status OVA-12" in out


class TestSourceMetadataInFollowUpCommands:
    """Verify that WORKFLOW.md follow-up task examples include source metadata
    for supported tracker kinds."""

    def _load_workflow_template(self) -> str:
        import os
        workflow_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "WORKFLOW.md"
        )
        if not os.path.isfile(workflow_path):
            pytest.skip("WORKFLOW.md not found")
        with open(workflow_path) as f:
            raw = f.read()
        parts = raw.split("---", 2)
        return parts[2].strip() if len(parts) == 3 else raw

    def test_github_follow_up_includes_source_flag(self):
        """GitHub-backed: 'oompah task create' follow-up includes --source flag."""
        template_source = self._load_workflow_template()
        issue = _make_issue(
            identifier="owner/repo#123",
            tracker_kind="github_issues",
            project_id="proj-src",
            branch_name="gh-123",
        )
        out = render_prompt(template_source, issue)
        # The follow-up task line should include --source with the issue identifier
        assert "--source owner/repo#123" in out

    def test_github_follow_up_uses_source_flag(self):
        """GitHub-backed rendered follow-up uses structured source metadata."""
        template_source = self._load_workflow_template()
        issue = _make_issue(
            identifier="owner/repo#99",
            tracker_kind="github_issues",
            project_id="proj-gh",
            branch_name="gh-99",
        )
        out = render_prompt(template_source, issue)
        # Free-form source prose should not replace structured source metadata.
        assert "Follow-up from owner/repo#99" not in out
        # But the oompah --source pattern should appear
        assert "--source owner/repo#99" in out
