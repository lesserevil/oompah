"""Regression coverage for transport-safe ACP tool results (OOMPAH-710)."""

from __future__ import annotations

import asyncio

from oompah.api_agent import _exec_read_file, _exec_search_files


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
