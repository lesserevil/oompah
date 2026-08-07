"""Tests for OOMPAH-468: Persist worker and epic contributor provider-model provenance.

Covers:
- WorkContributor model: to_dict / from_dict roundtrip
- merge_contributor_records: accumulation, preserve prior records
- load_contributors: safe deserialization from metadata
- sha_is_ancestor: git ancestry check (mocked subprocess)
- collect_epic_contributors: epic union with shared children, nested epics,
  commit exclusion, and cycle guards
- _build_work_contributor_record: API, ACP SDK-managed unknown model, CLI worker
- _write_work_contributor_record: metadata persistence, merges, error resilience
- _fire_work_contributor_record: non-blocking fire-and-forget, pool resilience
- _on_worker_exit integration: normal writes, stalled/abnormal do NOT write
- Redaction: no credentials, prompts, logs, or costs in stored records
- Restart rereads: records persist in tracker metadata across restarts
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import threading
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from oompah.models import Issue, LiveSession, RunningEntry
from oompah.work_contributors import (
    METADATA_KEY,
    WorkContributor,
    _UNKNOWN_MODEL_NAMES,
    collect_epic_contributors,
    load_contributors,
    merge_contributor_records,
    contributor_run_identity,
    sha_is_ancestor,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_contributor(
    run_id: str = "TASK-001__20260101T000000Z",
    provider_id: str | None = "prov-abc",
    provider_name: str | None = "TestProvider",
    model_id: str | None = "gpt-4o",
    focus: str | None = "feature",
    source_branch: str | None = "task-TASK-001",
    source_sha: str | None = "deadbeef0001",
    completed_at: str = "2026-01-01T00:00:00+00:00",
) -> WorkContributor:
    return WorkContributor(
        run_id=run_id,
        provider_id=provider_id,
        provider_name=provider_name,
        model_id=model_id,
        focus=focus,
        source_branch=source_branch,
        source_sha=source_sha,
        completed_at=completed_at,
    )


def _make_issue(
    identifier: str = "TASK-001",
    issue_type: str = "task",
    work_branch: str | None = None,
    branch_name: str | None = None,
    project_id: str | None = None,
    state: str = "in_progress",
) -> Issue:
    issue = Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="",
        state=state,
        issue_type=issue_type,
        project_id=project_id,
    )
    issue.work_branch = work_branch
    issue.branch_name = branch_name
    return issue


def _make_running_entry(
    identifier: str = "TASK-001",
    provider_id: str | None = "prov-abc",
    provider_name: str | None = "TestProvider",
    model_name: str | None = "gpt-4o",
    focus_name: str | None = "feature",
    workspace_path: str | None = None,
    agent_log_path: str | None = None,
    work_branch: str | None = "task-TASK-001",
    issue: Issue | None = None,
) -> RunningEntry:
    if issue is None:
        issue = _make_issue(identifier, work_branch=work_branch)
    entry = RunningEntry(
        worker_task=MagicMock(),
        identifier=identifier,
        issue=issue,
        session=MagicMock(spec=LiveSession),
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
    )
    entry.provider_id = provider_id
    entry.provider_name = provider_name
    entry.model_name = model_name
    entry.focus_name = focus_name
    entry.workspace_path = workspace_path
    entry.agent_log_path = agent_log_path
    return entry


def _make_orchestrator(tmp_path):
    """Create a minimal test orchestrator."""
    from oompah.config import ServiceConfig
    from unittest.mock import MagicMock

    cfg = ServiceConfig()
    project_store = MagicMock()
    project_store.list_all.return_value = []

    from oompah.orchestrator import Orchestrator

    orch = Orchestrator(
        config=cfg,
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    return orch


# ---------------------------------------------------------------------------
# TestWorkContributorModel
# ---------------------------------------------------------------------------


class TestWorkContributorModel:
    """WorkContributor data model: serialization roundtrip."""

    def test_to_dict_contains_all_fields(self):
        c = _make_contributor()
        d = c.to_dict()
        assert d["run_id"] == "TASK-001__20260101T000000Z"
        assert d["provider_id"] == "prov-abc"
        assert d["provider_name"] == "TestProvider"
        assert d["model_id"] == "gpt-4o"
        assert d["focus"] == "feature"
        assert d["source_branch"] == "task-TASK-001"
        assert d["source_sha"] == "deadbeef0001"
        assert d["completed_at"] == "2026-01-01T00:00:00+00:00"

    def test_from_dict_roundtrip(self):
        c = _make_contributor()
        restored = WorkContributor.from_dict(c.to_dict())
        assert restored.run_id == c.run_id
        assert restored.provider_id == c.provider_id
        assert restored.provider_name == c.provider_name
        assert restored.model_id == c.model_id
        assert restored.focus == c.focus
        assert restored.source_branch == c.source_branch
        assert restored.source_sha == c.source_sha
        assert restored.completed_at == c.completed_at

    def test_from_dict_tolerates_missing_optional_fields(self):
        """from_dict must not crash on a minimal dict."""
        c = WorkContributor.from_dict({"run_id": "abc", "completed_at": "2026-01-01T00:00:00+00:00"})
        assert c.run_id == "abc"
        assert c.provider_id is None
        assert c.provider_name is None
        assert c.model_id is None
        assert c.focus is None
        assert c.source_sha is None

    def test_from_dict_none_model_id_preserved(self):
        """None model_id (SDK-managed) round-trips as None."""
        c = _make_contributor(model_id=None)
        d = c.to_dict()
        assert d["model_id"] is None
        restored = WorkContributor.from_dict(d)
        assert restored.model_id is None

    def test_to_dict_contains_no_credentials(self):
        """Serialized dict must never contain credential-like keys."""
        c = _make_contributor()
        d = c.to_dict()
        forbidden = {"api_key", "token", "password", "secret", "credential", "prompt",
                     "cost", "tokens", "log_path"}
        for key in d:
            assert key.lower() not in forbidden, (
                f"to_dict() must not contain key {key!r}; it may carry credentials or costs"
            )


# ---------------------------------------------------------------------------
# TestRedaction
# ---------------------------------------------------------------------------


class TestRedaction:
    """Stored records must never include credentials, prompts, logs, or costs."""

    def test_to_dict_has_no_api_key(self):
        c = _make_contributor(provider_name="TestProvider", source_branch="main-branch")
        d = c.to_dict()
        for k in d:
            assert "api_key" not in str(k).lower()
        # No field should hold an OpenAI-style API key
        for k, v in d.items():
            if isinstance(v, str) and len(v) > 10:
                assert not (v.startswith("sk-") or v.startswith("Bearer ")), (
                    f"Field {k!r} looks like an API key: {v!r}"
                )

    def test_to_dict_has_no_cost_fields(self):
        c = _make_contributor()
        d = c.to_dict()
        for k in d:
            assert "cost" not in k.lower()
            assert "token" not in k.lower()
            assert "usd" not in k.lower()

    def test_to_dict_has_no_log_path(self):
        c = _make_contributor()
        d = c.to_dict()
        for k in d:
            assert "log" not in k.lower()
            assert "path" not in k.lower()

    def test_to_dict_has_no_prompt_field(self):
        c = _make_contributor()
        d = c.to_dict()
        for k in d:
            assert "prompt" not in k.lower()
            assert "instruction" not in k.lower()

    def test_merge_record_has_no_forbidden_keys(self):
        c = _make_contributor(provider_name="TestProvider", source_branch="main-branch")
        merged = merge_contributor_records(None, c)
        import json
        text = json.dumps(merged)
        for forbidden in ("api_key", "password", "token_count", "cost_usd"):
            assert forbidden not in text, (
                f"merge_contributor_records output contains {forbidden!r}"
            )
        # Check no value looks like an actual API key
        for key, value in merged.get("runs", [{}])[0].items():
            if isinstance(value, str) and len(value) > 10:
                assert not value.startswith("sk-"), (
                    f"Field {key!r} looks like an API key"
                )


# ---------------------------------------------------------------------------
# TestMergeContributorRecords
# ---------------------------------------------------------------------------


class TestMergeContributorRecords:
    """merge_contributor_records: accumulation and prior preservation."""

    def test_merge_into_none_returns_single_run(self):
        c = _make_contributor(run_id="run-1")
        merged = merge_contributor_records(None, c)
        assert len(merged["runs"]) == 1
        assert merged["runs"][0]["run_id"] == "run-1"

    def test_merge_into_empty_dict_returns_single_run(self):
        c = _make_contributor(run_id="run-1")
        merged = merge_contributor_records({}, c)
        assert len(merged["runs"]) == 1

    def test_merge_preserves_prior_records(self):
        """Prior runs must be preserved when a new run is added."""
        c1 = _make_contributor(run_id="run-1", completed_at="2026-01-01T00:00:00+00:00")
        c2 = _make_contributor(run_id="run-2", completed_at="2026-01-02T00:00:00+00:00")
        first = merge_contributor_records(None, c1)
        second = merge_contributor_records(first, c2)
        assert len(second["runs"]) == 2
        run_ids = {r["run_id"] for r in second["runs"]}
        assert run_ids == {"run-1", "run-2"}

    def test_merge_three_runs_accumulated(self):
        """Three retried runs produce three records."""
        existing = merge_contributor_records(None, _make_contributor(run_id="r1"))
        existing = merge_contributor_records(existing, _make_contributor(run_id="r2"))
        existing = merge_contributor_records(existing, _make_contributor(run_id="r3"))
        assert len(existing["runs"]) == 3

    def test_same_run_id_is_upserted_for_verified_completion(self):
        pending = _make_contributor(
            run_id="run-1", source_sha=None, completed_at=""
        )
        completed = _make_contributor(
            run_id="run-1", source_sha="abc123", completed_at="2026-01-01Z"
        )

        merged = merge_contributor_records(
            merge_contributor_records(None, pending), completed
        )

        assert len(merged["runs"]) == 1
        assert merged["runs"][0]["source_sha"] == "abc123"
        assert merged["runs"][0]["completed_at"] == "2026-01-01Z"

    def test_merge_different_providers_both_preserved(self):
        """Records from different providers are both stored."""
        c_api = _make_contributor(run_id="api-run", provider_name="OpenAI", model_id="gpt-4o")
        c_acp = _make_contributor(run_id="acp-run", provider_name="Anthropic", model_id=None)
        merged = merge_contributor_records(merge_contributor_records(None, c_api), c_acp)
        names = {r["provider_name"] for r in merged["runs"]}
        assert "OpenAI" in names
        assert "Anthropic" in names

    def test_merge_returns_runs_key(self):
        c = _make_contributor()
        merged = merge_contributor_records(None, c)
        assert "runs" in merged
        assert isinstance(merged["runs"], list)

    def test_merge_with_malformed_existing_still_appends(self):
        """If existing is missing 'runs' key, we proceed gracefully."""
        c = _make_contributor(run_id="new-run")
        merged = merge_contributor_records({"malformed": True}, c)
        assert any(r["run_id"] == "new-run" for r in merged["runs"])


# ---------------------------------------------------------------------------
# TestLoadContributors
# ---------------------------------------------------------------------------


class TestLoadContributors:
    """load_contributors: safe deserialization from metadata."""

    def test_empty_metadata_returns_empty(self):
        assert load_contributors({}) == []

    def test_missing_key_returns_empty(self):
        assert load_contributors({"other_key": "value"}) == []

    def test_single_run_deserialized(self):
        c = _make_contributor(run_id="r-42")
        meta = {METADATA_KEY: merge_contributor_records(None, c)}
        loaded = load_contributors(meta)
        assert len(loaded) == 1
        assert loaded[0].run_id == "r-42"
        assert loaded[0].provider_name == "TestProvider"

    def test_multiple_runs_deserialized(self):
        c1 = _make_contributor(run_id="r-1")
        c2 = _make_contributor(run_id="r-2")
        merged = merge_contributor_records(merge_contributor_records(None, c1), c2)
        loaded = load_contributors({METADATA_KEY: merged})
        assert len(loaded) == 2

    def test_malformed_run_is_skipped(self):
        """A malformed entry (not a dict) is silently skipped."""
        meta = {METADATA_KEY: {"runs": ["not-a-dict", None, 42]}}
        loaded = load_contributors(meta)
        assert loaded == []

    def test_partial_run_still_loads(self):
        """A run missing optional fields is still loaded."""
        meta = {METADATA_KEY: {"runs": [{"run_id": "x", "completed_at": "t"}]}}
        loaded = load_contributors(meta)
        assert len(loaded) == 1
        assert loaded[0].run_id == "x"
        assert loaded[0].model_id is None

    def test_none_value_for_key_returns_empty(self):
        meta = {METADATA_KEY: None}
        assert load_contributors(meta) == []


# ---------------------------------------------------------------------------
# TestShaIsAncestor
# ---------------------------------------------------------------------------


class TestShaIsAncestor:
    """sha_is_ancestor: git ancestry check."""

    def test_returns_true_when_git_exits_zero(self, tmp_path):
        with patch("oompah.work_contributors.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = sha_is_ancestor("abc123", "def456", str(tmp_path))
        assert result is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "merge-base" in cmd
        assert "--is-ancestor" in cmd
        assert "abc123" in cmd
        assert "def456" in cmd

    def test_returns_false_when_git_exits_nonzero(self, tmp_path):
        with patch("oompah.work_contributors.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = sha_is_ancestor("abc123", "def456", str(tmp_path))
        assert result is False

    def test_returns_false_on_os_error(self, tmp_path):
        with patch("oompah.work_contributors.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("git not found")
            result = sha_is_ancestor("abc123", "def456", str(tmp_path))
        assert result is False

    def test_returns_false_on_timeout(self, tmp_path):
        with patch("oompah.work_contributors.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(["git"], 15)
            result = sha_is_ancestor("abc123", "def456", str(tmp_path))
        assert result is False

    def test_returns_false_for_empty_sha(self, tmp_path):
        result = sha_is_ancestor("", "def456", str(tmp_path))
        assert result is False

    def test_returns_false_for_empty_base_sha(self, tmp_path):
        result = sha_is_ancestor("abc123", "", str(tmp_path))
        assert result is False

    def test_returns_false_for_empty_repo_path(self):
        result = sha_is_ancestor("abc123", "def456", "")
        assert result is False


# ---------------------------------------------------------------------------
# TestCollectEpicContributors
# ---------------------------------------------------------------------------


def _make_tracker_for_epic(
    contributors_by_id: dict[str, list[WorkContributor]],
    children_by_id: dict[str, list[Any]],
) -> MagicMock:
    """Build a mock tracker for epic contributor tests."""
    tracker = MagicMock()

    def get_metadata(identifier):
        contribs = contributors_by_id.get(identifier, [])
        if not contribs:
            return {}
        record = None
        for c in contribs:
            record = merge_contributor_records(record, c)
        return {METADATA_KEY: record}

    def fetch_children(epic_id):
        return children_by_id.get(epic_id, [])

    tracker.get_metadata.side_effect = get_metadata
    tracker.fetch_children.side_effect = fetch_children
    return tracker


class TestCollectEpicContributors:
    """collect_epic_contributors: union from epic and all children."""

    def test_own_contributors_included(self):
        """Epic's own work_contributors are always included."""
        c = _make_contributor(run_id="epic-run", source_sha=None)
        tracker = _make_tracker_for_epic(
            {"EPIC-1": [c]},
            {"EPIC-1": []},
        )
        result = collect_epic_contributors("EPIC-1", "", tracker)
        assert len(result) == 1
        assert result[0].run_id == "epic-run"

    def test_child_contributors_included(self):
        """Contributors from direct child tasks are included in the union."""
        epic_c = _make_contributor(run_id="epic-run", source_sha=None)
        child_c = _make_contributor(run_id="child-run", source_sha=None)
        child = _make_issue("CHILD-1")
        tracker = _make_tracker_for_epic(
            {"EPIC-1": [epic_c], "CHILD-1": [child_c]},
            {"EPIC-1": [child]},
        )
        result = collect_epic_contributors("EPIC-1", "", tracker)
        run_ids = {c.run_id for c in result}
        assert "epic-run" in run_ids
        assert "child-run" in run_ids

    def test_shared_epic_children_all_included(self):
        """Multiple children of the same epic are all included."""
        c1 = _make_contributor(run_id="c1", source_sha=None)
        c2 = _make_contributor(run_id="c2", source_sha=None)
        c3 = _make_contributor(run_id="c3", source_sha=None)
        child1 = _make_issue("CHILD-1")
        child2 = _make_issue("CHILD-2")
        tracker = _make_tracker_for_epic(
            {"EPIC-1": [], "CHILD-1": [c1, c2], "CHILD-2": [c3]},
            {"EPIC-1": [child1, child2]},
        )
        result = collect_epic_contributors("EPIC-1", "", tracker)
        run_ids = {c.run_id for c in result}
        assert run_ids == {"c1", "c2", "c3"}

    def test_nested_epics_collected_recursively(self):
        """Contributors from nested epics (children of children) are included."""
        grandchild_c = _make_contributor(run_id="grandchild-run", source_sha=None)
        child_epic = _make_issue("CHILD-EPIC", issue_type="epic")
        grandchild = _make_issue("GRANDCHILD-1")
        tracker = _make_tracker_for_epic(
            {
                "EPIC-1": [],
                "CHILD-EPIC": [],
                "GRANDCHILD-1": [grandchild_c],
            },
            {
                "EPIC-1": [child_epic],
                "CHILD-EPIC": [grandchild],
            },
        )
        result = collect_epic_contributors("EPIC-1", "", tracker)
        assert any(c.run_id == "grandchild-run" for c in result)

    def test_deduplication_by_run_id(self):
        """If the same run_id appears in multiple children, it's deduplicated."""
        c = _make_contributor(run_id="shared-run", source_sha=None)
        child1 = _make_issue("CHILD-1")
        child2 = _make_issue("CHILD-2")
        # Both children somehow have the same run_id (e.g. shared worktree)
        tracker = _make_tracker_for_epic(
            {"EPIC-1": [], "CHILD-1": [c], "CHILD-2": [c]},
            {"EPIC-1": [child1, child2]},
        )
        result = collect_epic_contributors("EPIC-1", "", tracker)
        assert len(result) == 1  # deduplicated

    def test_commits_excluded_when_not_ancestor(self, tmp_path):
        """Contributors whose source_sha is not an ancestor of audit_sha are excluded."""
        included = _make_contributor(run_id="in-revision", source_sha="aaa111")
        excluded = _make_contributor(run_id="not-in-revision", source_sha="bbb222")
        tracker = _make_tracker_for_epic(
            {"EPIC-1": [included, excluded]},
            {"EPIC-1": []},
        )

        def ancestor_check(sha, base, repo):
            return sha == "aaa111"  # only aaa111 is an ancestor

        with patch("oompah.work_contributors.sha_is_ancestor", side_effect=ancestor_check):
            result = collect_epic_contributors(
                "EPIC-1", "audit-sha", tracker, repo_path=str(tmp_path)
            )
        run_ids = {c.run_id for c in result}
        assert "in-revision" in run_ids
        assert "not-in-revision" not in run_ids

    def test_unknown_sha_included_conservatively(self, tmp_path):
        """A contributor with no source_sha is always included (conservative)."""
        c = _make_contributor(run_id="no-sha", source_sha=None)
        tracker = _make_tracker_for_epic(
            {"EPIC-1": [c]},
            {"EPIC-1": []},
        )
        # Ancestry check always returns False
        with patch("oompah.work_contributors.sha_is_ancestor", return_value=False):
            result = collect_epic_contributors(
                "EPIC-1", "audit-sha", tracker, repo_path=str(tmp_path)
            )
        assert any(c.run_id == "no-sha" for c in result)

    def test_cycle_guard_prevents_infinite_recursion(self):
        """Circular parent references do not cause infinite recursion."""
        c = _make_contributor(run_id="r1", source_sha=None)
        child_epic = _make_issue("CHILD-EPIC", issue_type="epic")
        # CHILD-EPIC's children include the parent EPIC-1 (cycle)
        parent = _make_issue("EPIC-1", issue_type="epic")
        tracker = _make_tracker_for_epic(
            {"EPIC-1": [c], "CHILD-EPIC": []},
            {
                "EPIC-1": [child_epic],
                "CHILD-EPIC": [parent],  # cycle back to parent
            },
        )
        result = collect_epic_contributors("EPIC-1", "", tracker)
        # Should complete without error
        assert isinstance(result, list)

    def test_tracker_error_on_metadata_is_skipped(self):
        """Tracker metadata errors for a child do not abort the whole collection."""
        c = _make_contributor(run_id="epic-run", source_sha=None)
        child = _make_issue("CHILD-1")
        tracker = MagicMock()

        def get_metadata(identifier):
            if identifier == "EPIC-1":
                return {METADATA_KEY: merge_contributor_records(None, c)}
            raise RuntimeError("db error")

        tracker.get_metadata.side_effect = get_metadata
        tracker.fetch_children.return_value = [child]

        result = collect_epic_contributors("EPIC-1", "", tracker)
        # Epic's own contributor is still included despite child's error
        assert any(c.run_id == "epic-run" for c in result)

    def test_no_repo_path_includes_all(self):
        """When no repo_path is given, no ancestry filtering is applied."""
        c1 = _make_contributor(run_id="r1", source_sha="sha1")
        c2 = _make_contributor(run_id="r2", source_sha="sha2")
        tracker = _make_tracker_for_epic(
            {"EPIC-1": [c1, c2]},
            {"EPIC-1": []},
        )
        result = collect_epic_contributors("EPIC-1", "audit-sha", tracker, repo_path=None)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# TestBuildWorkContributorRecord
