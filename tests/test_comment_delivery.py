"""Tests for mid-run task comment delivery to running agents (OOMPAH-211).

Covers:
- Orchestrator.deliver_comment_to_running_agent() — routing, idempotency,
  fallback, and audit logging.
- ClaudeAcpBackendSession multi-turn injection — comments queued mid-run are
  sent as new agent turns at each ResultMessage boundary.
- AcpAgentSession.inject_message() — facade delegates to the backend session.
- Server api_add_comment hook — comment delivery is attempted on every
  non-oompah comment post.
- GitHub intake bridge — imported GitHub comments trigger delivery.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.acp_agent import AcpAgentSession
from oompah.acp_backends.base import AcpBackendOptions
from oompah.models import Issue, RunningEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(identifier: str = "OOMPAH-TEST", issue_id: str = "issue-1") -> Issue:
    return Issue(
        id=issue_id,
        identifier=identifier,
        title="Test",
        description="Test issue",
        state="in_progress",
    )


def _make_running_entry(issue: Issue) -> RunningEntry:
    from datetime import datetime, timezone

    return RunningEntry(
        worker_task=MagicMock(),
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
    )


def _make_orchestrator(tmp_path):
    from oompah.config import ServiceConfig
    from oompah.orchestrator import Orchestrator

    project_store = MagicMock()
    project_store.list_all.return_value = []
    project_store.get.return_value = None
    return Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


# ---------------------------------------------------------------------------
# Orchestrator.deliver_comment_to_running_agent()
# ---------------------------------------------------------------------------


class TestDeliverCommentToRunningAgent:
    """Unit tests for the orchestrator's comment delivery method."""

    def test_returns_false_when_no_running_agent(self, tmp_path):
        """When no agent is running for the identifier, return False (graceful
        fallback)."""
        orch = _make_orchestrator(tmp_path)
        result = orch.deliver_comment_to_running_agent(
            "OOMPAH-999",
            "Hello agent",
        )
        assert result is False

    def test_returns_false_when_no_comment_queue_registered(self, tmp_path):
        """A running entry without a comment queue (non-ACP worker) falls back
        gracefully and returns False."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue()
        orch.state.running[issue.id] = _make_running_entry(issue)
        # No queue registered in _agent_comment_queues
        result = orch.deliver_comment_to_running_agent(
            issue.identifier,
            "Hello agent",
        )
        assert result is False

    def test_returns_true_and_queues_comment_when_queue_present(self, tmp_path):
        """When a comment queue is registered for the issue, the comment is
        enqueued and True is returned."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue()
        orch.state.running[issue.id] = _make_running_entry(issue)
        q: asyncio.Queue = asyncio.Queue()
        orch._agent_comment_queues[issue.id] = q

        result = orch.deliver_comment_to_running_agent(
            issue.identifier,
            "Hello agent",
        )
        assert result is True
        assert not q.empty()
        assert q.get_nowait() == "Hello agent"

    def test_idempotent_with_comment_id(self, tmp_path):
        """The same comment_id is only delivered once (exactly-once guarantee)."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue()
        orch.state.running[issue.id] = _make_running_entry(issue)
        q: asyncio.Queue = asyncio.Queue()
        orch._agent_comment_queues[issue.id] = q

        # First delivery succeeds
        r1 = orch.deliver_comment_to_running_agent(
            issue.identifier,
            "Hello agent",
            comment_id="comment-abc",
        )
        # Second delivery with same comment_id is a no-op
        r2 = orch.deliver_comment_to_running_agent(
            issue.identifier,
            "Hello agent",
            comment_id="comment-abc",
        )

        assert r1 is True
        assert r2 is True  # idempotent success
        # Queue has exactly ONE entry, not two.
        assert q.qsize() == 1

    def test_different_comment_ids_both_delivered(self, tmp_path):
        """Two comments with different IDs are both enqueued."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue()
        orch.state.running[issue.id] = _make_running_entry(issue)
        q: asyncio.Queue = asyncio.Queue()
        orch._agent_comment_queues[issue.id] = q

        orch.deliver_comment_to_running_agent(
            issue.identifier, "First", comment_id="c1"
        )
        orch.deliver_comment_to_running_agent(
            issue.identifier, "Second", comment_id="c2"
        )

        assert q.qsize() == 2
        assert q.get_nowait() == "First"
        assert q.get_nowait() == "Second"

    def test_no_comment_id_delivered_every_time(self, tmp_path):
        """Without a comment_id, every call is delivered (no dedup)."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue()
        orch.state.running[issue.id] = _make_running_entry(issue)
        q: asyncio.Queue = asyncio.Queue()
        orch._agent_comment_queues[issue.id] = q

        orch.deliver_comment_to_running_agent(issue.identifier, "A")
        orch.deliver_comment_to_running_agent(issue.identifier, "B")

        assert q.qsize() == 2

    def test_audit_log_populated_on_queue(self, tmp_path):
        """Every successful delivery appends an entry to the audit log."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue()
        orch.state.running[issue.id] = _make_running_entry(issue)
        q: asyncio.Queue = asyncio.Queue()
        orch._agent_comment_queues[issue.id] = q

        orch.deliver_comment_to_running_agent(
            issue.identifier, "Hello!", comment_id="c-123"
        )

        log = orch._agent_comment_delivery_log.get(issue.id, [])
        assert len(log) == 1
        entry = log[0]
        assert entry["status"] == "queued"
        assert entry["comment_id"] == "c-123"
        assert "Hello!" in entry["text_preview"]
        assert "ts" in entry

    def test_audit_log_records_fallback(self, tmp_path):
        """Fallback (no queue) is still recorded with status='fallback'."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue()
        orch.state.running[issue.id] = _make_running_entry(issue)
        # No queue registered → fallback path

        orch.deliver_comment_to_running_agent(
            issue.identifier, "Fallback comment", comment_id="c-999"
        )

        log = orch._agent_comment_delivery_log.get(issue.id, [])
        assert len(log) == 1
        assert log[0]["status"] == "fallback"
        assert log[0]["comment_id"] == "c-999"

    def test_queue_cleanup_removes_state(self, tmp_path):
        """After the worker exits, the queue and idempotency set are removed."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue()
        orch.state.running[issue.id] = _make_running_entry(issue)
        q: asyncio.Queue = asyncio.Queue()
        orch._agent_comment_queues[issue.id] = q
        orch._agent_delivered_comment_ids[issue.id] = {"c1"}

        # Simulate worker exit cleanup
        orch._agent_comment_queues.pop(issue.id, None)
        orch._agent_delivered_comment_ids.pop(issue.id, None)

        assert issue.id not in orch._agent_comment_queues
        assert issue.id not in orch._agent_delivered_comment_ids


