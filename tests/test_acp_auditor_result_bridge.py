"""Regression coverage for ACP completion-auditor result submission."""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import types
from collections.abc import Callable
from typing import Any

import pytest

from oompah.auditor import (
    AUDITOR_RESULT_TOOL_NAME,
    AuditorTargetContract,
)
from oompah.authority_boundary import auditor_policy


def _target() -> AuditorTargetContract:
    return AuditorTargetContract(
        audit_id="audit-612",
        task_id="TASK-612",
        project_id="project-612",
        target_state="Done",
        evidence_fingerprint="6" * 64,
        attempt_id="attempt-612",
        previous_state="In Validation",
    )


def _payload() -> dict[str, Any]:
    target = _target()
    return {
        "audit_id": target.audit_id,
        "target_state": target.target_state,
        "evidence_fingerprint": target.evidence_fingerprint,
        "verdict": "pass",
        "message": "The requested completion evidence passed.",
        "attempt_id": target.attempt_id,
    }


async def _exercise_same_loop_bridge(
    build_catalog: Callable[..., list[Any]],
) -> tuple[dict[str, Any], dict[str, Any], int, set[int], int]:
    """Run the production sync bridge from an async ACP tool."""

    loop = asyncio.get_running_loop()
    loop_thread = threading.get_ident()
    applied_attempts: set[str] = set()
    applied_count = 0
    handler_threads: set[int] = set()

    async def apply_result(result: Any) -> dict[str, Any]:
        nonlocal applied_count
        await asyncio.sleep(0)
        idempotent = result.attempt_id in applied_attempts
        if not idempotent:
            applied_attempts.add(result.attempt_id)
            applied_count += 1
        return {
            "accepted": True,
            "audit_id": result.audit_id,
            "applied_status": "Done",
            "idempotent": idempotent,
        }

    def sync_handler(result: Any) -> dict[str, Any]:
        handler_threads.add(threading.get_ident())
        future = asyncio.run_coroutine_threadsafe(apply_result(result), loop)
        return future.result(timeout=2)

    target = _target()
    catalog = build_catalog(
        ".",
        project_id=target.project_id,
        auditor=True,
        action_policy=auditor_policy(
            task_identifier=target.task_id,
            project_id=target.project_id,
        ),
        audit_target=target,
        audit_result_handler=sync_handler,
    )
    tool = next(item for item in catalog if item.name == AUDITOR_RESULT_TOOL_NAME)

    first = await asyncio.wait_for(
        tool.handler(_payload()),
        timeout=5,
    )
    second = await asyncio.wait_for(
        tool.handler(_payload()),
        timeout=5,
    )

    first_payload = json.loads(first["content"][0]["text"])
    second_payload = json.loads(second["content"][0]["text"])
    return (
        first_payload,
        second_payload,
        applied_count,
        handler_threads,
        loop_thread,
    )


def test_claude_acp_submission_does_not_block_its_dispatch_loop() -> None:
    pytest.importorskip("claude_agent_sdk")
    from oompah.acp_tools import build_tool_catalog

    first, second, applied_count, handler_threads, loop_thread = asyncio.run(
        _exercise_same_loop_bridge(build_tool_catalog)
    )

    assert first == {
        "accepted": True,
        "audit_id": "audit-612",
        "applied_status": "Done",
        "idempotent": False,
    }
    assert second["accepted"] is True
    assert second["idempotent"] is True
    assert applied_count == 1
    assert handler_threads
    assert loop_thread not in handler_threads


def test_opencode_acp_submission_does_not_block_its_dispatch_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def tool(name: str, _description: str, _schema: dict[str, Any]):
        def decorate(handler: Callable[..., Any]) -> Any:
            return types.SimpleNamespace(name=name, handler=handler)

        return decorate

    monkeypatch.setitem(sys.modules, "opencode", types.SimpleNamespace(tool=tool))

    from oompah.acp_tools import build_opencode_tool_catalog

    first, second, applied_count, handler_threads, loop_thread = asyncio.run(
        _exercise_same_loop_bridge(build_opencode_tool_catalog)
    )

    assert first["accepted"] is True
    assert second["idempotent"] is True
    assert applied_count == 1
    assert handler_threads
    assert loop_thread not in handler_threads


def test_claude_acp_submission_surfaces_coordinator_rejection() -> None:
    pytest.importorskip("claude_agent_sdk")
    from oompah.acp_tools import build_tool_catalog

    async def run() -> tuple[str, int]:
        loop = asyncio.get_running_loop()
        calls = 0

        async def reject_result(_result: Any) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0)
            return {"accepted": False, "reason": "stale target"}

        def sync_handler(result: Any) -> dict[str, Any]:
            future = asyncio.run_coroutine_threadsafe(reject_result(result), loop)
            return future.result(timeout=2)

        target = _target()
        catalog = build_tool_catalog(
            ".",
            project_id=target.project_id,
            auditor=True,
            action_policy=auditor_policy(
                task_identifier=target.task_id,
                project_id=target.project_id,
            ),
            audit_target=target,
            audit_result_handler=sync_handler,
        )
        tool = next(
            item for item in catalog if item.name == AUDITOR_RESULT_TOOL_NAME
        )
        result = await asyncio.wait_for(
            tool.handler(_payload()),
            timeout=5,
        )
        return result["content"][0]["text"], calls

    text, calls = asyncio.run(run())

    assert text == "Error: audit scheduler rejected result"
    assert calls == 1
