"""Tests for TASK-407.10 — per-project provider whitelist.

Covers:
  - Project model: provider_whitelist field default, to_dict, from_dict round-trip
  - ProjectStore.update(): validation and persistence of provider_whitelist
  - Orchestrator._apply_project_provider_whitelist(): filtering logic
  - Orchestrator._run_worker(): whitelist blocks all candidates → error, not CLI fallback
  - Server PATCH API: provider_whitelist field accepted/validated/returned

Acceptance criteria verified:
  AC1  Project records support an optional provider whitelist field, persisted through
       create/update/load/save round trips.
  AC2  Empty/unset whitelist leaves behavior unchanged.
  AC3  Non-empty whitelist filters role candidates to only whitelisted providers.
  AC4  All-candidates-filtered → clear warning, no agent started.
  AC5  Filtering happens before the preflight / startup loop.
  AC6  API allows viewing and editing the whitelist as a list of provider names.
  AC7  Tests cover default-unset, single-provider, multi-provider, all-filtered,
       persistence/API behavior.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from oompah.config import ServiceConfig
from oompah.models import AgentProfile, Issue, ModelProvider, Project, RunningEntry
from oompah.orchestrator import DispatchTarget, Orchestrator
from oompah.projects import ProjectError, ProjectStore
from oompah.roles import Candidate, RoleStore


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_project(
    *,
    pid: str = "proj-1",
    name: str = "myproject",
    provider_whitelist: list[str] | None = None,
) -> Project:
    """Create a minimal Project for testing."""
    return Project(
        id=pid,
        name=name,
        repo_url="https://github.com/org/repo.git",
        repo_path=f"/tmp/repos/{name}",
        branch="main",
        provider_whitelist=provider_whitelist or [],
    )


def _make_provider(
    *,
    pid: str = "p1",
    name: str = "TestProv",
    api_key: str = "sk-test",
    models: list[str] | None = None,
    mode: str = "api",
) -> ModelProvider:
    return ModelProvider(
        id=pid,
        name=name,
        base_url="http://test.example.com/v1",
        api_key=api_key,
        models=models or ["gpt-4o"],
        default_model=(models or ["gpt-4o"])[0],
        mode=mode,
        billing_model="subscription" if mode == "acp" else "per_token",
    )


def _make_issue(
    identifier: str = "TEST-1",
    project_id: str | None = "proj-1",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="Test issue — enough text to pass the empty-description gate.",
        state="open",
        issue_type="task",
        priority=2,
        labels=[],
        project_id=project_id,
    )


def _make_target(
    *,
    provider: ModelProvider,
    model: str | None = None,
    role_name: str = "fast",
    index: int = 0,
) -> DispatchTarget:
    m = model or (provider.models[0] if provider.models else "")
    return DispatchTarget(
        role_name=role_name,
        provider=provider,
        model=m,
        candidate_key=f"{provider.id}/{m}",
        source=f"role:{role_name}[{index}]",
        candidate=Candidate(provider_id=provider.id, model=m),
    )


def _make_orchestrator(tmp_path, projects: list[Project] | None = None) -> Orchestrator:
    """Create a minimal orchestrator with mocked project_store.

    Note: ``projects`` is referenced by the mock, not copied.  All items in
    the list at call time AND added later are visible to the mock via the
    shared reference.
    """
    # Use the same list object so tests can add projects after construction.
    project_list: list[Project] = projects if projects is not None else []
    project_store = MagicMock()
    project_store.list_all.return_value = project_list
    project_store.get.side_effect = lambda pid: next(
        (p for p in project_list if p.id == pid), None
    )
    role_store = RoleStore(path=str(tmp_path / "roles.json"))
    orch = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=role_store,
        state_path=str(tmp_path / "state.json"),
    )
    orch._fetch_in_progress_issues = MagicMock(return_value=[])
    return orch


def _make_project_store(tmp_path) -> ProjectStore:
    """Create a ProjectStore with a pre-loaded project."""
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "wt"),
    )
    p = _make_project()
    store._projects[p.id] = p
    store._save()
    return store


# ===========================================================================
# AC1: Project model — default, to_dict, from_dict round-trip
# ===========================================================================


class TestProjectModel:
    """Project dataclass field tests."""

    def test_default_whitelist_is_empty_list(self):
        p = _make_project()
        assert p.provider_whitelist == []

    def test_to_dict_includes_provider_whitelist_empty(self):
        p = _make_project()
        d = p.to_dict()
        assert "provider_whitelist" in d
        assert d["provider_whitelist"] == []

    def test_to_dict_includes_provider_whitelist_values(self):
        p = _make_project(provider_whitelist=["claude", "openai"])
        d = p.to_dict()
        assert d["provider_whitelist"] == ["claude", "openai"]

    def test_from_dict_reads_provider_whitelist(self):
        d = {
            "id": "proj-abc",
            "name": "proj",
            "repo_url": "https://example.com/repo.git",
            "repo_path": "/tmp/repo",
            "provider_whitelist": ["claude", "codex"],
        }
        p = Project.from_dict(d)
        assert p.provider_whitelist == ["claude", "codex"]

    def test_from_dict_missing_whitelist_defaults_empty(self):
        d = {
            "id": "proj-abc",
            "name": "proj",
            "repo_url": "https://example.com/repo.git",
            "repo_path": "/tmp/repo",
        }
        p = Project.from_dict(d)
        assert p.provider_whitelist == []

    def test_from_dict_null_whitelist_defaults_empty(self):
        d = {
            "id": "proj-abc",
            "name": "proj",
            "repo_url": "https://example.com/repo.git",
            "repo_path": "/tmp/repo",
            "provider_whitelist": None,
        }
        p = Project.from_dict(d)
        assert p.provider_whitelist == []

    def test_round_trip_preserves_whitelist(self):
        p = _make_project(provider_whitelist=["bar", "baz"])
        p2 = Project.from_dict(p.to_dict())
        assert p2.provider_whitelist == ["bar", "baz"]

    def test_round_trip_empty_whitelist(self):
        p = _make_project()
        p2 = Project.from_dict(p.to_dict())
        assert p2.provider_whitelist == []

    def test_from_dict_strips_blank_entries(self):
        d = {
            "id": "proj-abc",
            "name": "proj",
            "repo_url": "https://example.com/repo.git",
            "repo_path": "/tmp/repo",
            "provider_whitelist": ["  claude  ", "", "  ", "openai"],
        }
        p = Project.from_dict(d)
        assert "claude" in p.provider_whitelist
        assert "openai" in p.provider_whitelist
        assert "" not in p.provider_whitelist

    def test_to_safe_dict_includes_provider_whitelist(self):
        p = _make_project(provider_whitelist=["prov-x"])
        d = p.to_safe_dict()
        assert d["provider_whitelist"] == ["prov-x"]


# ===========================================================================
# AC1/AC2: ProjectStore.update() — persistence and validation
# ===========================================================================


class TestProjectStoreWhitelist:
    """ProjectStore.update() whitelist field tests."""

    @pytest.fixture(autouse=True)
    def store(self, tmp_path):
        self.store = _make_project_store(tmp_path)
        return self.store

    def test_update_provider_whitelist_single(self):
        updated = self.store.update("proj-1", provider_whitelist=["claude"])
        assert updated is not None
        assert updated.provider_whitelist == ["claude"]

    def test_update_provider_whitelist_multi(self):
        updated = self.store.update("proj-1", provider_whitelist=["claude", "openai"])
        assert updated.provider_whitelist == ["claude", "openai"]

    def test_update_provider_whitelist_empty_list(self):
        self.store.update("proj-1", provider_whitelist=["claude"])
        updated = self.store.update("proj-1", provider_whitelist=[])
        assert updated.provider_whitelist == []

    def test_update_provider_whitelist_null_resets_to_empty(self):
        self.store.update("proj-1", provider_whitelist=["claude"])
        updated = self.store.update("proj-1", provider_whitelist=None)
        assert updated.provider_whitelist == []

    def test_update_provider_whitelist_persists_to_disk(self, tmp_path):
        self.store.update("proj-1", provider_whitelist=["my-provider"])
        store2 = ProjectStore(
            path=self.store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        proj = store2.get("proj-1")
        assert proj is not None
        assert proj.provider_whitelist == ["my-provider"]

    def test_update_provider_whitelist_strips_blank_entries(self):
        updated = self.store.update("proj-1", provider_whitelist=["claude", "", "  "])
        assert updated.provider_whitelist == ["claude"]

    def test_update_provider_whitelist_rejects_non_string_entries(self):
        with pytest.raises(ProjectError, match="entries must be strings"):
            self.store.update("proj-1", provider_whitelist=[123])

    def test_update_provider_whitelist_rejects_non_list(self):
        with pytest.raises(ProjectError, match="must be a list"):
            self.store.update("proj-1", provider_whitelist="claude")

    def test_existing_project_without_whitelist_unaffected(self, tmp_path):
        """Existing projects that don't set provider_whitelist behave as before."""
        store2 = ProjectStore(
            path=self.store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        proj = store2.get("proj-1")
        assert proj.provider_whitelist == []


# ===========================================================================
# AC2/AC3/AC4: _apply_project_provider_whitelist() unit tests
# ===========================================================================


class TestApplyProjectProviderWhitelist:
    """Unit tests for Orchestrator._apply_project_provider_whitelist()."""

    def test_no_whitelist_returns_all_targets_unchanged(self, tmp_path):
        """AC2: Empty whitelist leaves all targets available."""
        p = _make_project(provider_whitelist=[])
        orch = _make_orchestrator(tmp_path, projects=[p])
        prov_a = _make_provider(pid="p-a", name="alice")
        prov_b = _make_provider(pid="p-b", name="bob")
        targets = [_make_target(provider=prov_a), _make_target(provider=prov_b)]
        issue = _make_issue(project_id=p.id)

        filtered, was_applied = orch._apply_project_provider_whitelist(targets, issue)
        assert filtered == targets
        assert was_applied is False

    def test_single_whitelist_entry_includes_matching(self, tmp_path):
        """AC3: Single whitelist entry keeps matching provider."""
        p = _make_project(provider_whitelist=["alice"])
        orch = _make_orchestrator(tmp_path, projects=[p])
        prov_a = _make_provider(pid="p-a", name="alice")
        prov_b = _make_provider(pid="p-b", name="bob")
        targets = [_make_target(provider=prov_a), _make_target(provider=prov_b)]
        issue = _make_issue(project_id=p.id)

        filtered, was_applied = orch._apply_project_provider_whitelist(targets, issue)
        assert len(filtered) == 1
        assert filtered[0].provider.name == "alice"
        assert was_applied is True

    def test_single_whitelist_entry_excludes_non_matching(self, tmp_path):
        """AC3: Single whitelist entry excludes non-whitelisted providers."""
        p = _make_project(provider_whitelist=["alice"])
        orch = _make_orchestrator(tmp_path, projects=[p])
        prov_b = _make_provider(pid="p-b", name="bob")
        targets = [_make_target(provider=prov_b)]
        issue = _make_issue(project_id=p.id)

        filtered, was_applied = orch._apply_project_provider_whitelist(targets, issue)
        assert filtered == []
        assert was_applied is True

    def test_multi_whitelist_keeps_multiple_matching(self, tmp_path):
        """AC3: Multiple whitelist entries keep all matching providers."""
        p = _make_project(provider_whitelist=["alice", "charlie"])
        orch = _make_orchestrator(tmp_path, projects=[p])
        prov_a = _make_provider(pid="p-a", name="alice")
        prov_b = _make_provider(pid="p-b", name="bob")
        prov_c = _make_provider(pid="p-c", name="charlie")
        targets = [
            _make_target(provider=prov_a, index=0),
            _make_target(provider=prov_b, index=1),
            _make_target(provider=prov_c, index=2),
        ]
        issue = _make_issue(project_id=p.id)

        filtered, was_applied = orch._apply_project_provider_whitelist(targets, issue)
        names = [t.provider.name for t in filtered]
        assert "alice" in names
        assert "charlie" in names
        assert "bob" not in names
        assert was_applied is True

    def test_all_filtered_returns_empty_with_flag(self, tmp_path):
        """AC4: All candidates filtered → empty list, was_applied=True."""
        p = _make_project(provider_whitelist=["nonexistent"])
        orch = _make_orchestrator(tmp_path, projects=[p])
        prov_a = _make_provider(pid="p-a", name="alice")
        targets = [_make_target(provider=prov_a)]
        issue = _make_issue(project_id=p.id)

        filtered, was_applied = orch._apply_project_provider_whitelist(targets, issue)
        assert filtered == []
        assert was_applied is True

    def test_no_project_id_returns_unchanged(self, tmp_path):
        """Issue with no project_id is not filtered."""
        orch = _make_orchestrator(tmp_path, projects=[])
        prov_a = _make_provider(pid="p-a", name="alice")
        targets = [_make_target(provider=prov_a)]
        issue = _make_issue(project_id=None)

        filtered, was_applied = orch._apply_project_provider_whitelist(targets, issue)
        assert filtered == targets
        assert was_applied is False

    def test_unknown_project_returns_unchanged(self, tmp_path):
        """Unknown project_id (not in store) → no filter applied."""
        orch = _make_orchestrator(tmp_path, projects=[])
        prov_a = _make_provider(pid="p-a", name="alice")
        targets = [_make_target(provider=prov_a)]
        issue = _make_issue(project_id="does-not-exist")

        filtered, was_applied = orch._apply_project_provider_whitelist(targets, issue)
        assert filtered == targets
        assert was_applied is False

    def test_preserves_candidate_order(self, tmp_path):
        """Whitelist filtering preserves the order of matching targets."""
        p = _make_project(provider_whitelist=["charlie", "alice"])
        orch = _make_orchestrator(tmp_path, projects=[p])
        prov_a = _make_provider(pid="p-a", name="alice")
        prov_b = _make_provider(pid="p-b", name="bob")
        prov_c = _make_provider(pid="p-c", name="charlie")
        # Order in targets: alice, bob, charlie
        targets = [
            _make_target(provider=prov_a, index=0),
            _make_target(provider=prov_b, index=1),
            _make_target(provider=prov_c, index=2),
        ]
        issue = _make_issue(project_id=p.id)

        filtered, _ = orch._apply_project_provider_whitelist(targets, issue)
        # bob excluded, alice and charlie kept in original order
        assert [t.provider.name for t in filtered] == ["alice", "charlie"]

    def test_all_filtered_logs_warning(self, tmp_path, caplog):
        """AC4: All-filtered case logs a WARNING with project name and whitelist."""
        p = _make_project(provider_whitelist=["absent-provider"])
        orch = _make_orchestrator(tmp_path, projects=[p])
        prov_a = _make_provider(pid="p-a", name="alice")
        targets = [_make_target(provider=prov_a)]
        issue = _make_issue(project_id=p.id)

        with caplog.at_level(logging.WARNING, logger="oompah.orchestrator"):
            orch._apply_project_provider_whitelist(targets, issue)

        assert any(
            "whitelist" in r.message.lower() or "provider" in r.message.lower()
            for r in caplog.records
        ), "Expected a warning about whitelist filtering"

    def test_empty_targets_with_nonempty_whitelist(self, tmp_path):
        """Empty target list + non-empty whitelist → empty list, was_applied=True."""
        p = _make_project(provider_whitelist=["alice"])
        orch = _make_orchestrator(tmp_path, projects=[p])
        issue = _make_issue(project_id=p.id)

        filtered, was_applied = orch._apply_project_provider_whitelist([], issue)
        assert filtered == []
        assert was_applied is True

    def test_empty_targets_with_empty_whitelist(self, tmp_path):
        """Empty target list + empty whitelist → empty list, was_applied=False."""
        p = _make_project(provider_whitelist=[])
        orch = _make_orchestrator(tmp_path, projects=[p])
        issue = _make_issue(project_id=p.id)

        filtered, was_applied = orch._apply_project_provider_whitelist([], issue)
        assert filtered == []
        assert was_applied is False


# ===========================================================================
# AC4: _run_worker() — all candidates filtered → error, no CLI fallback
# ===========================================================================


def _make_blocking_orchestrator(
    tmp_path, project: Project, extra_providers: list[ModelProvider] | None = None
) -> Orchestrator:
    """Orchestrator that returns the given project; _on_worker_exit is mocked."""
    orch = _make_orchestrator(tmp_path, projects=[project])
    orch._on_worker_exit = AsyncMock()
    for prov in extra_providers or []:
        orch.provider_store._providers[prov.id] = prov
    return orch


def _register_running(orch: Orchestrator, issue: Issue) -> None:
    """Add issue to state.running (required for _on_worker_exit to be called)."""
    orch.state.running[issue.id] = RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        agent_profile_name="standard",
    )


