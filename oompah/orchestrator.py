"""Orchestrator: polling, dispatch, reconciliation, and retry management."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from oompah.agent import AgentError, AgentEvent, AgentSession
from oompah.api_agent import AgentActivity, ApiAgentSession
from oompah.config import ServiceConfig, WorkflowError, load_workflow, validate_dispatch_config
from oompah.models import (
    AgentProfile,
    AgentTotals,
    Issue,
    LiveSession,
    OrchestratorState,
    RetryEntry,
    RunningEntry,
)
from oompah.focus import analyze_completed_issue, save_suggestion, select_focus
from oompah.prompt import PromptError, build_continuation_prompt, render_prompt
from oompah.projects import ProjectError, ProjectStore
from oompah.providers import ProviderStore
from oompah.tracker import BeadsTracker, TrackerError
from oompah.workspace import WorkspaceError, WorkspaceManager

logger = logging.getLogger(__name__)


class Orchestrator:
    """Owns the poll tick, dispatch decisions, and in-memory runtime state."""

    def __init__(self, config: ServiceConfig, workflow_path: str,
                 provider_store: ProviderStore | None = None,
                 project_store: ProjectStore | None = None):
        self.config = config
        self.workflow_path = workflow_path
        self.provider_store = provider_store or ProviderStore()
        self.project_store = project_store or ProjectStore()
        self.state = OrchestratorState(
            poll_interval_ms=config.poll_interval_ms,
            max_concurrent_agents=config.max_concurrent_agents,
        )
        # Legacy single tracker (used when no projects configured)
        self.tracker = BeadsTracker(
            active_states=config.tracker_active_states,
            terminal_states=config.tracker_terminal_states,
        )
        # Per-project trackers, keyed by project_id
        self._project_trackers: dict[str, BeadsTracker] = {}
        self.workspace_mgr = WorkspaceManager(
            workspace_root=config.workspace_root,
            hooks={
                "after_create": config.hooks_after_create,
                "before_run": config.hooks_before_run,
                "after_run": config.hooks_after_run,
                "before_remove": config.hooks_before_remove,
            },
            hooks_timeout_ms=config.hooks_timeout_ms,
        )
        self._prompt_template: str = ""
        self._tick_task: asyncio.Task | None = None
        self._stopping = False
        self._paused = False
        self._observers: list[Any] = []
        self._activity_observers: list[Any] = []
        self._refresh_requested = asyncio.Event()

    def reload_config(self, config: ServiceConfig, prompt_template: str) -> None:
        """Apply new config and prompt template from workflow reload."""
        self.config = config
        self._prompt_template = prompt_template
        self.state.poll_interval_ms = config.poll_interval_ms
        self.state.max_concurrent_agents = config.max_concurrent_agents
        self.tracker = BeadsTracker(
            active_states=config.tracker_active_states,
            terminal_states=config.tracker_terminal_states,
        )
        # Clear cached per-project trackers so they pick up new state config
        self._project_trackers.clear()
        self.workspace_mgr = WorkspaceManager(
            workspace_root=config.workspace_root,
            hooks={
                "after_create": config.hooks_after_create,
                "before_run": config.hooks_before_run,
                "after_run": config.hooks_after_run,
                "before_remove": config.hooks_before_remove,
            },
            hooks_timeout_ms=config.hooks_timeout_ms,
        )
        logger.info("Config reloaded poll_interval_ms=%d max_agents=%d",
                     config.poll_interval_ms, config.max_concurrent_agents)

    def set_prompt_template(self, template: str) -> None:
        self._prompt_template = template

    def pause(self) -> None:
        """Pause: stop all running agents and prevent new dispatches."""
        self._paused = True
        # Terminate all running agents (keep workspaces for resume)
        asyncio.ensure_future(self._terminate_all_running())
        logger.info("Orchestrator paused — all agents stopped")
        self._notify_observers()

    async def _terminate_all_running(self) -> None:
        """Terminate all running agents without cleaning workspaces."""
        for issue_id in list(self.state.running.keys()):
            await self._terminate_running(issue_id, cleanup_workspace=False)
        self._notify_observers()

    def unpause(self) -> None:
        """Resume dispatching — agents will be re-dispatched on next tick."""
        self._paused = False
        logger.info("Orchestrator unpaused")
        self._refresh_requested.set()
        self._notify_observers()

    def _tracker_for_project(self, project_id: str) -> BeadsTracker:
        """Get or create a BeadsTracker for a project."""
        if project_id in self._project_trackers:
            return self._project_trackers[project_id]
        project = self.project_store.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")
        tracker = BeadsTracker(
            active_states=self.config.tracker_active_states,
            terminal_states=self.config.tracker_terminal_states,
            cwd=project.repo_path,
        )
        self._project_trackers[project_id] = tracker
        return tracker

    def _tracker_for_issue(self, issue: Issue) -> BeadsTracker:
        """Get the appropriate tracker for an issue (project-specific or legacy)."""
        if issue.project_id:
            return self._tracker_for_project(issue.project_id)
        return self.tracker

    @property
    def is_paused(self) -> bool:
        return self._paused

    def request_refresh(self) -> None:
        """Request an immediate poll+reconciliation cycle."""
        self._refresh_requested.set()

    async def startup_cleanup(self) -> None:
        """Remove workspaces/worktrees for issues in terminal states."""
        projects = self.project_store.list_all()
        if projects:
            for project in projects:
                try:
                    tracker = self._tracker_for_project(project.id)
                    terminal_issues = tracker.fetch_issues_by_states(
                        self.config.tracker_terminal_states
                    )
                    for issue in terminal_issues:
                        try:
                            self.project_store.remove_worktree(project.id, issue.identifier)
                            logger.info("Cleaned terminal worktree project=%s issue=%s",
                                        project.name, issue.identifier)
                        except Exception as exc:
                            logger.warning("Failed to clean worktree project=%s issue=%s error=%s",
                                           project.name, issue.identifier, exc)
                except (TrackerError, ProjectError) as exc:
                    logger.warning("Startup cleanup failed for project %s: %s", project.name, exc)
        else:
            try:
                terminal_issues = self.tracker.fetch_issues_by_states(
                    self.config.tracker_terminal_states
                )
                for issue in terminal_issues:
                    try:
                        self.workspace_mgr.remove_workspace(issue.identifier)
                        logger.info("Cleaned terminal workspace issue_identifier=%s",
                                    issue.identifier)
                    except Exception as exc:
                        logger.warning("Failed to clean workspace issue_identifier=%s error=%s",
                                       issue.identifier, exc)
            except TrackerError as exc:
                logger.warning("Startup terminal cleanup failed: %s", exc)

    async def run(self) -> None:
        """Main event loop: poll, dispatch, reconcile."""
        await self.startup_cleanup()
        logger.info("Orchestrator starting poll loop interval_ms=%d", self.state.poll_interval_ms)

        while not self._stopping:
            await self._tick()
            # Wait for either the poll interval or a refresh request
            try:
                await asyncio.wait_for(
                    self._refresh_requested.wait(),
                    timeout=self.state.poll_interval_ms / 1000.0,
                )
                self._refresh_requested.clear()
                logger.info("Refresh requested, running immediate tick")
            except asyncio.TimeoutError:
                pass

    async def stop(self) -> None:
        """Gracefully stop the orchestrator."""
        self._stopping = True
        # Terminate all running agents
        for issue_id, entry in list(self.state.running.items()):
            await self._terminate_running(issue_id, cleanup_workspace=False)
        # Cancel retry timers
        for issue_id, retry in list(self.state.retry_attempts.items()):
            if retry.timer_handle and not retry.timer_handle.done():
                retry.timer_handle.cancel()
        logger.info("Orchestrator stopped")

    async def _tick(self) -> None:
        """One poll-and-dispatch cycle."""
        # Part 1: Reconcile
        await self._reconcile()

        # Part 2: Validate config
        errors = validate_dispatch_config(self.config)
        if errors:
            logger.error("Dispatch validation failed: %s", "; ".join(errors))
            self._notify_observers()
            return

        # Part 3: Fetch candidates from all projects (and legacy tracker)
        candidates = self._fetch_all_candidates()

        # Part 4: Sort and dispatch
        sorted_issues = self._sort_for_dispatch(candidates)
        for issue in sorted_issues:
            if self._available_slots() <= 0:
                break
            if self._should_dispatch(issue):
                await self._dispatch(issue, attempt=None)

        # Part 5: Auto-archive closed issues older than 7 days
        self._auto_archive()

        self._notify_observers()

    def _fetch_all_candidates(self) -> list[Issue]:
        """Fetch candidate issues from all configured projects."""
        projects = self.project_store.list_all()
        if not projects:
            # No projects configured — use legacy tracker
            try:
                return self.tracker.fetch_candidate_issues()
            except TrackerError as exc:
                logger.error("Tracker fetch failed: %s", exc)
                return []

        all_candidates: list[Issue] = []
        for project in projects:
            try:
                tracker = self._tracker_for_project(project.id)
                issues = tracker.fetch_candidate_issues()
                for issue in issues:
                    issue.project_id = project.id
                all_candidates.extend(issues)
            except (TrackerError, ProjectError) as exc:
                logger.error("Fetch failed for project %s: %s", project.name, exc)
        return all_candidates

    def _available_slots(self) -> int:
        return max(self.state.max_concurrent_agents - len(self.state.running), 0)

    def _per_state_available(self, state: str) -> bool:
        normalized = state.strip().lower()
        limit = self.config.max_concurrent_agents_by_state.get(normalized)
        if limit is None:
            return True
        count = sum(
            1
            for e in self.state.running.values()
            if e.issue.state.strip().lower() == normalized
        )
        return count < limit

    def _should_dispatch(self, issue: Issue) -> bool:
        if self._paused:
            return False
        if not issue.id or not issue.identifier or not issue.title or not issue.state:
            return False
        state_norm = issue.state.strip().lower()
        if state_norm not in [s.strip().lower() for s in self.config.tracker_active_states]:
            return False
        if state_norm in [s.strip().lower() for s in self.config.tracker_terminal_states]:
            return False
        if issue.id in self.state.running:
            return False
        if issue.id in self.state.claimed:
            return False
        if self._available_slots() <= 0:
            return False
        if not self._per_state_available(issue.state):
            return False
        # Blocker rule for "open"/"todo" state
        if state_norm in ("open", "todo"):
            terminal_norms = {s.strip().lower() for s in self.config.tracker_terminal_states}
            for blocker in issue.blocked_by:
                if blocker.state and blocker.state.strip().lower() not in terminal_norms:
                    return False
        # Budget circuit breaker
        if not self._check_budget():
            if not self.state.budget_exceeded:
                self.state.budget_exceeded = True
                logger.warning("Budget limit exceeded (%.2f/%.2f), halting dispatch",
                             self.state.agent_totals.estimated_cost, self.config.budget_limit)
            return False
        return True

    def _sort_for_dispatch(self, issues: list[Issue]) -> list[Issue]:
        def sort_key(issue: Issue):
            pri = issue.priority if issue.priority is not None else 999
            created = issue.created_at or datetime.max.replace(tzinfo=timezone.utc)
            return (pri, created, issue.identifier)
        return sorted(issues, key=sort_key)

    def _match_agent_profile(self, issue: Issue) -> AgentProfile | None:
        """Select the best agent profile for an issue based on matching rules.

        Matching priority:
        1. Issue type match (e.g., bug -> specific profile)
        2. Keyword match in title/description
        3. Priority range match
        4. First profile with no constraints (default fallback)
        """
        profiles = self.config.agent_profiles
        if not profiles:
            return None

        title_lower = (issue.title or "").lower()
        desc_lower = (issue.description or "").lower()
        text = f"{title_lower} {desc_lower}"

        best = None
        best_score = -1

        for profile in profiles:
            score = 0

            # Issue type match
            if profile.issue_types:
                if issue.issue_type in profile.issue_types:
                    score += 10
                else:
                    continue  # type specified but doesn't match — skip

            # Keyword match
            if profile.keywords:
                matched = sum(1 for kw in profile.keywords if kw.lower() in text)
                if matched > 0:
                    score += matched * 5
                else:
                    if not profile.issue_types:
                        continue  # keywords specified but none matched and no type match

            # Priority range
            if profile.min_priority is not None or profile.max_priority is not None:
                pri = issue.priority if issue.priority is not None else 2
                if profile.min_priority is not None and pri < profile.min_priority:
                    continue
                if profile.max_priority is not None and pri > profile.max_priority:
                    continue
                score += 3

            # Default fallback (no constraints)
            if not profile.issue_types and not profile.keywords and profile.min_priority is None and profile.max_priority is None:
                score = 0  # lowest priority, but valid

            if score > best_score:
                best_score = score
                best = profile

        return best

    def _get_profile_by_name(self, name: str) -> AgentProfile | None:
        """Look up an agent profile by name."""
        for p in self.config.agent_profiles:
            if p.name == name:
                return p
        return None

    # Profile hierarchy for escalation (weakest to strongest).
    # Profiles not listed here won't be escalated to.
    _PROFILE_HIERARCHY = ["default", "quick", "standard", "deep"]

    def _escalate_profile(self, current_profile: AgentProfile | None,
                          issue: Issue) -> AgentProfile | None:
        """Return the next higher profile for an issue that keeps stalling.

        Escalation follows _PROFILE_HIERARCHY. Returns None if already at the
        top or if no higher profile exists in the config.
        """
        if not current_profile:
            return None

        hierarchy = self._PROFILE_HIERARCHY
        try:
            idx = hierarchy.index(current_profile.name)
        except ValueError:
            return None  # profile not in hierarchy, no escalation

        # Walk up the hierarchy looking for the next configured profile
        for higher_name in hierarchy[idx + 1:]:
            higher = self._get_profile_by_name(higher_name)
            if higher:
                return higher
        return None

    def _resolve_model(self, profile: AgentProfile, provider) -> str | None:
        """Resolve the model name from a profile and provider."""
        model = None
        if profile.model_role and provider.model_roles:
            model = provider.model_roles.get(profile.model_role)
        if not model:
            model = profile.model or provider.default_model or (provider.models[0] if provider.models else None)
        return model

    def _estimate_cost(self, profile: AgentProfile, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a session based on provider model costs, falling back to profile rates."""
        cost_in = profile.cost_per_1k_input
        cost_out = profile.cost_per_1k_output
        # Resolve costs from provider if available
        if profile.provider_id:
            provider = self.provider_store.get(profile.provider_id)
            if provider and provider.model_costs:
                model = self._resolve_model(profile, provider)
                if model:
                    pc_in, pc_out = provider.get_model_costs(model)
                    if pc_in or pc_out:
                        cost_in, cost_out = pc_in, pc_out
        return (input_tokens / 1000.0) * cost_in + \
               (output_tokens / 1000.0) * cost_out

    def _check_budget(self) -> bool:
        """Return True if within budget, False if budget exceeded."""
        if self.config.budget_limit <= 0:
            return True  # no budget limit set
        return self.state.agent_totals.estimated_cost < self.config.budget_limit

    def _post_comment(self, identifier: str, text: str, author: str = "oompah",
                      project_id: str | None = None) -> None:
        """Post a comment on an issue (best-effort, non-blocking)."""
        try:
            tracker = self._tracker_for_project(project_id) if project_id else self.tracker
            tracker.add_comment(identifier, text, author=author)
        except Exception as exc:
            logger.debug("Failed to post comment on %s: %s", identifier, exc)

    async def _dispatch(self, issue: Issue, attempt: int | None,
                        override_profile: str | None = None) -> None:
        """Dispatch a worker for an issue."""
        # Use escalated profile if provided, otherwise match normally
        if override_profile:
            profile = self._get_profile_by_name(override_profile)
            if not profile:
                profile = self._match_agent_profile(issue)
        else:
            profile = self._match_agent_profile(issue)
        profile_name = profile.name if profile else "default"

        logger.info(
            "Dispatching issue_id=%s issue_identifier=%s attempt=%s agent_profile=%s",
            issue.id,
            issue.identifier,
            attempt,
            profile_name,
        )
        self.state.claimed.add(issue.id)

        # Move issue to in_progress
        try:
            tracker = self._tracker_for_issue(issue)
            tracker.update_issue(issue.identifier, status="in_progress")
        except Exception as exc:
            logger.debug("Failed to set in_progress for %s: %s", issue.identifier, exc)

        # Remove from retry if present
        retry = self.state.retry_attempts.pop(issue.id, None)
        if retry and retry.timer_handle and not retry.timer_handle.done():
            retry.timer_handle.cancel()

        now = datetime.now(timezone.utc)
        worker_task = asyncio.create_task(
            self._run_worker(issue, attempt, profile),
            name=f"worker-{issue.identifier}",
        )

        self.state.running[issue.id] = RunningEntry(
            worker_task=worker_task,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=attempt or 0,
            started_at=now,
            agent_profile_name=profile_name,
        )

        if attempt and attempt > 1:
            self._post_comment(issue.identifier, f"Retrying (attempt #{attempt}, agent: {profile_name})",
                               project_id=issue.project_id)
        else:
            self._post_comment(issue.identifier, f"Agent dispatched (profile: {profile_name})",
                               project_id=issue.project_id)

        self._notify_observers()

    async def _run_worker(self, issue: Issue, attempt: int | None, profile: AgentProfile | None = None) -> None:
        """Worker: create workspace, build prompt, run agent turns."""
        # Route to API agent if profile has a provider_id
        if profile and profile.provider_id:
            provider = self.provider_store.get(profile.provider_id)
            if provider:
                await self._run_api_worker(issue, attempt, profile, provider)
                return
            else:
                logger.warning("Provider %s not found for profile %s, falling back to CLI",
                             profile.provider_id, profile.name)

        await self._run_cli_worker(issue, attempt, profile)

    async def _run_api_worker(self, issue: Issue, attempt: int | None, profile: AgentProfile, provider) -> None:
        """Worker using the OpenAI-compatible API agent."""
        exit_reason = "normal"
        error_msg = None
        max_turns = profile.max_turns if profile.max_turns else self.config.max_turns
        # Resolve model: role lookup → explicit model → provider default
        model = self._resolve_model(profile, provider)
        if not model:
            raise ValueError(f"No model resolved for profile {profile.name!r} with provider {provider.name}")
        if profile.model_role and provider.model_roles and profile.model_role not in provider.model_roles:
            logger.error("Model role %r not defined in provider %s (available roles: %s)",
                         profile.model_role, provider.name, ", ".join(provider.model_roles))
            raise ValueError(f"Model role {profile.model_role!r} not defined in provider {provider.name}")
        if provider.models and model not in provider.models:
            logger.error("Model %s not available in provider %s (available: %s)",
                         model, provider.name, ", ".join(provider.models))
            raise ValueError(f"Model {model} not available in provider {provider.name}")

        try:
            # Create workspace: use project worktree if available, else legacy
            if issue.project_id:
                workspace_path = self.project_store.create_worktree(
                    issue.project_id, issue.identifier)
            else:
                workspace = self.workspace_mgr.create_for_issue(issue.identifier)
                workspace_path = workspace.path
                self.workspace_mgr.run_before_run(workspace_path)

            # Select focus tailored to this issue
            focus = select_focus(issue)
            logger.info("Issue %s assigned focus: %s (%s)", issue.identifier, focus.name, focus.role)
            self._post_comment(issue.identifier, f"Focus: {focus.role}",
                               project_id=issue.project_id)

            # Fetch existing comments to kick-start agent context
            try:
                tracker = self._tracker_for_issue(issue)
                comments = tracker.fetch_comments(issue.identifier)
            except Exception:
                comments = []

            # Build prompt
            prompt = render_prompt(
                self._prompt_template, issue, attempt,
                comments=comments, focus_text=focus.render(),
            )

            session = ApiAgentSession(
                base_url=provider.base_url,
                api_key=provider.api_key,
                model=model,
                workspace_path=workspace_path,
                max_turns=max_turns,
                stall_turns=self.config.stall_turns,
                system_prompt="You are an autonomous coding agent. Use the provided tools to complete the task.",
            )

            # Update running entry with minimal session info
            if issue.id in self.state.running:
                self.state.running[issue.id].session = LiveSession(
                    session_id=f"api-{provider.name}-{model}",
                    thread_id="api",
                    turn_id="0",
                    agent_pid=None,
                    last_event="api_started",
                    last_timestamp=datetime.now(timezone.utc),
                    last_message=f"Using {provider.name}/{model}",
                )

            def _on_activity(activity_entry: AgentActivity) -> None:
                if issue.id in self.state.running:
                    self.state.running[issue.id].activity_log.append(activity_entry)
                    if self.state.running[issue.id].session:
                        self.state.running[issue.id].session.last_message = activity_entry.summary[:200]
                        self.state.running[issue.id].session.last_event = activity_entry.kind
                        self.state.running[issue.id].session.last_timestamp = datetime.now(timezone.utc)
                    # Broadcast activity entry to WS clients
                    self._notify_activity(issue.identifier, activity_entry)
                    self._notify_observers()

            def _is_cancelled() -> bool:
                """Check if this issue has been closed or removed from running."""
                if issue.id not in self.state.running:
                    return True
                try:
                    tracker = self._tracker_for_issue(issue)
                    refreshed = tracker.fetch_issue_states_by_ids([issue.id])
                    if refreshed:
                        state = refreshed[0].state.strip().lower()
                        terminal = {s.strip().lower() for s in self.config.tracker_terminal_states}
                        if state in terminal:
                            return True
                except Exception:
                    pass
                return False

            result = await session.run_task(prompt, on_activity=_on_activity,
                                            is_cancelled=_is_cancelled)

            # Update session with final token counts
            if issue.id in self.state.running and self.state.running[issue.id].session:
                s = self.state.running[issue.id].session
                s.input_tokens = result.input_tokens
                s.output_tokens = result.output_tokens
                s.total_tokens = result.total_tokens
                s.turn_count = result.turns
                s.last_message = result.last_message[:200]
                s.last_event = f"api_{result.status}"

            if result.status == "failed":
                exit_reason = "abnormal"
                error_msg = result.error or "API agent failed"
            elif result.status == "max_turns":
                exit_reason = "max_turns"
                logger.info("API agent reached max turns for %s", issue.identifier)
            elif result.status == "stalled":
                exit_reason = "stalled"
                error_msg = result.error
                logger.info("API agent stalled on %s: %s", issue.identifier, error_msg)

        except Exception as exc:
            exit_reason = "abnormal"
            error_msg = str(exc)
            logger.exception("API worker failed issue_id=%s", issue.id)
        finally:
            if not issue.project_id:
                try:
                    wp = self.workspace_mgr.workspace_path_for(issue.identifier)
                    self.workspace_mgr.run_after_run(wp)
                except Exception:
                    pass
            await self._on_worker_exit(issue.id, exit_reason, error_msg)

    async def _run_cli_worker(self, issue: Issue, attempt: int | None, profile: AgentProfile | None = None) -> None:
        """Worker using CLI subprocess (original behavior)."""
        exit_reason = "normal"
        error_msg = None
        agent_command = profile.command if profile else self.config.agent_command
        max_turns = profile.max_turns if profile and profile.max_turns else self.config.max_turns

        try:
            # Create workspace: use project worktree if available, else legacy
            if issue.project_id:
                workspace_path = self.project_store.create_worktree(
                    issue.project_id, issue.identifier)
            else:
                workspace = self.workspace_mgr.create_for_issue(issue.identifier)
                workspace_path = workspace.path
                self.workspace_mgr.run_before_run(workspace_path)

            # Start agent session
            session = AgentSession(
                command=agent_command,
                workspace_path=workspace_path,
                read_timeout_ms=self.config.read_timeout_ms,
                turn_timeout_ms=self.config.turn_timeout_ms,
            )
            await session.start()

            try:
                await session.initialize()
                await session.start_thread()

                # Update running entry with session info
                if issue.id in self.state.running:
                    self.state.running[issue.id].session = LiveSession(
                        session_id=session.session_id or "",
                        thread_id=session.thread_id or "",
                        turn_id=session.turn_id or "",
                        agent_pid=session.pid,
                        last_event=None,
                        last_timestamp=None,
                        last_message="",
                        input_tokens=0,
                        output_tokens=0,
                        total_tokens=0,
                        last_reported_input_tokens=0,
                        last_reported_output_tokens=0,
                        last_reported_total_tokens=0,
                        turn_count=0,
                    )

                current_issue = issue

                # Select focus tailored to this issue
                cli_focus = select_focus(issue)
                logger.info("Issue %s assigned focus: %s (%s)", issue.identifier, cli_focus.name, cli_focus.role)
                self._post_comment(issue.identifier, f"Focus: {cli_focus.role}",
                                   project_id=issue.project_id)

                # Fetch existing comments to kick-start agent context
                try:
                    tracker = self._tracker_for_issue(issue)
                    cli_comments = tracker.fetch_comments(issue.identifier)
                except Exception:
                    cli_comments = []

                for turn_number in range(1, max_turns + 1):
                    # Build prompt
                    if turn_number == 1:
                        prompt = render_prompt(
                            self._prompt_template, current_issue, attempt,
                            comments=cli_comments, focus_text=cli_focus.render(),
                        )
                    else:
                        prompt = build_continuation_prompt(
                            current_issue, turn_number, max_turns
                        )

                    # Start and stream turn
                    await session.start_turn(
                        prompt=prompt,
                        issue_identifier=current_issue.identifier,
                        issue_title=current_issue.title,
                    )

                    if issue.id in self.state.running and self.state.running[issue.id].session:
                        self.state.running[issue.id].session.turn_count = turn_number
                        self.state.running[issue.id].session.turn_id = session.turn_id or ""
                        self.state.running[issue.id].session.session_id = session.session_id or ""

                    def _on_event(event: AgentEvent) -> None:
                        self._handle_agent_event(issue.id, event)

                    status = await session.stream_turn(on_event=_on_event)

                    if status != "succeeded":
                        exit_reason = "abnormal"
                        error_msg = f"Turn ended with status: {status}"
                        break

                    # Re-check issue state for continuation
                    try:
                        tracker = self._tracker_for_issue(issue)
                        refreshed = tracker.fetch_issue_states_by_ids([issue.id])
                        if refreshed:
                            current_issue = refreshed[0]
                            current_issue.project_id = issue.project_id
                    except TrackerError:
                        break

                    active_norms = {s.strip().lower() for s in self.config.tracker_active_states}
                    if current_issue.state.strip().lower() not in active_norms:
                        break
                else:
                    # Loop completed without break — all turns used up
                    active_norms = {s.strip().lower() for s in self.config.tracker_active_states}
                    if current_issue.state.strip().lower() in active_norms:
                        exit_reason = "max_turns"
                        logger.info("CLI agent reached max turns for %s", issue.identifier)

            finally:
                await session.stop()

        except (WorkspaceError, AgentError, PromptError) as exc:
            exit_reason = "abnormal"
            error_msg = str(exc)
            logger.error(
                "Worker failed issue_id=%s issue_identifier=%s error=%s",
                issue.id,
                issue.identifier,
                exc,
            )
        except Exception as exc:
            exit_reason = "abnormal"
            error_msg = str(exc)
            logger.exception(
                "Worker unexpected error issue_id=%s issue_identifier=%s",
                issue.id,
                issue.identifier,
            )
        finally:
            if not issue.project_id:
                try:
                    wp = self.workspace_mgr.workspace_path_for(issue.identifier)
                    self.workspace_mgr.run_after_run(wp)
                except Exception:
                    pass

            # Report exit to orchestrator
            await self._on_worker_exit(issue.id, exit_reason, error_msg)

    def _handle_agent_event(self, issue_id: str, event: AgentEvent) -> None:
        """Update running entry with agent event data."""
        entry = self.state.running.get(issue_id)
        if not entry or not entry.session:
            return

        entry.session.last_event = event.event
        entry.session.last_timestamp = datetime.fromtimestamp(
            event.timestamp, tz=timezone.utc
        )
        entry.session.last_message = event.payload.get("message", "")
        entry.session.agent_pid = event.agent_pid

        # Update token counts from absolute totals
        if event.usage:
            new_input = event.usage.get("input_tokens", 0)
            new_output = event.usage.get("output_tokens", 0)
            new_total = event.usage.get("total_tokens", 0)

            # Track deltas for aggregate totals
            if new_total > 0:
                delta_input = max(0, new_input - entry.session.last_reported_input_tokens)
                delta_output = max(0, new_output - entry.session.last_reported_output_tokens)
                delta_total = max(0, new_total - entry.session.last_reported_total_tokens)

                entry.session.input_tokens += delta_input
                entry.session.output_tokens += delta_output
                entry.session.total_tokens += delta_total

                entry.session.last_reported_input_tokens = new_input
                entry.session.last_reported_output_tokens = new_output
                entry.session.last_reported_total_tokens = new_total

        # Update rate limits if present
        rate_limits = event.payload.get("rate_limits")
        if rate_limits:
            self.state.rate_limits = rate_limits

    async def _on_worker_exit(
        self, issue_id: str, reason: str, error: str | None
    ) -> None:
        """Handle worker completion."""
        entry = self.state.running.pop(issue_id, None)
        if not entry:
            return

        # Add runtime seconds to totals
        elapsed = (datetime.now(timezone.utc) - entry.started_at).total_seconds()
        self.state.agent_totals.seconds_running += elapsed

        # Add token totals and estimate cost
        if entry.session:
            self.state.agent_totals.input_tokens += entry.session.input_tokens
            self.state.agent_totals.output_tokens += entry.session.output_tokens
            self.state.agent_totals.total_tokens += entry.session.total_tokens

            # Estimate cost from agent profile
            profile = self._get_profile_by_name(entry.agent_profile_name)
            if profile:
                cost = self._estimate_cost(profile, entry.session.input_tokens, entry.session.output_tokens)
                self.state.agent_totals.estimated_cost += cost
                self.state.cost_by_profile[entry.agent_profile_name] = \
                    self.state.cost_by_profile.get(entry.agent_profile_name, 0.0) + cost

                # Reset circuit breaker if we're back under budget
                if self.state.budget_exceeded and self._check_budget():
                    self.state.budget_exceeded = False

        tokens_str = ""
        if entry.session and entry.session.total_tokens > 0:
            tokens_str = f" ({entry.session.total_tokens} tokens)"

        project_id = entry.issue.project_id if entry.issue else None

        if reason == "normal":
            self.state.completed.add(issue_id)
            self.state.claimed.discard(issue_id)
            self.state.stall_counts.pop(issue_id, None)
            self._post_comment(
                entry.identifier,
                f"Agent completed successfully in {elapsed:.0f}s{tokens_str}",
                project_id=project_id,
            )
            logger.info(
                "Worker completed normally issue_id=%s issue_identifier=%s",
                issue_id,
                entry.identifier,
            )
            # Analyze completed work against foci library
            self._analyze_focus_fit(entry.issue, project_id)
        elif reason in ("max_turns", "stalled"):
            next_attempt = (entry.retry_attempt or 0) + 1
            delay = self._backoff_delay(next_attempt)

            # Track stall count for escalation
            escalated = None
            if reason == "stalled":
                self.state.stall_counts[issue_id] = self.state.stall_counts.get(issue_id, 0) + 1
                stall_count = self.state.stall_counts[issue_id]
                # Check if we should escalate to a higher profile
                current_profile = self._get_profile_by_name(entry.agent_profile_name)
                escalated = self._escalate_profile(current_profile, entry.issue)
                if escalated:
                    msg = (f"Agent stalled {stall_count} time(s) ({elapsed:.0f}s{tokens_str}). "
                           f"Escalating from '{entry.agent_profile_name}' to '{escalated.name}'. "
                           f"Retrying in {delay // 1000}s (attempt #{next_attempt})")
                    logger.info("Escalating issue %s from profile %s to %s (stall_count=%d)",
                                entry.identifier, entry.agent_profile_name, escalated.name, stall_count)
                else:
                    msg = (f"Agent stalled — no productive actions (writes/commands) "
                           f"for {self.config.stall_turns} consecutive turns "
                           f"({elapsed:.0f}s{tokens_str}). "
                           f"Retrying in {delay // 1000}s (attempt #{next_attempt})")
            else:
                msg = (f"Agent hit safety turn limit ({elapsed:.0f}s{tokens_str}). "
                       f"Retrying in {delay // 1000}s (attempt #{next_attempt})")
            self._post_comment(entry.identifier, msg, project_id=project_id)
            self._schedule_retry(
                issue_id,
                attempt=next_attempt,
                identifier=entry.identifier,
                delay_ms=delay,
                error=error or reason,
                escalated_profile=escalated.name if reason == "stalled" and escalated else None,
            )
            logger.info(
                "Worker %s issue_id=%s issue_identifier=%s retrying_in_ms=%d",
                reason,
                issue_id,
                entry.identifier,
                delay,
            )
        else:
            next_attempt = (entry.retry_attempt or 0) + 1
            delay = self._backoff_delay(next_attempt)
            self._post_comment(
                entry.identifier,
                f"Agent failed: {error or 'unknown error'}. Retrying in {delay // 1000}s (attempt #{next_attempt})",
                project_id=project_id,
            )
            self._schedule_retry(
                issue_id,
                attempt=next_attempt,
                identifier=entry.identifier,
                delay_ms=delay,
                error=error,
            )
            logger.warning(
                "Worker failed issue_id=%s issue_identifier=%s error=%s retrying_in_ms=%d",
                issue_id,
                entry.identifier,
                error,
                delay,
            )

        self._notify_observers()

    def _backoff_delay(self, attempt: int) -> int:
        """Compute exponential backoff delay."""
        delay = min(10000 * (2 ** (attempt - 1)), self.config.max_retry_backoff_ms)
        return delay

    def _schedule_retry(
        self,
        issue_id: str,
        attempt: int,
        identifier: str,
        delay_ms: int,
        error: str | None,
        escalated_profile: str | None = None,
    ) -> None:
        """Schedule a retry timer for an issue."""
        # Cancel existing retry
        existing = self.state.retry_attempts.pop(issue_id, None)
        if existing and existing.timer_handle and not existing.timer_handle.done():
            existing.timer_handle.cancel()

        due_at_ms = time.monotonic() * 1000 + delay_ms

        loop = asyncio.get_event_loop()
        timer = loop.call_later(
            delay_ms / 1000.0,
            lambda: asyncio.create_task(self._on_retry_timer(issue_id)),
        )

        self.state.retry_attempts[issue_id] = RetryEntry(
            issue_id=issue_id,
            identifier=identifier,
            attempt=attempt,
            due_at_ms=due_at_ms,
            timer_handle=timer,
            error=error,
            escalated_profile=escalated_profile,
        )

    async def _on_retry_timer(self, issue_id: str) -> None:
        """Handle retry timer expiration."""
        retry = self.state.retry_attempts.pop(issue_id, None)
        if not retry:
            return

        try:
            candidates = self._fetch_all_candidates()
        except (TrackerError, ProjectError):
            # Requeue
            self._schedule_retry(
                issue_id,
                retry.attempt + 1,
                retry.identifier,
                self._backoff_delay(retry.attempt + 1),
                "retry poll failed",
            )
            return

        issue = next((i for i in candidates if i.id == issue_id), None)
        if issue is None:
            # Issue no longer active, release claim
            self.state.claimed.discard(issue_id)
            logger.info("Retry released claim issue_id=%s (no longer candidate)", issue_id)
            return

        if self._available_slots() <= 0:
            self._schedule_retry(
                issue_id,
                retry.attempt + 1,
                issue.identifier,
                self._backoff_delay(retry.attempt + 1),
                "no available orchestrator slots",
            )
            return

        await self._dispatch(issue, attempt=retry.attempt,
                             override_profile=retry.escalated_profile)

    async def _reconcile(self) -> None:
        """Reconcile running issues: stall detection + tracker state refresh."""
        # Part A: Stall detection
        if self.config.stall_timeout_ms > 0:
            now_mono = time.monotonic()
            for issue_id, entry in list(self.state.running.items()):
                last_ts = None
                if entry.session and entry.session.last_timestamp:
                    last_ts = entry.session.last_timestamp.timestamp()
                else:
                    last_ts = entry.started_at.timestamp()

                elapsed_ms = (time.time() - last_ts) * 1000
                if elapsed_ms > self.config.stall_timeout_ms:
                    logger.warning(
                        "Stall detected issue_id=%s issue_identifier=%s elapsed_ms=%.0f",
                        issue_id,
                        entry.identifier,
                        elapsed_ms,
                    )
                    await self._terminate_running(issue_id, cleanup_workspace=False)
                    next_attempt = (entry.retry_attempt or 0) + 1
                    self._schedule_retry(
                        issue_id,
                        next_attempt,
                        entry.identifier,
                        self._backoff_delay(next_attempt),
                        "stall timeout",
                    )

        # Part B: Tracker state refresh
        running_ids = list(self.state.running.keys())
        if not running_ids:
            return

        # Group running issues by project for targeted tracker queries
        refreshed_map: dict[str, Issue] = {}
        by_project: dict[str | None, list[str]] = {}
        for issue_id, entry in self.state.running.items():
            pid = entry.issue.project_id if entry.issue else None
            by_project.setdefault(pid, []).append(issue_id)

        for pid, ids in by_project.items():
            try:
                tracker = self._tracker_for_project(pid) if pid else self.tracker
                refreshed = tracker.fetch_issue_states_by_ids(ids)
                for issue in refreshed:
                    issue.project_id = pid
                    refreshed_map[issue.id] = issue
            except (TrackerError, ProjectError):
                logger.debug("Reconciliation refresh failed for project %s", pid)
        terminal_norms = {s.strip().lower() for s in self.config.tracker_terminal_states}
        active_norms = {s.strip().lower() for s in self.config.tracker_active_states}

        for issue_id in running_ids:
            if issue_id not in self.state.running:
                continue
            issue = refreshed_map.get(issue_id)
            if not issue:
                continue

            state_norm = issue.state.strip().lower()
            if state_norm in terminal_norms:
                logger.info(
                    "Reconcile: terminal state issue_id=%s state=%s",
                    issue_id,
                    issue.state,
                )
                await self._terminate_running(issue_id, cleanup_workspace=True)
            elif state_norm in active_norms:
                self.state.running[issue_id].issue = issue
            else:
                logger.info(
                    "Reconcile: non-active state issue_id=%s state=%s",
                    issue_id,
                    issue.state,
                )
                await self._terminate_running(issue_id, cleanup_workspace=False)

    _ARCHIVE_DAYS = 7

    def _analyze_focus_fit(self, issue: Issue, project_id: str | None) -> None:
        """Analyze a completed issue's work against existing foci.

        If no focus covers the work well, saves a suggestion for a new one.
        """
        try:
            tracker = self._tracker_for_issue(issue)
            comments = tracker.fetch_comments(issue.identifier)
        except Exception:
            return

        suggestion = analyze_completed_issue(issue, comments)
        if suggestion:
            save_suggestion(suggestion)
            logger.info(
                "Focus suggestion created for %s: '%s' (%s)",
                issue.identifier, suggestion.suggested_name, suggestion.suggested_role,
            )

    def _auto_archive(self) -> None:
        """Archive closed issues older than _ARCHIVE_DAYS days."""
        now = datetime.now(timezone.utc)
        projects = self.project_store.list_all()

        trackers: list[tuple[str | None, BeadsTracker]] = []
        if projects:
            for project in projects:
                try:
                    trackers.append((project.id, self._tracker_for_project(project.id)))
                except (ProjectError, TrackerError):
                    pass
        else:
            trackers.append((None, self.tracker))

        for pid, tracker in trackers:
            try:
                closed = tracker.fetch_issues_by_states(self.config.tracker_terminal_states)
                for issue in closed:
                    if tracker.is_archived(issue):
                        continue
                    if issue.closed_at and (now - issue.closed_at).days >= self._ARCHIVE_DAYS:
                        try:
                            tracker.archive_issue(issue.identifier)
                            logger.info("Auto-archived issue %s (closed %d days ago)",
                                        issue.identifier, (now - issue.closed_at).days)
                        except TrackerError as exc:
                            logger.debug("Failed to archive %s: %s", issue.identifier, exc)
            except (TrackerError, ProjectError) as exc:
                logger.debug("Auto-archive fetch failed for project %s: %s", pid, exc)

    async def _terminate_running(
        self, issue_id: str, cleanup_workspace: bool
    ) -> None:
        """Terminate a running worker and optionally clean its workspace."""
        entry = self.state.running.pop(issue_id, None)
        if not entry:
            return

        # Cancel the worker task
        if entry.worker_task and not entry.worker_task.done():
            entry.worker_task.cancel()
            try:
                await entry.worker_task
            except (asyncio.CancelledError, Exception):
                pass

        # Add runtime to totals
        elapsed = (datetime.now(timezone.utc) - entry.started_at).total_seconds()
        self.state.agent_totals.seconds_running += elapsed
        if entry.session:
            self.state.agent_totals.input_tokens += entry.session.input_tokens
            self.state.agent_totals.output_tokens += entry.session.output_tokens
            self.state.agent_totals.total_tokens += entry.session.total_tokens

        self.state.claimed.discard(issue_id)

        if cleanup_workspace:
            project_id = entry.issue.project_id if entry.issue else None
            try:
                if project_id:
                    self.project_store.remove_worktree(project_id, entry.identifier)
                else:
                    self.workspace_mgr.remove_workspace(entry.identifier)
            except Exception as exc:
                logger.warning(
                    "Workspace cleanup failed issue_identifier=%s error=%s",
                    entry.identifier,
                    exc,
                )

        logger.info(
            "Terminated running issue_id=%s issue_identifier=%s cleanup=%s",
            issue_id,
            entry.identifier,
            cleanup_workspace,
        )

    def get_snapshot(self) -> dict[str, Any]:
        """Return a snapshot of the current orchestrator state for the API."""
        now = datetime.now(timezone.utc)

        running_rows = []
        live_seconds = 0.0
        for issue_id, entry in self.state.running.items():
            elapsed = (now - entry.started_at).total_seconds()
            live_seconds += elapsed
            row: dict[str, Any] = {
                "issue_id": issue_id,
                "issue_identifier": entry.identifier,
                "project_id": entry.issue.project_id if entry.issue else None,
                "state": entry.issue.state,
                "started_at": entry.started_at.isoformat(),
                "agent_profile": entry.agent_profile_name,
                "turn_count": 0,
                "session_id": None,
                "last_event": None,
                "last_message": "",
                "last_event_at": None,
                "tokens": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            }
            if entry.session:
                row["session_id"] = entry.session.session_id
                row["turn_count"] = entry.session.turn_count
                row["last_event"] = entry.session.last_event
                row["last_message"] = entry.session.last_message
                row["last_event_at"] = (
                    entry.session.last_timestamp.isoformat()
                    if entry.session.last_timestamp
                    else None
                )
                row["tokens"] = {
                    "input_tokens": entry.session.input_tokens,
                    "output_tokens": entry.session.output_tokens,
                    "total_tokens": entry.session.total_tokens,
                }
            running_rows.append(row)

        retry_rows = []
        for issue_id, retry in self.state.retry_attempts.items():
            due_dt = datetime.fromtimestamp(
                retry.due_at_ms / 1000.0, tz=timezone.utc
            )
            retry_rows.append(
                {
                    "issue_id": issue_id,
                    "issue_identifier": retry.identifier,
                    "attempt": retry.attempt,
                    "due_at": due_dt.isoformat(),
                    "error": retry.error,
                }
            )

        totals = self.state.agent_totals
        return {
            "generated_at": now.isoformat(),
            "paused": self._paused,
            "counts": {
                "running": len(running_rows),
                "retrying": len(retry_rows),
            },
            "running": running_rows,
            "retrying": retry_rows,
            "agent_totals": {
                "input_tokens": totals.input_tokens,
                "output_tokens": totals.output_tokens,
                "total_tokens": totals.total_tokens,
                "seconds_running": totals.seconds_running + live_seconds,
                "estimated_cost": totals.estimated_cost,
            },
            "cost_by_profile": dict(self.state.cost_by_profile),
            "budget": {
                "limit": self.config.budget_limit,
                "spent": totals.estimated_cost,
                "exceeded": self.state.budget_exceeded,
            },
            "agent_profiles": [
                {
                    "name": p.name,
                    "command": p.command,
                    "provider_id": p.provider_id,
                    "model": p.model,
                    "model_role": p.model_role,
                }
                for p in self.config.agent_profiles
            ],
            "rate_limits": self.state.rate_limits,
            "projects": [p.to_dict() for p in self.project_store.list_all()],
        }

    def get_issue_detail(self, issue_identifier: str) -> dict[str, Any] | None:
        """Return detailed state for a specific issue."""
        # Search running
        for issue_id, entry in self.state.running.items():
            if entry.identifier == issue_identifier:
                snapshot_entry = None
                if entry.session:
                    snapshot_entry = {
                        "session_id": entry.session.session_id,
                        "turn_count": entry.session.turn_count,
                        "state": entry.issue.state,
                        "started_at": entry.started_at.isoformat(),
                        "last_event": entry.session.last_event,
                        "last_message": entry.session.last_message,
                        "last_event_at": (
                            entry.session.last_timestamp.isoformat()
                            if entry.session.last_timestamp
                            else None
                        ),
                        "tokens": {
                            "input_tokens": entry.session.input_tokens,
                            "output_tokens": entry.session.output_tokens,
                            "total_tokens": entry.session.total_tokens,
                        },
                    }
                return {
                    "issue_identifier": entry.identifier,
                    "issue_id": issue_id,
                    "status": "running",
                    "workspace": {
                        "path": self.workspace_mgr.workspace_path_for(entry.identifier),
                    },
                    "running": snapshot_entry,
                    "retry": None,
                }

        # Search retry queue
        for issue_id, retry in self.state.retry_attempts.items():
            if retry.identifier == issue_identifier:
                due_dt = datetime.fromtimestamp(
                    retry.due_at_ms / 1000.0, tz=timezone.utc
                )
                return {
                    "issue_identifier": retry.identifier,
                    "issue_id": issue_id,
                    "status": "retrying",
                    "workspace": {
                        "path": self.workspace_mgr.workspace_path_for(retry.identifier),
                    },
                    "running": None,
                    "retry": {
                        "attempt": retry.attempt,
                        "due_at": due_dt.isoformat(),
                        "error": retry.error,
                    },
                }

        return None

    def _notify_observers(self) -> None:
        """Notify any registered observers of state changes."""
        for observer in self._observers:
            try:
                observer(self.get_snapshot())
            except Exception:
                pass

    def _notify_activity(self, identifier: str, entry: Any) -> None:
        """Notify observers of a specific agent activity entry."""
        for observer in self._activity_observers:
            try:
                observer(identifier, entry)
            except Exception:
                pass
