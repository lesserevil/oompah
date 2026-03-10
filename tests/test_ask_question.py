"""Tests for the ask_question feature (oompah-055).

Tests cover:
1. api_agent.py — ask_question tool definition and execution in the agent loop
2. orchestrator.py — dispatch guard for 'asking_question' label + ask_question exit handling
3. server.py — automatic removal of 'asking_question' label when user posts comment
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.api_agent import (
    TOOL_DEFINITIONS,
    ApiAgentResult,
    ApiAgentSession,
    _TOOL_REQUIRED_ARGS,
)
from oompah.config import ServiceConfig
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config() -> ServiceConfig:
    """Create a minimal ServiceConfig for testing."""
    return ServiceConfig()


def _make_issue(
    issue_id: str = "test-001",
    identifier: str = "test-001",
    title: str = "Test issue",
    state: str = "open",
    labels: list[str] | None = None,
    priority: int = 2,
    issue_type: str = "task",
) -> Issue:
    return Issue(
        id=issue_id,
        identifier=identifier,
        title=title,
        state=state,
        labels=labels or [],
        priority=priority,
        issue_type=issue_type,
    )


@pytest.fixture
def event_loop():
    """Provide an event loop for tests that use asyncio."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(None)


# ---------------------------------------------------------------------------
# 1. api_agent.py — tool definition
# ---------------------------------------------------------------------------


class TestAskQuestionToolDefinition:
    """Verify ask_question is properly defined in TOOL_DEFINITIONS."""

    def test_ask_question_in_tool_definitions(self):
        """The ask_question tool must appear in TOOL_DEFINITIONS."""
        tool_names = [
            t["function"]["name"]
            for t in TOOL_DEFINITIONS
            if t.get("type") == "function"
        ]
        assert "ask_question" in tool_names

    def test_ask_question_has_required_question_param(self):
        """The ask_question tool must require a 'question' parameter."""
        tool = None
        for t in TOOL_DEFINITIONS:
            if t.get("type") == "function" and t["function"]["name"] == "ask_question":
                tool = t
                break
        assert tool is not None
        params = tool["function"]["parameters"]
        assert "question" in params["properties"]
        assert "question" in params["required"]

    def test_ask_question_in_required_args(self):
        """ask_question must be listed in _TOOL_REQUIRED_ARGS."""
        assert "ask_question" in _TOOL_REQUIRED_ARGS
        assert "question" in _TOOL_REQUIRED_ARGS["ask_question"]


# ---------------------------------------------------------------------------
# 2. api_agent.py — ask_question in agent loop
# ---------------------------------------------------------------------------


class TestAskQuestionAgentLoop:
    """Verify the agent loop handles ask_question tool calls correctly."""

    def test_ask_question_returns_ask_question_status(self):
        """When the model calls ask_question, run_task should return status='ask_question'."""
        session = ApiAgentSession(
            base_url="http://fake.test",
            api_key="fake-key",
            model="test-model",
            workspace_path="/tmp/test-workspace",
            max_turns=10,
        )

        mock_response = {
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "ask_question",
                                    "arguments": json.dumps({
                                        "question": "What database should I use?"
                                    }),
                                },
                            }
                        ],
                    },
                }
            ],
        }

        async def _run():
            with patch.object(session, "_call_api", new_callable=AsyncMock) as mock_api:
                mock_api.return_value = mock_response
                return await session.run_task("Test prompt")

        result = asyncio.run(_run())

        assert result.status == "ask_question"
        assert result.question == "What database should I use?"
        assert result.last_message == "What database should I use?"
        assert result.turns == 1

    def test_ask_question_empty_question_continues(self):
        """If ask_question is called with empty question, it should error and continue."""
        session = ApiAgentSession(
            base_url="http://fake.test",
            api_key="fake-key",
            model="test-model",
            workspace_path="/tmp/test-workspace",
            max_turns=2,
        )

        # First call: ask_question with empty question (should error and continue)
        response_1 = {
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "ask_question",
                                    "arguments": json.dumps({"question": ""}),
                                },
                            }
                        ],
                    },
                }
            ],
        }
        # Second call: model finishes normally
        response_2 = {
            "usage": {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300},
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "Done!",
                    },
                }
            ],
        }

        async def _run():
            with patch.object(session, "_call_api", new_callable=AsyncMock) as mock_api:
                mock_api.side_effect = [response_1, response_2]
                return await session.run_task("Test prompt")

        result = asyncio.run(_run())
        assert result.status == "succeeded"
        assert result.question is None


# ---------------------------------------------------------------------------
# 3. orchestrator.py — dispatch guard for asking_question label
# ---------------------------------------------------------------------------


