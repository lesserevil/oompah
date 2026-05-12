"""Tests for oompah.issue_enhancer (oompah-zlz_2-u8pz).

The module is a pure function: it loads AGENTS.md or a WORKFLOW.md
issue.quality block from the workspace, builds a chat-completions
prompt, calls the provider via _http_post, parses the JSON response,
and returns an :class:`EnhancementResult`. These tests exercise each
piece in isolation plus an end-to-end happy path with a stub
_http_post.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from oompah.issue_enhancer import (
    EnhancementResult,
    IssueEnhancerError,
    _build_messages,
    _strip_code_fence,
    build_unified_diff,
    enhance_issue,
    extract_issue_quality_section,
    has_quality_source,
    load_quality_source,
    parse_llm_response,
    read_agents_md,
    read_workflow_issue_quality,
)


# ---------------------------------------------------------------------------
# Quality-source loading
# ---------------------------------------------------------------------------


class TestReadAgentsMd:
    def test_empty_repo_path_returns_empty(self):
        assert read_agents_md(None) == ""
        assert read_agents_md("") == ""

    def test_missing_file_returns_empty(self, tmp_path):
        assert read_agents_md(str(tmp_path)) == ""

    def test_reads_agents_md(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# Quality rules\n- every issue needs AC\n")
        assert "Quality rules" in read_agents_md(str(tmp_path))

    def test_reads_lowercase_agents_md(self, tmp_path):
        (tmp_path / "agents.md").write_text("# lowercase\n")
        # On case-insensitive filesystems both candidates point to the
        # same file; on Linux only the lowercase one matches. Either
        # way the helper returns the body.
        assert "lowercase" in read_agents_md(str(tmp_path))

    def test_handles_read_error_gracefully(self, tmp_path):
        path = tmp_path / "AGENTS.md"
        path.write_text("ok")
        with patch("builtins.open", side_effect=OSError("boom")):
            assert read_agents_md(str(tmp_path)) == ""


class TestExtractIssueQualitySection:
    def test_returns_empty_when_header_missing(self):
        assert extract_issue_quality_section("# Other heading\n- thing\n") == ""

    def test_extracts_section_with_dot_form(self):
        text = "# Top\n\n## issue.quality\n\n- need AC\n- need repro\n\n## next\nbody"
        out = extract_issue_quality_section(text)
        assert "need AC" in out and "need repro" in out
        assert "next" not in out

    def test_extracts_section_with_space_form(self):
        text = "## Issue Quality\nrules here\n"
        out = extract_issue_quality_section(text)
        assert "rules here" in out

    def test_extracts_to_eof_when_no_following_header(self):
        text = "# Issue Quality\nlast section, no heading after"
        out = extract_issue_quality_section(text)
        assert "last section" in out


class TestReadWorkflowIssueQuality:
    def test_empty_repo_path(self):
        assert read_workflow_issue_quality(None) == ""

    def test_missing_workflow_md(self, tmp_path):
        assert read_workflow_issue_quality(str(tmp_path)) == ""

    def test_extracts_block(self, tmp_path):
        (tmp_path / "WORKFLOW.md").write_text(
            "# Header\n\n## issue.quality\n\nrequirements\n\n## next\n"
        )
        out = read_workflow_issue_quality(str(tmp_path))
        assert "requirements" in out


class TestLoadQualitySource:
    def test_no_source_returns_empty(self, tmp_path):
        assert load_quality_source(str(tmp_path)) == ("", "")

    def test_agents_md_wins(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("agents body")
        (tmp_path / "WORKFLOW.md").write_text("## issue.quality\nworkflow body\n")
        kind, body = load_quality_source(str(tmp_path))
        assert kind == "agents_md"
        assert "agents body" in body

    def test_workflow_quality_fallback(self, tmp_path):
        (tmp_path / "WORKFLOW.md").write_text("## issue.quality\nworkflow body\n")
        kind, body = load_quality_source(str(tmp_path))
        assert kind == "workflow_quality"
        assert "workflow body" in body


class TestHasQualitySource:
    def test_none_path(self):
        assert has_quality_source(None) is False

    def test_no_files(self, tmp_path):
        assert has_quality_source(str(tmp_path)) is False

    def test_agents_md_present(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("x")
        assert has_quality_source(str(tmp_path)) is True

    def test_workflow_md_without_block(self, tmp_path):
        (tmp_path / "WORKFLOW.md").write_text("# unrelated\nbody")
        assert has_quality_source(str(tmp_path)) is False

    def test_workflow_md_with_block(self, tmp_path):
        (tmp_path / "WORKFLOW.md").write_text("## issue.quality\nrules")
        assert has_quality_source(str(tmp_path)) is True


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


class TestBuildMessages:
    def test_returns_two_messages(self):
        msgs = _build_messages("t", "d", "rules")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_system_contains_quality_source(self):
        msgs = _build_messages("t", "d", "MY-RULES-MARKER")
        assert "MY-RULES-MARKER" in msgs[0]["content"]

    def test_system_requests_json_output(self):
        msgs = _build_messages("t", "d", "x")
        assert "JSON" in msgs[0]["content"]
        assert "title" in msgs[0]["content"]
        assert "description" in msgs[0]["content"]
        assert "missing_fields" in msgs[0]["content"]

    def test_user_contains_title_and_description(self):
        msgs = _build_messages("Fix login", "When I log in...", "x")
        assert "Fix login" in msgs[1]["content"]
        assert "When I log in..." in msgs[1]["content"]

    def test_user_handles_empty_description(self):
        msgs = _build_messages("t", "", "x")
        assert "no description" in msgs[1]["content"].lower()


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


class TestStripCodeFence:
    def test_no_fence_passthrough(self):
        assert _strip_code_fence("plain") == "plain"

    def test_strips_json_fence(self):
        s = "```json\n{\"a\": 1}\n```"
        assert _strip_code_fence(s) == '{"a": 1}'

    def test_strips_bare_fence(self):
        s = "```\nhello\n```"
        assert _strip_code_fence(s) == "hello"


class TestParseLlmResponse:
    def test_happy_path(self):
        body = json.dumps({
            "title": "Enhanced title",
            "description": "Enhanced body\n## Acceptance criteria\n- x",
            "missing_fields": ["repro steps"],
            "suggested_changes": "Added AC.",
        })
        out = parse_llm_response(body)
        assert out["title"] == "Enhanced title"
        assert "Enhanced body" in out["description"]
        assert out["missing_fields"] == ["repro steps"]
        assert out["suggested_changes"] == "Added AC."

    def test_handles_fenced_response(self):
        body = "```json\n" + json.dumps({"title": "t", "description": "d"}) + "\n```"
        out = parse_llm_response(body)
        assert out["title"] == "t"

    def test_rejects_empty_response(self):
        with pytest.raises(IssueEnhancerError):
            parse_llm_response("")

    def test_rejects_non_json(self):
        with pytest.raises(IssueEnhancerError):
            parse_llm_response("not json")

    def test_rejects_non_object(self):
        with pytest.raises(IssueEnhancerError):
            parse_llm_response('["a", "b"]')

    def test_rejects_missing_title(self):
        with pytest.raises(IssueEnhancerError):
            parse_llm_response(json.dumps({"description": "d"}))

    def test_rejects_blank_title(self):
        with pytest.raises(IssueEnhancerError):
            parse_llm_response(json.dumps({"title": "   ", "description": "d"}))

    def test_rejects_missing_description(self):
        with pytest.raises(IssueEnhancerError):
            parse_llm_response(json.dumps({"title": "t"}))

    def test_defaults_missing_fields_to_empty(self):
        out = parse_llm_response(json.dumps({"title": "t", "description": "d"}))
        assert out["missing_fields"] == []
        assert out["suggested_changes"] == ""


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


class TestBuildUnifiedDiff:
    def test_identical_returns_empty(self):
        assert build_unified_diff("a", "a") == ""

    def test_returns_unified_diff(self):
        d = build_unified_diff("old\n", "new\n")
        assert "old" in d
        assert "new" in d
        assert "---" in d
        assert "+++" in d


# ---------------------------------------------------------------------------
# enhance_issue end-to-end
# ---------------------------------------------------------------------------


def _make_provider(api_key="sk-test", base_url="https://api.example.com"):
    p = MagicMock()
    p.api_key = api_key
    p.base_url = base_url
    return p


def _make_response(title="Enhanced", description="Enhanced body", missing=None, suggested=""):
    payload = {
        "title": title,
        "description": description,
        "missing_fields": missing or [],
        "suggested_changes": suggested,
    }
    return {
        "choices": [{"message": {"content": json.dumps(payload)}}],
    }


class TestEnhanceIssue:
    def test_happy_path(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# Project rules\n- need AC\n")
        provider = _make_provider()
        with patch(
            "oompah.api_agent._http_post",
            return_value=_make_response(title="Better title", description="Better body", suggested="expanded"),
        ):
            result = enhance_issue(
                title="fix the thing",
                description="thing is broken",
                repo_path=str(tmp_path),
                provider=provider,
                model="gpt-4o-mini",
            )
        assert isinstance(result, EnhancementResult)
        assert result.original_title == "fix the thing"
        assert result.original_description == "thing is broken"
        assert result.enhanced_title == "Better title"
        assert result.enhanced_description == "Better body"
        assert result.suggested_changes == "expanded"
        # Diff was built since description changed
        assert result.diff

    def test_rejects_empty_title(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("rules")
        with pytest.raises(IssueEnhancerError, match="non-empty"):
            enhance_issue(
                title="   ",
                description="x",
                repo_path=str(tmp_path),
                provider=_make_provider(),
                model="m",
            )

    def test_rejects_when_no_quality_source(self, tmp_path):
        with pytest.raises(IssueEnhancerError, match="No quality source"):
            enhance_issue(
                title="t",
                description=None,
                repo_path=str(tmp_path),
                provider=_make_provider(),
                model="m",
            )

    def test_rejects_when_no_provider(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("rules")
        with pytest.raises(IssueEnhancerError, match="provider"):
            enhance_issue(
                title="t",
                description=None,
                repo_path=str(tmp_path),
                provider=None,
                model="m",
            )

    def test_rejects_when_no_model(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("rules")
        with pytest.raises(IssueEnhancerError, match="model"):
            enhance_issue(
                title="t",
                description=None,
                repo_path=str(tmp_path),
                provider=_make_provider(),
                model="",
            )

    def test_rejects_when_provider_has_no_base_url(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("rules")
        provider = _make_provider(base_url="")
        with pytest.raises(IssueEnhancerError, match="base_url"):
            enhance_issue(
                title="t",
                description=None,
                repo_path=str(tmp_path),
                provider=provider,
                model="m",
            )

    def test_http_failure_propagates_as_enhancer_error(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("rules")
        with patch("oompah.api_agent._http_post", side_effect=RuntimeError("boom")):
            with pytest.raises(IssueEnhancerError, match="LLM call failed"):
                enhance_issue(
                    title="t",
                    description="d",
                    repo_path=str(tmp_path),
                    provider=_make_provider(),
                    model="m",
                )

    def test_malformed_response_propagates(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("rules")
        with patch(
            "oompah.api_agent._http_post",
            return_value={"choices": []},  # missing message
        ):
            with pytest.raises(IssueEnhancerError, match="unexpected"):
                enhance_issue(
                    title="t",
                    description="d",
                    repo_path=str(tmp_path),
                    provider=_make_provider(),
                    model="m",
                )

    def test_uses_workflow_quality_when_no_agents_md(self, tmp_path):
        (tmp_path / "WORKFLOW.md").write_text("## issue.quality\nrules-from-workflow\n")
        captured_messages = {}

        def fake_post(url, headers, body, ssl_ctx):
            captured_messages["body"] = json.loads(body.decode("utf-8"))
            return _make_response()

        with patch("oompah.api_agent._http_post", side_effect=fake_post):
            enhance_issue(
                title="t",
                description="d",
                repo_path=str(tmp_path),
                provider=_make_provider(),
                model="m",
            )
        system_msg = captured_messages["body"]["messages"][0]["content"]
        assert "rules-from-workflow" in system_msg

    def test_sends_bearer_token_and_url(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("rules")
        seen = {}

        def fake_post(url, headers, body, ssl_ctx):
            seen["url"] = url
            seen["headers"] = headers
            seen["body"] = json.loads(body.decode("utf-8"))
            return _make_response()

        with patch("oompah.api_agent._http_post", side_effect=fake_post):
            enhance_issue(
                title="t",
                description="d",
                repo_path=str(tmp_path),
                provider=_make_provider(api_key="sk-XYZ", base_url="https://api.example.com/"),
                model="gpt-test",
            )
        assert seen["url"] == "https://api.example.com/chat/completions"
        assert seen["headers"]["Authorization"] == "Bearer sk-XYZ"
        assert seen["body"]["model"] == "gpt-test"
        # Temperature pinned for deterministic re-runs.
        assert seen["body"]["temperature"] == 0.0


class TestEnhancementResultToDict:
    def test_to_dict_shape(self):
        r = EnhancementResult(
            original_title="o",
            original_description="od",
            enhanced_title="e",
            enhanced_description="ed",
            missing_fields=["a"],
            suggested_changes="s",
            diff="-o\n+e",
        )
        d = r.to_dict()
        assert d["original"]["title"] == "o"
        assert d["original"]["description"] == "od"
        assert d["enhanced"]["title"] == "e"
        assert d["enhanced"]["description"] == "ed"
        assert d["missing_fields"] == ["a"]
        assert d["suggested_changes"] == "s"
        assert d["diff"] == "-o\n+e"