# ---------------------------------------------------------------------------


class TestBuildWorkContributorRecord:
    """_build_work_contributor_record: builds WorkContributor from RunningEntry."""

    def test_api_worker_all_fields_set(self, tmp_path):
        """API worker: all fields populated."""
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(
            identifier="TASK-001",
            provider_id="prov-xyz",
            provider_name="OpenAI",
            model_name="gpt-4o",
            focus_name="feature",
            workspace_path=str(tmp_path),
            agent_log_path="/logs/TASK-001__20260101T000000Z.jsonl",
            work_branch="task-TASK-001",
        )
        with patch.object(orch, "_worktree_head", return_value="abc123"):
            c = orch._build_work_contributor_record(entry)
        assert c is not None
        assert c.run_id == contributor_run_identity(
            entry.run_id, "prov-xyz", "gpt-4o"
        )
        assert c.provider_id == "prov-xyz"
        assert c.provider_name == "OpenAI"
        assert c.model_id == "gpt-4o"
        assert c.focus == "feature"
        assert c.source_branch == "task-TASK-001"
        assert c.source_sha == "abc123"
        assert c.completed_at  # non-empty ISO timestamp

    def test_acp_sdk_managed_unknown_model_gives_none_model_id(self, tmp_path):
        """ACP SDK-managed model (model_name='default') → model_id = None."""
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(
            provider_id="acp",
            provider_name="acp",
            model_name="default",  # synthetic SDK-managed name
        )
        c = orch._build_work_contributor_record(entry)
        assert c is not None
        assert c.model_id is None

    def test_acp_none_model_gives_none_model_id(self, tmp_path):
        """ACP with model_name=None → model_id = None."""
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(model_name=None)
        c = orch._build_work_contributor_record(entry)
        assert c is not None
        assert c.model_id is None

    def test_cli_worker_gives_none_model_id(self, tmp_path):
        """CLI worker (model_name='cli-managed') → model_id = None."""
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(
            provider_id="cli",
            provider_name="cli",
            model_name="cli-managed",
        )
        c = orch._build_work_contributor_record(entry)
        assert c is not None
        assert c.model_id is None
        assert c.provider_id == "cli"
        assert c.provider_name == "cli"

    def test_cli_worker_empty_model_name(self, tmp_path):
        """CLI worker with empty model_name → model_id = None."""
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(model_name="")
        c = orch._build_work_contributor_record(entry)
        assert c is not None
        assert c.model_id is None

    def test_run_id_from_log_path(self, tmp_path):
        """run_id is derived from agent_log_path basename without .jsonl."""
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(
            agent_log_path="/var/logs/TASK-042__20260201T120000Z.jsonl"
        )
        entry.run_id = ""
        c = orch._build_work_contributor_record(entry)
        assert c is not None
        assert c.run_id == "TASK-042__20260201T120000Z"

    def test_dispatch_run_id_precedes_log_path(self, tmp_path):
        """Completion retains the base identity that derived its launch fence."""

        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(agent_log_path="/logs/different.jsonl")
        entry.run_id = "dispatch-run"

        contributor = orch._build_work_contributor_record(entry)

        assert contributor is not None
        assert contributor.run_id == contributor_run_identity(
            "dispatch-run", entry.provider_id, entry.model_name
        )

    def test_run_id_fallback_when_no_log_path(self, tmp_path):
        """Without agent_log_path, run_id falls back to identifier__timestamp."""
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(identifier="TASK-123", agent_log_path=None)
        entry.run_id = ""
        c = orch._build_work_contributor_record(entry)
        assert c is not None
        assert c.run_id.startswith("TASK-123__")

    def test_source_sha_from_worktree_head(self, tmp_path):
        """source_sha is populated from _worktree_head(workspace_path)."""
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(workspace_path=str(tmp_path))
        with patch.object(orch, "_worktree_head", return_value="cafebabe") as mock:
            c = orch._build_work_contributor_record(entry)
        mock.assert_called_once_with(str(tmp_path))
        assert c is not None
        assert c.source_sha == "cafebabe"

    def test_source_sha_none_when_no_workspace(self, tmp_path):
        """source_sha is None when workspace_path is not set."""
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(workspace_path=None)
        c = orch._build_work_contributor_record(entry)
        assert c is not None
        assert c.source_sha is None

    def test_source_sha_none_when_worktree_head_empty(self, tmp_path):
        """source_sha is None when _worktree_head returns empty string."""
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(workspace_path=str(tmp_path))
        with patch.object(orch, "_worktree_head", return_value=""):
            c = orch._build_work_contributor_record(entry)
        assert c is not None
        assert c.source_sha is None

    def test_source_branch_from_work_branch(self, tmp_path):
        """source_branch comes from issue.work_branch first."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("T-1", work_branch="work-branch-name", branch_name="alt-branch")
        entry = _make_running_entry(issue=issue)
        c = orch._build_work_contributor_record(entry)
        assert c is not None
        assert c.source_branch == "work-branch-name"

    def test_source_branch_fallback_to_branch_name(self, tmp_path):
        """source_branch falls back to issue.branch_name when work_branch is None."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("T-1", work_branch=None, branch_name="fallback-branch")
        entry = _make_running_entry(issue=issue)
        c = orch._build_work_contributor_record(entry)
        assert c is not None
        assert c.source_branch == "fallback-branch"

    def test_missing_identifier_returns_none(self, tmp_path):
        """When entry has no identifier, build returns None."""
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(identifier="")
        entry.identifier = ""
        c = orch._build_work_contributor_record(entry)
        assert c is None

    def test_completed_at_is_utc_iso(self, tmp_path):
        """completed_at is an ISO-8601 UTC string."""
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry()
        c = orch._build_work_contributor_record(entry)
        assert c is not None
        dt = datetime.fromisoformat(c.completed_at)
        assert dt.tzinfo is not None

    def test_unknown_model_names_all_yield_none_model_id(self, tmp_path):
        """All _UNKNOWN_MODEL_NAMES values produce model_id = None."""
        orch = _make_orchestrator(tmp_path)
        for name in _UNKNOWN_MODEL_NAMES:
            entry = _make_running_entry(model_name=name)
            c = orch._build_work_contributor_record(entry)
            assert c is not None
            assert c.model_id is None, (
                f"Expected model_id=None for unknown model name {name!r}"
            )


