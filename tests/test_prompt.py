"""Tests for oompah.prompt."""

import pytest

from oompah.models import Issue
from oompah.prompt import PromptError, build_continuation_prompt, render_prompt


def _make_issue(**kwargs):
    defaults = dict(id="1", identifier="beads-001", title="Fix the bug", state="open")
    defaults.update(kwargs)
    return Issue(**defaults)


class TestRenderPrompt:
    def test_basic_render(self):
        issue = _make_issue()
        template = "Working on {{ issue.identifier }}: {{ issue.title }}"
        result = render_prompt(template, issue)
        assert "beads-001" in result
        assert "Fix the bug" in result

    def test_empty_template_fallback(self):
        issue = _make_issue()
        result = render_prompt("  ", issue)
        assert "beads-001" in result
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
        assert "beads-001" in result
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