class TestRunWorkerWhitelistBlocking:
    """Integration tests: _run_worker() with whitelist that blocks all candidates."""

    def test_all_filtered_calls_on_worker_exit_with_error(self, tmp_path):
        """AC4: When whitelist filters all candidates, _on_worker_exit is called."""
        project = _make_project(provider_whitelist=["whitelisted-only"])
        prov = _make_provider(pid="other", name="not-whitelisted")
        orch = _make_blocking_orchestrator(tmp_path, project, [prov])
        orch._run_api_worker = AsyncMock()

        profile = AgentProfile(
            name="standard",
            command="claude",
            provider_id=prov.id,
            mode="api",
        )
        issue = _make_issue(project_id=project.id)
        _register_running(orch, issue)

        asyncio.run(orch._run_worker(issue, attempt=1, profile=profile))

        orch._on_worker_exit.assert_awaited_once()
        args = orch._on_worker_exit.call_args[0]
        assert args[0] == issue.id
        assert args[1] != "normal"

    def test_all_filtered_error_message_mentions_whitelist(self, tmp_path):
        """AC4: Error message mentions the whitelist to help operators debug."""
        project = _make_project(provider_whitelist=["whitelisted-only"])
        prov = _make_provider(pid="other", name="not-whitelisted")
        orch = _make_blocking_orchestrator(tmp_path, project, [prov])
        orch._run_api_worker = AsyncMock()

        profile = AgentProfile(
            name="standard",
            command="claude",
            provider_id=prov.id,
            mode="api",
        )
        issue = _make_issue(project_id=project.id)
        _register_running(orch, issue)

        asyncio.run(orch._run_worker(issue, attempt=1, profile=profile))

        args = orch._on_worker_exit.call_args[0]
        error_msg = args[2] if len(args) > 2 else ""
        assert "whitelist" in error_msg.lower(), (
            f"Expected 'whitelist' in error message, got: {error_msg!r}"
        )

    def test_all_filtered_does_not_fall_through_to_cli(self, tmp_path):
        """AC4: Whitelist-blocked dispatch must NOT fall through to CLI."""
        project = _make_project(provider_whitelist=["whitelisted-only"])
        prov = _make_provider(pid="other", name="not-whitelisted")
        orch = _make_blocking_orchestrator(tmp_path, project, [prov])
        orch._run_api_worker = AsyncMock()
        orch._run_cli_worker = AsyncMock()

        profile = AgentProfile(
            name="standard",
            command="claude",
            provider_id=prov.id,
            mode="api",
        )
        issue = _make_issue(project_id=project.id)
        _register_running(orch, issue)

        asyncio.run(orch._run_worker(issue, attempt=1, profile=profile))

        # Neither _run_api_worker nor _run_cli_worker should have been called
        orch._run_api_worker.assert_not_awaited()
        orch._run_cli_worker.assert_not_awaited()

    def test_no_whitelist_does_not_block_dispatch(self, tmp_path):
        """AC2: No whitelist → dispatch proceeds normally."""
        project = _make_project(provider_whitelist=[])
        prov = _make_provider(pid="p1", name="my-provider")
        orch = _make_blocking_orchestrator(tmp_path, project, [prov])
        orch._run_api_worker = AsyncMock()

        profile = AgentProfile(
            name="standard",
            command="claude",
            provider_id=prov.id,
            mode="api",
        )
        issue = _make_issue(project_id=project.id)
        _register_running(orch, issue)

        asyncio.run(orch._run_worker(issue, attempt=1, profile=profile))

        # _run_api_worker should have been called (dispatch proceeded)
        orch._run_api_worker.assert_awaited_once()
        # _on_worker_exit should NOT have been called due to whitelist
        orch._on_worker_exit.assert_not_awaited()