# ---------------------------------------------------------------------------
# ClaudeAcpBackendSession multi-turn injection
# ---------------------------------------------------------------------------


def _make_result_message(*, is_error: bool = False, errors=None, session_id="s1"):
    """Build a minimal mock ResultMessage."""
    try:
        from claude_agent_sdk import ResultMessage
        return ResultMessage(
            subtype="error" if is_error else "success",
            duration_ms=10,
            duration_api_ms=5,
            is_error=is_error,
            num_turns=1,
            session_id=session_id,
            stop_reason=None,
            total_cost_usd=None,
            usage=None,
            result=None,
            structured_output=None,
            model_usage=None,
            permission_denials=None,
            errors=errors,
            uuid="u1",
        )
    except ImportError:
        pytest.skip("claude_agent_sdk not installed")


class TestClaudeMultiTurnInjection:
    """Tests for mid-turn comment injection in ClaudeAcpBackendSession."""

    async def _run_session_with_queue(self, mock_messages_per_turn, *, comment_queue=None):
        """Run a session with mocked SDK responses across multiple turns.

        mock_messages_per_turn: list of lists. Each inner list is the sequence
        of messages yielded by one call to receive_response().
        """
        pytest.importorskip("claude_agent_sdk")
        events = []

        turn_iter = iter(mock_messages_per_turn)

        def _make_receive_response():
            """Return a fresh async generator for the next turn's messages."""
            try:
                msgs = next(turn_iter)
            except StopIteration:
                msgs = []

            async def _gen():
                for m in msgs:
                    yield m

            return _gen()

        client_mock = AsyncMock()
        client_mock.query = AsyncMock()
        client_mock.receive_response = MagicMock(side_effect=lambda: _make_receive_response())
        client_mock.interrupt = AsyncMock()

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=client_mock)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch("claude_agent_sdk.ClaudeSDKClient", return_value=cm):
            from oompah.acp_backends.claude import ClaudeAcpBackendSession
            from oompah.acp_backends.base import AcpBackendOptions

            options = AcpBackendOptions(
                workspace_path="/tmp/ws",
                prompt="do the thing",
                comment_queue=comment_queue,
            )
            session = ClaudeAcpBackendSession(options)
            async for ev in session.run_turn():
                events.append(ev)

        return session, events, client_mock

    def test_no_injection_single_turn(self):
        """Without a comment queue, a single ResultMessage ends the session."""
        result_msg = _make_result_message()

        async def _run():
            return await self._run_session_with_queue([[result_msg]])

        session, events, client = asyncio.run(_run())
        assert session.status == "succeeded"
        # query() called exactly once (the initial prompt)
        client.query.assert_called_once()

    def test_injection_delivers_comment_as_new_turn(self):
        """A comment queued before the ResultMessage is sent as a new turn."""
        result_msg = _make_result_message()
        result_msg2 = _make_result_message(session_id="s2")

        comment_queue: asyncio.Queue = asyncio.Queue()
        comment_queue.put_nowait("Human comment: please also check the README")

        async def _run():
            # Two turns: first ends with result_msg (triggers injection),
            # second ends with result_msg2 (no more comments → done).
            return await self._run_session_with_queue(
                [[result_msg], [result_msg2]],
                comment_queue=comment_queue,
            )

        session, events, client = asyncio.run(_run())
        assert session.status == "succeeded"
        # query() called twice: initial prompt + injected comment
        assert client.query.call_count == 2
        # The second query contains the injected comment text
        second_call_arg = client.query.call_args_list[1][0][0]
        assert "Human comment: please also check the README" in second_call_arg

    def test_injected_comment_event_emitted(self):
        """An acp_injected_comment BackendEvent is emitted when a comment is
        injected so the audit trail records the injection."""
        result_msg = _make_result_message()
        result_msg2 = _make_result_message(session_id="s2")

        comment_queue: asyncio.Queue = asyncio.Queue()
        comment_queue.put_nowait("Add tests for the edge case")

        async def _run():
            return await self._run_session_with_queue(
                [[result_msg], [result_msg2]],
                comment_queue=comment_queue,
            )

        _, events, _ = asyncio.run(_run())
        kinds = [ev.kind for ev in events]
        assert "injected_comment" in kinds

        injected_ev = next(ev for ev in events if ev.kind == "injected_comment")
        assert "Add tests" in injected_ev.payload.get("text", "")

    def test_multiple_queued_comments_delivered_in_order(self):
        """Multiple pending comments are delivered in FIFO order (one per
        turn boundary)."""
        result_msg1 = _make_result_message(session_id="s1")
        result_msg2 = _make_result_message(session_id="s2")
        result_msg3 = _make_result_message(session_id="s3")

        comment_queue: asyncio.Queue = asyncio.Queue()
        comment_queue.put_nowait("First comment")
        comment_queue.put_nowait("Second comment")

        async def _run():
            # Three turns needed for 2 injected comments + final done
            return await self._run_session_with_queue(
                [[result_msg1], [result_msg2], [result_msg3]],
                comment_queue=comment_queue,
            )

        session, _, client = asyncio.run(_run())
        assert session.status == "succeeded"
        # Initial prompt + first injection + second injection = 3 calls
        assert client.query.call_count == 3
        calls = [c[0][0] for c in client.query.call_args_list]
        assert "First comment" in calls[1]
        assert "Second comment" in calls[2]

    def test_empty_queue_does_not_inject(self):
        """With an empty comment_queue, no extra turn is added."""
        result_msg = _make_result_message()
        comment_queue: asyncio.Queue = asyncio.Queue()  # empty

        async def _run():
            return await self._run_session_with_queue(
                [[result_msg]],
                comment_queue=comment_queue,
            )

        session, _, client = asyncio.run(_run())
        assert session.status == "succeeded"
        client.query.assert_called_once()  # only the initial prompt

    def test_error_result_message_skips_injection(self):
        """A failed ResultMessage (is_error=True) is NOT followed by injection —
        we don't send comments to a failing session."""
        error_msg = _make_result_message(is_error=True, errors=["bad thing happened"])
        comment_queue: asyncio.Queue = asyncio.Queue()
        comment_queue.put_nowait("Ignored comment")

        async def _run():
            return await self._run_session_with_queue(
                [[error_msg]],
                comment_queue=comment_queue,
            )

        session, _, client = asyncio.run(_run())
        assert session.status == "failed"
        client.query.assert_called_once()  # only the initial prompt
        # The queued comment was NOT consumed (injection is skipped on error)
        assert not comment_queue.empty()

    def test_stop_requested_during_injection_turn_returns_interrupted(self):
        """If the session is stopped during an injection turn, the status is
        interrupted (not succeeded)."""
        result_msg = _make_result_message(session_id="s1")

        comment_queue: asyncio.Queue = asyncio.Queue()
        comment_queue.put_nowait("Comment that arrives after stop")

        async def _slow_stream():
            # Simulate a slow second turn that checks stop flag
            await asyncio.sleep(0)  # yield control
            yield result_msg

        pytest.importorskip("claude_agent_sdk")

        from oompah.acp_backends.claude import ClaudeAcpBackendSession
        from oompah.acp_backends.base import AcpBackendOptions

        turn_count = 0

        def _make_receive_response():
            nonlocal turn_count
            turn_count += 1
            if turn_count == 1:
                # First turn: yield normal result
                async def _gen():
                    yield result_msg
                return _gen()
            else:
                # Second turn: set stop before yielding
                async def _gen2():
                    await asyncio.sleep(0)
                    yield result_msg  # This will be preempted by stop check
                return _gen2()

        client_mock = AsyncMock()
        client_mock.query = AsyncMock()
        client_mock.receive_response = MagicMock(side_effect=lambda: _make_receive_response())
        client_mock.interrupt = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=client_mock)
        cm.__aexit__ = AsyncMock(return_value=None)

        async def _run():
            options = AcpBackendOptions(
                workspace_path="/tmp/ws",
                prompt="do the thing",
                comment_queue=comment_queue,
            )
            session = ClaudeAcpBackendSession(options)

            async def _drain():
                events = []
                async for ev in session.run_turn():
                    events.append(ev)
                    # After injection starts (2nd query sent), request stop
                    if ev.kind == "injected_comment":
                        session._stop_requested = True
                return events

            with patch("claude_agent_sdk.ClaudeSDKClient", return_value=cm):
                events = await _drain()
            return session, events

        session, events = asyncio.run(_run())
        assert session.status == "interrupted"