class TestDispatchGuardAskingQuestion:
    """Issues with 'asking_question' label must NOT be dispatched."""

    def test_should_dispatch_rejects_asking_question(self, tmp_path):
        """_should_dispatch returns False for issues with 'asking_question' label."""
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=str(tmp_path / "state.json"),
        )
        issue = _make_issue(labels=["asking_question"])
        assert orch._should_dispatch(issue) is False

    def test_should_dispatch_accepts_normal_issue(self, tmp_path):
        """_should_dispatch returns True for issues without 'asking_question' label."""
        config = _make_config()
        config.budget_limit = 0  # disable budget check
        orch = Orchestrator(
            config=config,
            workflow_path="WORKFLOW.md",
            state_path=str(tmp_path / "state.json"),
        )
        issue = _make_issue(labels=["feature"])
        result = orch._should_dispatch(issue)
        assert result is True

    def test_should_dispatch_rejects_asking_question_with_other_labels(self, tmp_path):
        """Issues with asking_question among other labels are still rejected."""
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=str(tmp_path / "state.json"),
        )
        issue = _make_issue(labels=["feature", "asking_question", "urgent"])
        assert orch._should_dispatch(issue) is False


# ---------------------------------------------------------------------------
# 4. orchestrator.py — _on_worker_exit with ask_question reason
# ---------------------------------------------------------------------------


class TestOrchestratorAskQuestionExit:
    """Verify _on_worker_exit handles 'ask_question' exit reason correctly."""

    def test_ask_question_exit_posts_comment_and_labels(self, tmp_path, event_loop):
        """When exit reason is 'ask_question', orchestrator should post comment,
        add label, and move issue to open."""
        config = _make_config()
        orch = Orchestrator(
            config=config,
            workflow_path="WORKFLOW.md",
            state_path=str(tmp_path / "state.json"),
        )

        issue = _make_issue()
        issue_id = issue.id

        mock_tracker = MagicMock()
        orch.tracker = mock_tracker

        orch.state.running[issue_id] = RunningEntry(
            worker_task=None,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="standard",
        )
        orch.state.claimed.add(issue_id)

        event_loop.run_until_complete(
            orch._on_worker_exit(issue_id, "ask_question", "What database should I use?")
        )

        # Verify: comment was posted with the question
        mock_tracker.add_comment.assert_called_once()
        comment_args = mock_tracker.add_comment.call_args
        assert issue.identifier in comment_args[0]
        assert "What database should I use?" in comment_args[0][1]

        # Verify: issue was moved to open with label added atomically
        mock_tracker.update_issue.assert_called_once_with(
            issue.identifier, status="open", **{"add-label": "asking_question"}
        )

        # Verify: issue_id removed from running and claimed
        assert issue_id not in orch.state.running
        assert issue_id not in orch.state.claimed

        # Verify: NOT in retry queue
        assert issue_id not in orch.state.retry_attempts

    def test_ask_question_exit_not_marked_completed(self, tmp_path, event_loop):
        """ask_question should NOT mark the issue as completed."""
        config = _make_config()
        orch = Orchestrator(
            config=config,
            workflow_path="WORKFLOW.md",
            state_path=str(tmp_path / "state.json"),
        )

        issue = _make_issue()
        mock_tracker = MagicMock()
        orch.tracker = mock_tracker

        orch.state.running[issue.id] = RunningEntry(
            worker_task=None,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
        )

        event_loop.run_until_complete(
            orch._on_worker_exit(issue.id, "ask_question", "A question")
        )

        assert issue.id not in orch.state.completed

    def test_ask_question_exit_clears_stall_count(self, tmp_path, event_loop):
        """ask_question should clear the stall count for the issue."""
        config = _make_config()
        orch = Orchestrator(
            config=config,
            workflow_path="WORKFLOW.md",
            state_path=str(tmp_path / "state.json"),
        )

        issue = _make_issue()
        mock_tracker = MagicMock()
        orch.tracker = mock_tracker

        orch.state.stall_counts[issue.id] = 3
        orch.state.running[issue.id] = RunningEntry(
            worker_task=None,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
        )

        event_loop.run_until_complete(
            orch._on_worker_exit(issue.id, "ask_question", "Question?")
        )

        assert issue.id not in orch.state.stall_counts


# ---------------------------------------------------------------------------
# 5. server.py — asking_question label removal on user comment
# ---------------------------------------------------------------------------