# ===========================================================================
# AC3: Whitelist allows subset — non-whitelisted provider is not tried
# ===========================================================================


class TestWhitelistSubsetFiltering:
    """When whitelist only allows provider-B, provider-A is excluded."""

    def test_non_whitelisted_provider_is_not_dispatched(self, tmp_path):
        """Profile pointing to non-whitelisted provider → whitelist blocks dispatch."""
        project = _make_project(provider_whitelist=["provider-b"])
        prov_a = _make_provider(pid="pa", name="provider-a")
        orch = _make_blocking_orchestrator(tmp_path, project, [prov_a])
        orch._run_api_worker = AsyncMock()
        orch._run_cli_worker = AsyncMock()

        # Profile points to provider-a; whitelist only allows provider-b
        profile = AgentProfile(
            name="standard",
            command="claude",
            provider_id=prov_a.id,
            mode="api",
        )
        issue = _make_issue(project_id=project.id)
        _register_running(orch, issue)

        asyncio.run(orch._run_worker(issue, attempt=1, profile=profile))

        # _on_worker_exit called (whitelist blocked all)
        orch._on_worker_exit.assert_awaited_once()
        # Neither api nor cli worker should run
        orch._run_api_worker.assert_not_awaited()
        orch._run_cli_worker.assert_not_awaited()

    def test_whitelisted_candidate_is_dispatched(self, tmp_path):
        """When two providers exist and only one is whitelisted, that one runs."""
        project = _make_project(provider_whitelist=["provider-b"])
        prov_b = _make_provider(pid="pb", name="provider-b")
        orch = _make_blocking_orchestrator(tmp_path, project, [prov_b])
        orch._run_api_worker = AsyncMock()

        profile = AgentProfile(
            name="standard",
            command="claude",
            provider_id=prov_b.id,
            mode="api",
        )
        issue = _make_issue(project_id=project.id)
        _register_running(orch, issue)

        asyncio.run(orch._run_worker(issue, attempt=1, profile=profile))

        # _run_api_worker should be called (prov_b is whitelisted)
        orch._run_api_worker.assert_awaited_once()
        # _on_worker_exit should NOT have been called
        orch._on_worker_exit.assert_not_awaited()