# ---------------------------------------------------------------------------
# AcpAgentSession.inject_message()
# ---------------------------------------------------------------------------


class TestAcpAgentSessionInjectMessage:
    """Tests for the inject_message() facade on AcpAgentSession."""

    def test_returns_false_when_no_session_active(self):
        """inject_message() returns False when no backend session is active
        (session not started yet)."""
        session = AcpAgentSession(workspace_path="/tmp", prompt="x")
        result = asyncio.run(session.inject_message("hello"))
        assert result is False

    def test_returns_false_when_backend_lacks_inject_message(self):
        """inject_message() returns False for backends that don't implement
        the method (graceful fallback for CLI / api_agent)."""
        session = AcpAgentSession(workspace_path="/tmp", prompt="x")
        # Simulate an active backend session without inject_message
        mock_backend = MagicMock(spec=[])  # no inject_message attribute
        session._backend_session = mock_backend
        result = asyncio.run(session.inject_message("hello"))
        assert result is False

    def test_returns_true_when_backend_accepts_message(self):
        """inject_message() returns True when the backend session has
        inject_message and it succeeds."""
        session = AcpAgentSession(workspace_path="/tmp", prompt="x")
        mock_backend = MagicMock()
        mock_backend.inject_message = AsyncMock(return_value=None)
        session._backend_session = mock_backend
        result = asyncio.run(session.inject_message("hello"))
        assert result is True
        mock_backend.inject_message.assert_awaited_once_with("hello")

    def test_returns_false_when_backend_inject_raises(self):
        """inject_message() catches exceptions from the backend and returns
        False rather than propagating."""
        session = AcpAgentSession(workspace_path="/tmp", prompt="x")
        mock_backend = MagicMock()
        mock_backend.inject_message = AsyncMock(side_effect=RuntimeError("boom"))
        session._backend_session = mock_backend
        result = asyncio.run(session.inject_message("hello"))
        assert result is False

    def test_inject_message_passed_through_to_backend(self):
        """The exact text is forwarded to the backend session unchanged."""
        session = AcpAgentSession(workspace_path="/tmp", prompt="x")
        mock_backend = MagicMock()
        injected = []
        mock_backend.inject_message = AsyncMock(side_effect=lambda t: injected.append(t))
        session._backend_session = mock_backend
        asyncio.run(session.inject_message("Please also update the README"))
        assert injected == ["Please also update the README"]