# ---------------------------------------------------------------------------
# TestWriteWorkContributorRecord
# ---------------------------------------------------------------------------


class TestWriteWorkContributorRecord:
    """_write_work_contributor_record: metadata persistence."""

    def _make_orch_with_tracker(self, tmp_path, metadata_store=None):
        orch = _make_orchestrator(tmp_path)
        if metadata_store is None:
            metadata_store = {}
        mock_tracker = MagicMock()
        mock_tracker.get_metadata.side_effect = (
            lambda identifier: metadata_store.get(identifier, {})
        )
        mock_tracker.set_metadata_field.side_effect = (
            lambda identifier, key, value:
            metadata_store.setdefault(identifier, {}).__setitem__(key, value)
        )
        orch.tracker = mock_tracker
        orch._project_trackers = {"__legacy__": mock_tracker}
        return orch, mock_tracker, metadata_store

    def test_prelaunch_evidence_is_written_and_read_back_synchronously(self, tmp_path):
        store: dict[str, dict] = {}
        orch, tracker, store = self._make_orch_with_tracker(tmp_path, store)
        issue = _make_issue("TASK-001")

        orch._persist_work_contributor_launch(
            issue,
            run_id="run-launch",
            provider_id="provider-1",
            provider_name="Provider One",
            model="default",
            focus="feature",
        )

        contributor = load_contributors(store[issue.identifier])[0]
        assert contributor.run_id == "run-launch"
        assert contributor.provider_id == "provider-1"
        assert contributor.model_id is None
        assert contributor.completed_at == ""
        assert tracker.get_metadata.call_count == 2

    def test_prelaunch_write_without_readback_confirmation_fails(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.get_metadata.return_value = {}
        orch.tracker = tracker
        issue = _make_issue("TASK-001")

        with pytest.raises(RuntimeError, match="did not confirm"):
            orch._persist_work_contributor_launch(
                issue,
                run_id="run-launch",
                provider_id="provider-1",
                provider_name="Provider One",
                model="model-1",
            )

    def test_completion_enriches_the_stable_prelaunch_identity(self, tmp_path):
        store: dict[str, dict] = {}
        orch, _tracker, store = self._make_orch_with_tracker(tmp_path, store)
        issue = _make_issue("TASK-001")
        base_run_id = "dispatch-run"
        identity = contributor_run_identity(base_run_id, "provider-1", "model-1")
        orch._persist_work_contributor_launch(
            issue,
            run_id=identity,
            provider_id="provider-1",
            provider_name="Provider One",
            model="model-1",
        )
        entry = _make_running_entry(
            issue=issue,
            provider_id="provider-1",
            provider_name="Provider One",
            model_name="model-1",
        )
        entry.run_id = base_run_id
        orch._write_work_contributor_record(entry)

        contributors = load_contributors(store[issue.identifier])
        assert len(contributors) == 1
        assert contributors[0].run_id == identity
        assert contributors[0].completed_at

    def test_competing_completion_writers_preserve_both_rows_across_restart(
        self,
        tmp_path,
    ):
        store: dict[str, dict] = {}
        orch, _tracker, store = self._make_orch_with_tracker(tmp_path, store)
        issue = _make_issue("TASK-001")
        entries = []
        for suffix in ("one", "two"):
            entry = _make_running_entry(
                issue=issue,
                provider_id=f"provider-{suffix}",
                provider_name=f"Provider {suffix}",
                model_name=f"model-{suffix}",
            )
            entry.run_id = f"run-{suffix}"
            entries.append(entry)
            # Reproduce the production sequence: each launch first installs
            # its crash-safe row, then completion writers race to enrich the
            # same stable identities rather than appending unrelated rows.
            orch._persist_work_contributor_launch(
                issue,
                run_id=contributor_run_identity(
                    entry.run_id,
                    entry.provider_id,
                    entry.model_name,
                ),
                provider_id=entry.provider_id,
                provider_name=entry.provider_name,
                model=entry.model_name,
            )

        threads = [
            threading.Thread(target=orch._write_work_contributor_record, args=(entry,))
            for entry in entries
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
            assert not thread.is_alive()

        restarted, _tracker, _store = self._make_orch_with_tracker(tmp_path, store)
        metadata = restarted.tracker.get_metadata(issue.identifier)
        contributors = load_contributors(metadata)
        assert {value.provider_id for value in contributors} == {
            "provider-one",
            "provider-two",
        }

    def test_writes_contributor_to_metadata(self, tmp_path):
        """Happy path: contributor record written into issue metadata."""
        store: dict[str, dict] = {}
        orch, mock_tracker, store = self._make_orch_with_tracker(tmp_path, store)
        issue = _make_issue("TASK-001")
        entry = _make_running_entry(
            identifier="TASK-001",
            provider_id="prov-1",
            provider_name="TestProv",
            model_name="claude-sonnet",
            focus_name="feature",
            agent_log_path="/logs/TASK-001__t.jsonl",
            issue=issue,
        )
        orch._write_work_contributor_record(entry)
        assert "TASK-001" in store
        record = store["TASK-001"].get(METADATA_KEY)
        assert record is not None
        assert len(record["runs"]) == 1
        run = record["runs"][0]
        assert run["provider_id"] == "prov-1"
        assert run["provider_name"] == "TestProv"
        assert run["model_id"] == "claude-sonnet"
        assert run["focus"] == "feature"

    def test_merges_with_existing_contributor_records(self, tmp_path):
        """Second write accumulates without losing the first record."""
        store: dict[str, dict] = {}
        orch, mock_tracker, store = self._make_orch_with_tracker(tmp_path, store)
        issue = _make_issue("TASK-001")

        # First write
        entry1 = _make_running_entry(
            identifier="TASK-001",
            agent_log_path="/logs/TASK-001__t1.jsonl",
            model_name="model-a",
            issue=issue,
        )
        entry1.run_id = "dispatch-t1"
        orch._write_work_contributor_record(entry1)

        # Second write
        entry2 = _make_running_entry(
            identifier="TASK-001",
            agent_log_path="/logs/TASK-001__t2.jsonl",
            model_name="model-b",
            issue=issue,
        )
        entry2.run_id = "dispatch-t2"
        orch._write_work_contributor_record(entry2)

        record = store["TASK-001"][METADATA_KEY]
        assert len(record["runs"]) == 2
        run_ids = {r["run_id"] for r in record["runs"]}
        assert run_ids == {
            contributor_run_identity("dispatch-t1", "prov-abc", "model-a"),
            contributor_run_identity("dispatch-t2", "prov-abc", "model-b"),
        }

    def test_tracker_error_on_get_metadata_fails_closed_without_write(self, tmp_path):
        """A metadata read error cannot safely be overwritten by a blind upsert."""
        orch = _make_orchestrator(tmp_path)
        from oompah.tracker import TrackerError
        mock_tracker = MagicMock()
        mock_tracker.get_metadata.side_effect = TrackerError("db error")
        orch.tracker = mock_tracker

        issue = _make_issue("TASK-001")
        entry = _make_running_entry(
            identifier="TASK-001",
            agent_log_path="/logs/TASK-001__t.jsonl",
            issue=issue,
        )
        orch._write_work_contributor_record(entry)
        mock_tracker.set_metadata_field.assert_not_called()

    def test_tracker_error_on_set_metadata_is_swallowed(self, tmp_path):
        """If metadata write fails, exception is logged but not propagated."""
        from oompah.tracker import TrackerError
        orch = _make_orchestrator(tmp_path)
        mock_tracker = MagicMock()
        mock_tracker.get_metadata.return_value = {}
        mock_tracker.set_metadata_field.side_effect = TrackerError("write failed")
        orch.tracker = mock_tracker

        issue = _make_issue("TASK-001")
        entry = _make_running_entry(
            identifier="TASK-001",
            agent_log_path="/logs/TASK-001__t.jsonl",
            issue=issue,
        )
        # Must not raise
        orch._write_work_contributor_record(entry)

    def test_unexpected_exception_is_swallowed(self, tmp_path):
        """Any unexpected exception is swallowed."""
        orch = _make_orchestrator(tmp_path)
        mock_tracker = MagicMock()
        mock_tracker.get_metadata.side_effect = RuntimeError("unexpected")
        orch.tracker = mock_tracker

        issue = _make_issue("TASK-001")
        entry = _make_running_entry(issue=issue)
        # Must not raise
        orch._write_work_contributor_record(entry)

    def test_restart_rereads_persisted_records(self, tmp_path):
        """Records written to tracker metadata survive a simulated restart.

        After writing, load_contributors reading the same metadata
        returns the same records — simulating service restart that
        re-reads from persistent tracker storage.
        """
        store: dict[str, dict] = {}
        orch, _, store = self._make_orch_with_tracker(tmp_path, store)
        issue = _make_issue("TASK-001")
        entry = _make_running_entry(
            identifier="TASK-001",
            provider_id="prov-1",
            provider_name="Anthropic",
            model_name="claude-3",
            focus_name="feature",
            agent_log_path="/logs/TASK-001__20260101T.jsonl",
            issue=issue,
        )
        orch._write_work_contributor_record(entry)

        # Simulate restart: read back from the store (as a new process would)
        reread_meta = store.get("TASK-001", {})
        loaded = load_contributors(reread_meta)
        assert len(loaded) == 1
        assert loaded[0].provider_id == "prov-1"
        assert loaded[0].model_id == "claude-3"

    def test_multiple_workers_on_same_task_accumulate(self, tmp_path):
        """Multiple workers (parallel or sequential) produce separate records."""
        store: dict[str, dict] = {}
        orch, _, store = self._make_orch_with_tracker(tmp_path, store)
        issue = _make_issue("TASK-001")

        workers = [
            ("w1", "prov-1", "Anthropic", "claude-3"),
            ("w2", "prov-2", "OpenAI", "gpt-4o"),
            ("w3", "prov-1", "Anthropic", "claude-3"),  # third attempt same provider
        ]
        for stem, pid, pname, model in workers:
            entry = _make_running_entry(
                identifier="TASK-001",
                provider_id=pid,
                provider_name=pname,
                model_name=model,
                agent_log_path=f"/logs/TASK-001__{stem}.jsonl",
                issue=issue,
            )
            entry.run_id = stem
            orch._write_work_contributor_record(entry)

        record = store["TASK-001"][METADATA_KEY]
        assert len(record["runs"]) == 3
        run_ids = {r["run_id"] for r in record["runs"]}
        assert run_ids == {
            contributor_run_identity(stem, provider_id, model)
            for stem, provider_id, _provider_name, model in workers
        }


# ---------------------------------------------------------------------------
# TestFireWorkContributorRecord
# ---------------------------------------------------------------------------


class TestFireWorkContributorRecord:
    """_fire_work_contributor_record: non-blocking fire-and-forget."""

    def test_submits_to_thread_pool(self, tmp_path):
        """Must submit to _tick_pool, not call synchronously."""
        orch = _make_orchestrator(tmp_path)
        submitted = []
        original = orch._tick_pool.submit

        def tracking_submit(fn, *a, **kw):
            submitted.append((fn, a))
            return original(fn, *a, **kw)

        orch._tick_pool.submit = tracking_submit
        entry = _make_running_entry()
        orch._fire_work_contributor_record(entry)
        assert len(submitted) == 1
        fn, args = submitted[0]
        assert fn == orch._write_work_contributor_record
        assert args == (entry,)

    def test_does_not_block(self, tmp_path):
        """Returns immediately even if writing is slow."""
        orch = _make_orchestrator(tmp_path)
        done = threading.Event()
        started = threading.Event()

        def slow_write(entry):
            started.set()
            done.wait(timeout=5)

        orch._write_work_contributor_record = slow_write
        entry = _make_running_entry()
        import time
        t0 = time.monotonic()
        orch._fire_work_contributor_record(entry)
        elapsed = time.monotonic() - t0
        assert elapsed < 1.0, f"_fire_work_contributor_record blocked for {elapsed:.2f}s"
        done.set()

    def test_survives_pool_full_exception(self, tmp_path):
        """If submitting to the pool raises, it is logged but not propagated."""
        orch = _make_orchestrator(tmp_path)
        orch._tick_pool.submit = MagicMock(side_effect=RuntimeError("pool is shut down"))
        entry = _make_running_entry()
        # Must not raise
        orch._fire_work_contributor_record(entry)


# ---------------------------------------------------------------------------
# TestOnWorkerExitContributor
# ---------------------------------------------------------------------------


def _make_live_session_for_test() -> LiveSession:
    """Create a LiveSession with numeric token fields for test compatibility."""
    s = LiveSession(
        session_id="test",
        thread_id="t1",
        turn_id="0",
        agent_pid=None,
    )
    s.input_tokens = 0
    s.output_tokens = 0
    s.total_tokens = 0
    return s


class TestOnWorkerExitContributor:
    """Integration: _on_worker_exit fires contributor record only on normal exit."""

    def _make_orch_with_entry(self, tmp_path, issue_id="TASK-001"):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(issue_id)
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier=issue_id,
            issue=issue,
            session=_make_live_session_for_test(),
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
        )
        entry.provider_id = "prov-1"
        entry.provider_name = "TestProvider"
        entry.model_name = "test-model"
        entry.focus_name = "feature"
        orch.state.running[issue_id] = entry
        return orch, entry

    def test_normal_exit_fires_contributor_record(self, tmp_path):
        """Normal exit → contributor record written."""
        orch, entry = self._make_orch_with_entry(tmp_path)
        fire_calls: list = []
        orch._fire_work_contributor_record = lambda e: fire_calls.append(e)
        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = _make_issue("TASK-001", state="done")
        orch.tracker = mock_tracker

        asyncio.run(orch._on_worker_exit("TASK-001", "normal", None))
        assert len(fire_calls) == 1
        assert fire_calls[0] is entry

    def test_stalled_exit_does_not_fire_contributor_record(self, tmp_path):
        """Stalled exit → contributor record NOT written (partial run)."""
        orch, entry = self._make_orch_with_entry(tmp_path)
        fire_calls: list = []
        orch._fire_work_contributor_record = lambda e: fire_calls.append(e)

        asyncio.run(orch._on_worker_exit("TASK-001", "stalled", "no progress"))
        assert len(fire_calls) == 0

    def test_abnormal_exit_does_not_fire_contributor_record(self, tmp_path):
        """Abnormal (error) exit → contributor record NOT written."""
        orch, entry = self._make_orch_with_entry(tmp_path)
        fire_calls: list = []
        orch._fire_work_contributor_record = lambda e: fire_calls.append(e)

        asyncio.run(orch._on_worker_exit("TASK-001", "abnormal", "provider startup failed"))
        assert len(fire_calls) == 0

    def test_max_turns_exit_does_not_fire_contributor_record(self, tmp_path):
        """Max-turns exit → contributor record NOT written."""
        orch, entry = self._make_orch_with_entry(tmp_path)
        fire_calls: list = []
        orch._fire_work_contributor_record = lambda e: fire_calls.append(e)

        asyncio.run(orch._on_worker_exit("TASK-001", "max_turns", None))
        assert len(fire_calls) == 0

    def test_unknown_issue_id_no_crash(self, tmp_path):
        """Non-existent issue_id in running is a no-op."""
        orch = _make_orchestrator(tmp_path)
        fire_calls: list = []
        orch._fire_work_contributor_record = lambda e: fire_calls.append(e)

        asyncio.run(orch._on_worker_exit("nonexistent-id", "normal", None))
        assert len(fire_calls) == 0

    def test_retries_produce_separate_records(self, tmp_path):
        """Each retry attempt produces its own contributor record."""
        store: dict[str, dict] = {}
        orch = _make_orchestrator(tmp_path)
        mock_tracker = MagicMock()
        mock_tracker.get_metadata.side_effect = lambda id: store.get(id, {})
        mock_tracker.set_metadata_field.side_effect = (
            lambda id, k, v: store.setdefault(id, {}).__setitem__(k, v)
        )
        mock_tracker.fetch_issue_detail.return_value = _make_issue("TASK-001", state="Done")
        orch.tracker = mock_tracker

        issue = _make_issue("TASK-001")
        # Simulate two retries on the same issue
        for attempt, stem in enumerate(["attempt-1", "attempt-2"]):
            entry = RunningEntry(
                worker_task=MagicMock(),
                identifier="TASK-001",
                issue=issue,
                session=_make_live_session_for_test(),
                retry_attempt=attempt,
                started_at=datetime.now(timezone.utc),
            )
            entry.provider_id = "prov-1"
            entry.provider_name = "TestProvider"
            entry.model_name = "model-x"
            entry.focus_name = "feature"
            entry.agent_log_path = f"/logs/TASK-001__{stem}.jsonl"
            entry.run_id = f"dispatch-{stem}"
            orch.state.running["TASK-001"] = entry
            asyncio.run(orch._on_worker_exit("TASK-001", "normal", None))

        record = store.get("TASK-001", {}).get(METADATA_KEY)
        assert record is not None
        assert len(record["runs"]) == 2
        run_ids = {r["run_id"] for r in record["runs"]}
        assert run_ids == {
            contributor_run_identity("dispatch-attempt-1", "prov-1", "model-x"),
            contributor_run_identity("dispatch-attempt-2", "prov-1", "model-x"),
        }