class TestServerAskingQuestionLabelRemoval:
    """When a user (non-oompah) posts a comment on an issue with the
    'asking_question' label, the label should be automatically removed."""

    def test_user_comment_removes_asking_question_label(self):
        """Posting a comment as a user removes the asking_question label."""
        from fastapi.testclient import TestClient
        from oompah.server import app
        import oompah.server as server_mod

        mock_tracker = MagicMock()
        mock_issue = _make_issue(labels=["asking_question"])
        mock_tracker.fetch_issue_detail.return_value = mock_issue
        mock_tracker.add_comment.return_value = {"id": 1, "text": "answer"}

        mock_orch = MagicMock()
        mock_orch._tracker_for_project.return_value = mock_tracker
        mock_orch.get_snapshot.return_value = {"counts": {}, "running": [], "retrying": []}

        original_orch = server_mod._orchestrator
        server_mod._orchestrator = mock_orch

        try:
            client = TestClient(app)
            response = client.post(
                "/api/v1/issues/test-001/comments",
                json={
                    "text": "Use PostgreSQL",
                    "author": "user",
                    "project_id": "proj-1",
                },
            )
            assert response.status_code == 201
            mock_tracker.remove_label.assert_called_once_with("test-001", "asking_question")
        finally:
            server_mod._orchestrator = original_orch

    def test_oompah_comment_does_not_remove_label(self):
        """Posting a comment as 'oompah' should NOT remove the asking_question label."""
        from fastapi.testclient import TestClient
        from oompah.server import app
        import oompah.server as server_mod

        mock_tracker = MagicMock()
        mock_issue = _make_issue(labels=["asking_question"])
        mock_tracker.fetch_issue_detail.return_value = mock_issue
        mock_tracker.add_comment.return_value = {"id": 1, "text": "internal note"}

        mock_orch = MagicMock()
        mock_orch._tracker_for_project.return_value = mock_tracker

        original_orch = server_mod._orchestrator
        server_mod._orchestrator = mock_orch

        try:
            client = TestClient(app)
            response = client.post(
                "/api/v1/issues/test-001/comments",
                json={
                    "text": "Agent note",
                    "author": "oompah",
                    "project_id": "proj-1",
                },
            )
            assert response.status_code == 201
            mock_tracker.remove_label.assert_not_called()
        finally:
            server_mod._orchestrator = original_orch

    def test_user_comment_no_label_no_removal(self):
        """If the issue doesn't have asking_question label, no removal should happen."""
        from fastapi.testclient import TestClient
        from oompah.server import app
        import oompah.server as server_mod

        mock_tracker = MagicMock()
        mock_issue = _make_issue(labels=["feature"])
        mock_tracker.fetch_issue_detail.return_value = mock_issue
        mock_tracker.add_comment.return_value = {"id": 1, "text": "just a comment"}

        mock_orch = MagicMock()
        mock_orch._tracker_for_project.return_value = mock_tracker

        original_orch = server_mod._orchestrator
        server_mod._orchestrator = mock_orch

        try:
            client = TestClient(app)
            response = client.post(
                "/api/v1/issues/test-001/comments",
                json={
                    "text": "A regular comment",
                    "author": "user",
                    "project_id": "proj-1",
                },
            )
            assert response.status_code == 201
            mock_tracker.remove_label.assert_not_called()
        finally:
            server_mod._orchestrator = original_orch

    def test_user_comment_default_author_removes_label(self):
        """Default author is 'user', which should trigger label removal."""
        from fastapi.testclient import TestClient
        from oompah.server import app
        import oompah.server as server_mod

        mock_tracker = MagicMock()
        mock_issue = _make_issue(labels=["asking_question"])
        mock_tracker.fetch_issue_detail.return_value = mock_issue
        mock_tracker.add_comment.return_value = {"id": 1, "text": "answer"}

        mock_orch = MagicMock()
        mock_orch._tracker_for_project.return_value = mock_tracker
        mock_orch.get_snapshot.return_value = {"counts": {}, "running": [], "retrying": []}

        original_orch = server_mod._orchestrator
        server_mod._orchestrator = mock_orch

        try:
            client = TestClient(app)
            # No author specified — defaults to "user"
            response = client.post(
                "/api/v1/issues/test-001/comments",
                json={
                    "text": "Here is my answer",
                    "project_id": "proj-1",
                },
            )
            assert response.status_code == 201
            mock_tracker.remove_label.assert_called_once_with("test-001", "asking_question")
        finally:
            server_mod._orchestrator = original_orch


# ---------------------------------------------------------------------------
# 6. Integration: ApiAgentResult with ask_question status
# ---------------------------------------------------------------------------


class TestAskQuestionApiAgentResult:
    """Test the ApiAgentResult dataclass for ask_question status."""

    def test_result_has_question_field(self):
        """ApiAgentResult should support the question field."""
        result = ApiAgentResult(
            status="ask_question",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            turns=3,
            last_message="What framework?",
            question="What framework?",
        )
        assert result.status == "ask_question"
        assert result.question == "What framework?"

    def test_result_question_none_by_default(self):
        """question field should be None by default."""
        result = ApiAgentResult(
            status="succeeded",
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            turns=1,
            last_message="Done",
        )
        assert result.question is None
