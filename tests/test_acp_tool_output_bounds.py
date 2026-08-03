"""Regression coverage for transport-safe ACP tool results (OOMPAH-710)."""

from __future__ import annotations

import asyncio
import re

from oompah.api_agent import (
    CommandOutputStore,
    _exec_read_command_output,
    _exec_read_file,
    _exec_run_command,
    _exec_search_files,
)
from oompah.auditor import AuditorTargetContract
from oompah.authority_boundary import auditor_policy


def test_large_read_file_is_chunked_before_provider_transport(tmp_path) -> None:
    content = "0123456789" * 150_000
    (tmp_path / "large.txt").write_text(content, encoding="utf-8")

    first = _exec_read_file(tmp_path, {"path": "large.txt"})

    assert len(first) < 65_000
    assert "characters 0:32000 of 1500000" in first
    assert "offset=32000, limit=32000" in first
    assert ".claude" not in first
    assert content[:100] in first

    second = _exec_read_file(
        tmp_path,
        {"path": "large.txt", "offset": 32_000, "limit": 10_000},
    )
    assert "characters 32000:42000 of 1500000" in second
    assert content[32_000:32_100] in second
    assert "offset=42000, limit=10000" in second


def test_read_file_hard_caps_untrusted_limit_and_preserves_small_results(tmp_path) -> None:
    (tmp_path / "small.txt").write_text("small result", encoding="utf-8")
    assert _exec_read_file(tmp_path, {"path": "small.txt"}) == "small result"

    content = "x" * 1_500_000
    (tmp_path / "large.txt").write_text(content, encoding="utf-8")
    bounded = _exec_read_file(
        tmp_path,
        {"path": "large.txt", "offset": 0, "limit": 2_000_000},
    )
    assert len(bounded) < 65_000
    assert "characters 0:64000 of 1500000" in bounded
    assert "offset=64000, limit=64000" in bounded


def test_search_output_is_bounded_before_provider_transport(tmp_path) -> None:
    (tmp_path / "one-huge-line.txt").write_text(
        "needle" + ("x" * 1_500_000),
        encoding="utf-8",
    )

    result = _exec_search_files(tmp_path, {"pattern": "needle", "path": "."})

    assert len(result) < 65_000
    assert "search output truncated by Oompah" in result
    assert ".claude" not in result


def test_claude_catalog_keeps_large_auditor_read_in_approved_tool_channel(
    tmp_path,
) -> None:
    from oompah.acp_tools import build_tool_catalog

    (tmp_path / "large.txt").write_text("z" * 1_500_000, encoding="utf-8")
    read_tool = next(
        tool for tool in build_tool_catalog(str(tmp_path), auditor=True)
        if tool.name == "read_file"
    )

    assert read_tool.input_schema["required"] == ["path"]
    assert {"path", "offset", "limit"} <= set(
        read_tool.input_schema["properties"]
    )
    response = asyncio.run(read_tool.handler({"path": "large.txt"}))
    text = response["content"][0]["text"]

    assert len(text) < 65_000
    assert "continue only through the approved tool" in text
    assert "offset=32000" in text
    assert ".claude" not in text


def test_large_run_command_uses_opaque_approved_continuation(tmp_path) -> None:
    store = CommandOutputStore()
    result = _exec_run_command(
        tmp_path,
        {
            "command": (
                "python -c \"print('audit-start'); print('x' * 1500000); "
                "print('audit-end')\""
            )
        },
        output_store=store,
    )

    assert len(result) < 65_000
    match = re.search(r"result_id='([^']+)'", result)
    assert match is not None
    result_id = match.group(1)
    assert ".claude" not in result
    assert "read_command_output" in result

    page = _exec_read_command_output(
        store,
        {"result_id": result_id, "offset": 32_000, "limit": 32_000},
    )
    assert len(page) < 65_000
    assert "characters 32000:64000" in page
    assert "provider-private" not in page
    assert ".claude" not in page

    search = _exec_read_command_output(
        store,
        {"result_id": result_id, "pattern": "audit-end"},
    )
    assert "audit-end" in search
    assert ".claude" not in search


def test_claude_auditor_can_page_search_and_submit_after_large_command(
    tmp_path,
) -> None:
    from oompah.acp_tools import build_tool_catalog

    target = AuditorTargetContract(
        audit_id="audit-large-output",
        task_id="TASK-LARGE-OUTPUT",
        project_id="project-large-output",
        target_state="Done",
        evidence_fingerprint="a" * 64,
        attempt_id="attempt-large-output",
        previous_state="In Validation",
    )
    received = []
    (tmp_path / "Makefile").write_text(
        "test:\n"
        "\t@python -c \"print('audit-start'); print('x' * 1500000); "
        "print('audit-end')\"\n",
        encoding="utf-8",
    )
    catalog = build_tool_catalog(
        str(tmp_path),
        auditor=True,
        action_policy=auditor_policy(
            task_identifier=target.task_id,
            project_id=target.project_id,
        ),
        audit_target=target,
        audit_result_handler=received.append,
    )
    tools = {tool.name: tool for tool in catalog}

    result = asyncio.run(
        tools["run_command"].handler(
            {"command": "make test"}
        )
    )["content"][0]["text"]
    assert len(result) < 65_000
    result_id = re.search(r"result_id='([^']+)'", result).group(1)

    page = asyncio.run(
        tools["read_command_output"].handler(
            {"result_id": result_id, "offset": 32_000, "limit": 32_000}
        )
    )["content"][0]["text"]
    search = asyncio.run(
        tools["read_command_output"].handler(
            {"result_id": result_id, "pattern": "audit-end"}
        )
    )["content"][0]["text"]
    assert "characters 32000:64000" in page
    assert "audit-end" in search
    assert ".claude" not in result + page + search

    verdict = asyncio.run(
        tools["submit_audit_result"].handler(
            {
                "result": {
                    "audit_id": target.audit_id,
                    "target_state": target.target_state,
                    "evidence_fingerprint": target.evidence_fingerprint,
                    "verdict": "pass",
                    "message": "The bounded command result was inspected.",
                    "attempt_id": target.attempt_id,
                }
            }
        )
    )["content"][0]["text"]
    assert '"accepted": true' in verdict
    assert received[0].audit_id == target.audit_id