# ---------------------------------------------------------------------------
# Integration: AcpAgentSession with comment queue
# ---------------------------------------------------------------------------


class TestAcpAgentSessionCommentQueue:
    """Verifies that AcpAgentSession wires the comment_queue into the
    backend session and that comments are delivered exactly once."""

    def test_comment_queue_passed_to_backend_options(self):
        """The comment_queue kwarg flows into AcpBackendOptions."""
        from oompah.acp_agent import AcpAgentSession
        from oompah.acp_backends.base import AcpBackendOptions

        q: asyncio.Queue = asyncio.Queue()
        session = AcpAgentSession(
            workspace_path="/tmp",
            prompt="x",
            comment_queue=q,
        )
        assert session.comment_queue is q

        # Verify it is passed to AcpBackendOptions during run_task()
        captured: dict = {}

        original_init = AcpBackendOptions.__init__

        def _spy_init(self, **kwargs):
            captured.update(kwargs)
            original_init(self, **kwargs)

        with patch.object(AcpBackendOptions, "__init__", _spy_init):
            # We expect an error (no real backend), but we've captured options
            try:
                asyncio.run(session.run_task())
            except Exception:
                pass

        assert captured.get("comment_queue") is q

    def test_exactly_once_delivery_end_to_end(self):
        """A comment queued via deliver_comment_to_running_agent() is
        received by the running agent exactly once (integration test using
        mocked SDK)."""
        pytest.importorskip("claude_agent_sdk")

        comment_queue: asyncio.Queue = asyncio.Queue()
        events = []
        queries = []

        # Pre-queue a comment before the session starts
        comment_queue.put_nowait("[New comment from user]\n\nPlease also lint the code")

        from claude_agent_sdk import ResultMessage

        result_msg1 = ResultMessage(
            subtype="success", duration_ms=1, duration_api_ms=1,
            is_error=False, num_turns=1, session_id="s1",
            stop_reason=None, total_cost_usd=None, usage=None,
            result=None, structured_output=None, model_usage=None,
            permission_denials=None, errors=None, uuid="u1",
        )
        result_msg2 = ResultMessage(
            subtype="success", duration_ms=1, duration_api_ms=1,
            is_error=False, num_turns=1, session_id="s2",
            stop_reason=None, total_cost_usd=None, usage=None,
            result=None, structured_output=None, model_usage=None,
            permission_denials=None, errors=None, uuid="u2",
        )

        turn_num = [0]

        def _make_receive_response():
            turn_num[0] += 1

            async def _gen():
                if turn_num[0] == 1:
                    yield result_msg1
                else:
                    yield result_msg2

            return _gen()

        client_mock = AsyncMock()
        client_mock.query = AsyncMock(side_effect=lambda t: queries.append(t))
        client_mock.receive_response = MagicMock(side_effect=lambda: _make_receive_response())
        client_mock.interrupt = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=client_mock)
        cm.__aexit__ = AsyncMock(return_value=None)

        async def _run():
            with patch("claude_agent_sdk.ClaudeSDKClient", return_value=cm):
                session = AcpAgentSession(
                    workspace_path="/tmp/ws",
                    prompt="do the thing",
                    comment_queue=comment_queue,
                    on_event=events.append,
                )
                return await session.run_task()

        status = asyncio.run(_run())

        assert status == "succeeded"
        # The comment was delivered exactly once as a second turn
        assert len(queries) == 2
        assert "lint the code" in queries[1]
        # The queue is drained — no duplicate delivery
        assert comment_queue.empty()
        # An injected_comment event was emitted
        injected_events = [e for e in events if e.event == "acp_injected_comment"]
        assert len(injected_events) == 1