# ===========================================================================
# AC6: Server API — provider_whitelist field in PATCH and GET
# ===========================================================================


class TestServerApiWhitelist:
    """Server PATCH/GET API tests for provider_whitelist field."""

    @pytest.fixture(autouse=True)
    def _patch_server(self, tmp_path):
        """Patch the global orchestrator used by the server."""
        from oompah import server
        from fastapi.testclient import TestClient
        from oompah.server import app

        project = _make_project()
        store = _make_project_store(tmp_path)
        store._projects.clear()
        store._projects[project.id] = project
        store._save()

        orch = MagicMock()
        orch.project_store = store
        orch._observers = []
        orch._state_only_observers = []
        orch._activity_observers = []
        orch.get_snapshot.return_value = {"counts": {}, "running": {}}

        old_orch = server._orchestrator
        server._orchestrator = orch
        self.client = TestClient(app)
        self.project = project
        self.store = store
        yield
        server._orchestrator = old_orch

    def test_patch_sets_provider_whitelist(self):
        """PATCH with provider_whitelist passes list to store."""
        res = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"provider_whitelist": ["claude", "openai"]},
        )
        assert res.status_code == 200
        body = res.json()
        assert "provider_whitelist" in body
        assert body["provider_whitelist"] == ["claude", "openai"]
        # Also verify in the store
        assert self.store.get(self.project.id).provider_whitelist == ["claude", "openai"]

    def test_patch_clears_provider_whitelist_with_empty_list(self):
        """PATCH with empty list clears the whitelist."""
        self.store.update(self.project.id, provider_whitelist=["claude"])
        res = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"provider_whitelist": []},
        )
        assert res.status_code == 200
        assert res.json()["provider_whitelist"] == []

    def test_patch_clears_provider_whitelist_with_null(self):
        """PATCH with null clears the whitelist."""
        self.store.update(self.project.id, provider_whitelist=["claude"])
        res = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"provider_whitelist": None},
        )
        assert res.status_code == 200
        assert res.json()["provider_whitelist"] == []

    def test_patch_rejects_non_list_provider_whitelist(self):
        """PATCH with non-list value for provider_whitelist returns 400."""
        res = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"provider_whitelist": "claude"},
        )
        assert res.status_code == 400
        body = res.json()
        assert "provider_whitelist" in body["error"]["message"]

    def test_patch_rejects_list_with_non_strings(self):
        """PATCH with a list containing non-strings returns 400."""
        res = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"provider_whitelist": [123, "claude"]},
        )
        assert res.status_code == 400

    def test_get_project_includes_provider_whitelist_empty(self):
        """GET /api/v1/projects/{id} includes provider_whitelist field."""
        res = self.client.get(f"/api/v1/projects/{self.project.id}")
        assert res.status_code == 200
        body = res.json()
        assert "provider_whitelist" in body
        assert body["provider_whitelist"] == []

    def test_get_project_includes_provider_whitelist_values(self):
        """GET includes non-empty provider_whitelist."""
        self.store.update(self.project.id, provider_whitelist=["my-provider"])
        res = self.client.get(f"/api/v1/projects/{self.project.id}")
        assert res.status_code == 200
        body = res.json()
        assert body["provider_whitelist"] == ["my-provider"]

    def test_patch_multiple_providers_in_whitelist(self):
        """PATCH with multiple providers in whitelist."""
        res = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"provider_whitelist": ["provider-a", "provider-b", "provider-c"]},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["provider_whitelist"] == ["provider-a", "provider-b", "provider-c"]
