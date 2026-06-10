from __future__ import annotations

import os

from oompah.orchestrator import _agent_log_issue_stem, _agent_log_path


def test_agent_log_issue_stem_sanitizes_github_identifier():
    assert (
        _agent_log_issue_stem("NVIDIA-Omniverse/trickle#226")
        == "NVIDIA-Omniverse_trickle_226"
    )


def test_agent_log_path_keeps_github_identifier_in_single_basename(tmp_path):
    log_dir = tmp_path / "agent-logs"

    path = _agent_log_path(
        str(log_dir),
        "NVIDIA-Omniverse/trickle#226",
        ts="20260610T213730Z",
    )

    assert os.path.dirname(path) == str(log_dir)
    assert os.path.basename(path) == (
        "NVIDIA-Omniverse_trickle_226__20260610T213730Z.jsonl"
    )
    assert log_dir.is_dir()
    assert not (log_dir / "NVIDIA-Omniverse").exists()


def test_agent_log_issue_stem_falls_back_for_empty_identifier():
    assert _agent_log_issue_stem("") == "issue"