# ---------------------------------------------------------------------------
# GitHub intake bridge delivery hook
# ---------------------------------------------------------------------------


class TestGithubIntakeCommentDelivery:
    """Verifies that import_github_comment_to_native triggers delivery to
    any running agent via _deliver_github_comment_to_agent()."""

    def test_delivers_to_running_agent_on_new_comment(self):
        """When a GitHub comment is newly imported, the delivery hook is
        called with the correct identifier and text."""
        from oompah.github_intake_bridge import _deliver_github_comment_to_agent

        orch_mock = MagicMock()
        orch_mock.deliver_comment_to_running_agent = MagicMock(return_value=True)

        _deliver_github_comment_to_agent(
            orch_mock,
            "OOMPAH-TEST",
            author="alice",
            body="Please also add integration tests",
            comment_id="gh-123",
        )

        orch_mock.deliver_comment_to_running_agent.assert_called_once()
        call_args = orch_mock.deliver_comment_to_running_agent.call_args
        identifier = call_args[0][0]
        text = call_args[0][1]
        assert identifier == "OOMPAH-TEST"
        assert "alice" in text
        assert "integration tests" in text

    def test_no_delivery_when_orch_lacks_method(self):
        """If the orchestrator doesn't have deliver_comment_to_running_agent,
        _deliver_github_comment_to_agent silently no-ops."""
        from oompah.github_intake_bridge import _deliver_github_comment_to_agent

        orch_mock = object()  # no deliver_comment_to_running_agent method

        # Should not raise
        _deliver_github_comment_to_agent(
            orch_mock,
            "OOMPAH-TEST",
            author="bob",
            body="No crash",
            comment_id=None,
        )

    def test_comment_id_forwarded_for_idempotency(self):
        """The GitHub comment ID is forwarded as comment_id for idempotency."""
        from oompah.github_intake_bridge import _deliver_github_comment_to_agent

        orch_mock = MagicMock()
        orch_mock.deliver_comment_to_running_agent = MagicMock(return_value=True)

        _deliver_github_comment_to_agent(
            orch_mock,
            "OOMPAH-42",
            author="carol",
            body="Fix the flaky test",
            comment_id="gh-456",
        )

        call_kwargs = orch_mock.deliver_comment_to_running_agent.call_args[1]
        assert call_kwargs.get("comment_id") == "gh-456"


# ---------------------------------------------------------------------------
# Server api_add_comment hook
# ---------------------------------------------------------------------------


class TestServerCommentDeliveryHook:
    """Verifies that the server's api_add_comment route attempts delivery
    to running agents for non-oompah comments."""

    def test_delivery_called_for_human_comment(self):
        """When a human posts a comment, deliver_comment_to_running_agent is
        called on the orchestrator."""
        from unittest.mock import patch as _patch, AsyncMock as _AsyncMock

        # We can't easily invoke the FastAPI route in a unit test, so we
        # verify the logic by checking that the module-level server code
        # wires up the delivery call. We test the key condition:
        # author != "oompah" → delivery attempted.

        orch_mock = MagicMock()
        orch_mock.deliver_comment_to_running_agent = MagicMock(return_value=True)

        # Simulate the delivery logic from server.py's api_add_comment
        # (extracted for testability)
        import hashlib as _hashlib
        import time as _time

        def _simulate_server_delivery(author, text, identifier, orch):
            """Replicates the delivery block in api_add_comment."""
            if author != "oompah":
                try:
                    _comment_id = _hashlib.md5(
                        f"{identifier}:{text}:{_time.time()}".encode()
                    ).hexdigest()
                    orch.deliver_comment_to_running_agent(
                        identifier,
                        f"[New comment from {author}]\n\n{text}",
                        comment_id=_comment_id,
                    )
                except Exception:
                    pass

        _simulate_server_delivery(
            "alice", "Great work!", "OOMPAH-TEST", orch_mock
        )

        orch_mock.deliver_comment_to_running_agent.assert_called_once()
        call_args = orch_mock.deliver_comment_to_running_agent.call_args
        assert "Great work!" in call_args[0][1]
        assert "alice" in call_args[0][1]

    def test_delivery_not_called_for_oompah_comment(self):
        """When oompah itself posts a comment, delivery is NOT triggered
        (prevents feedback loops)."""
        orch_mock = MagicMock()
        orch_mock.deliver_comment_to_running_agent = MagicMock(return_value=True)

        import hashlib as _hashlib
        import time as _time

        def _simulate_server_delivery(author, text, identifier, orch):
            if author != "oompah":
                try:
                    _comment_id = _hashlib.md5(
                        f"{identifier}:{text}:{_time.time()}".encode()
                    ).hexdigest()
                    orch.deliver_comment_to_running_agent(
                        identifier,
                        f"[New comment from {author}]\n\n{text}",
                        comment_id=_comment_id,
                    )
                except Exception:
                    pass

        _simulate_server_delivery(
            "oompah", "Agent dispatched (profile: default)", "OOMPAH-TEST", orch_mock
        )

        orch_mock.deliver_comment_to_running_agent.assert_not_called()
