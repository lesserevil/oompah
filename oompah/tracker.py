"""Issue tracker client using beads (bd) for oompah."""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone

from oompah.models import BlockerRef, Issue

logger = logging.getLogger(__name__)


class TrackerError(Exception):
    """Raised when tracker operations fail."""


class BeadsTracker:
    """Issue tracker client backed by the bd (beads) CLI."""

    def __init__(
        self,
        active_states: list[str],
        terminal_states: list[str],
        cwd: str | None = None,
    ):
        self.active_states = [s.strip().lower() for s in active_states]
        self.terminal_states = [s.strip().lower() for s in terminal_states]
        self.cwd = cwd

    def fetch_candidate_issues(self) -> list[Issue]:
        """Fetch issues in active states, sorted for dispatch."""
        issues: list[Issue] = []
        seen_ids: set[str] = set()

        for status in self.active_states:
            try:
                raw_list = self._run_bd(["list", f"--status={status}", "--json"])
            except TrackerError:
                # Try without --status filter and filter manually
                try:
                    raw_list = self._run_bd(["list", "--json"])
                except TrackerError as exc:
                    logger.error("Failed to fetch candidates: %s", exc)
                    raise

            if isinstance(raw_list, list):
                for raw in raw_list:
                    issue = self._normalize_issue(raw)
                    if issue.id not in seen_ids:
                        state_norm = issue.state.strip().lower()
                        if state_norm in self.active_states:
                            issues.append(issue)
                            seen_ids.add(issue.id)

        # Sort: priority ascending (None last), created_at oldest first, identifier
        def sort_key(issue: Issue):
            pri = issue.priority if issue.priority is not None else 999
            created = issue.created_at or datetime.max.replace(tzinfo=timezone.utc)
            return (pri, created, issue.identifier)

        return sorted(issues, key=sort_key)

    def fetch_all_issues(self) -> list[Issue]:
        """Fetch all issues regardless of state."""
        all_raw: list[dict] = []
        for status_filter in [None, "closed", "deferred", "blocked", "pinned"]:
            try:
                args = ["list", "--json"]
                if status_filter:
                    args = ["list", f"--status={status_filter}", "--json"]
                result = self._run_bd(args)
                if isinstance(result, list):
                    all_raw.extend(result)
            except TrackerError:
                pass

        seen: set[str] = set()
        issues: list[Issue] = []
        for raw in all_raw:
            issue = self._normalize_issue(raw)
            if issue.id not in seen:
                issues.append(issue)
                seen.add(issue.id)
        return issues

    def create_issue(
        self,
        title: str,
        issue_type: str = "task",
        description: str | None = None,
        priority: int | None = None,
    ) -> Issue:
        """Create a new issue via bd create and return the normalized Issue."""
        args = ["create", f"--title={title}", f"--type={issue_type}", "--json"]
        if description:
            args.append(f"--description={description}")
        if priority is not None:
            args.append(f"--priority={priority}")
        raw = self._run_bd(args)
        if isinstance(raw, dict):
            return self._normalize_issue(raw)
        raise TrackerError("Unexpected response from bd create")

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> dict:
        """Add a comment to an issue."""
        raw = self._run_bd([
            "comments", "add", identifier, text,
            f"--author={author}", "--json",
        ])
        if isinstance(raw, dict):
            return raw
        return {}

    def fetch_comments(self, identifier: str) -> list[dict]:
        """Fetch all comments for an issue."""
        try:
            raw = self._run_bd(["comments", identifier, "--json"])
            if isinstance(raw, list):
                return raw
        except TrackerError:
            pass
        return []

    def add_parent_child(self, child_id: str, parent_id: str) -> None:
        """Link a child issue to a parent epic."""
        self._run_bd(["dep", "add", child_id, parent_id, "--type", "parent-child"])

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        """Fetch a single issue with full detail including parent info."""
        try:
            raw = self._run_bd(["show", identifier, "--json"])
            if isinstance(raw, list) and raw:
                return self._normalize_issue(raw[0])
            if isinstance(raw, dict):
                return self._normalize_issue(raw)
        except TrackerError:
            pass
        return None

    def fetch_children(self, epic_id: str) -> list[Issue]:
        """Fetch children of an epic."""
        try:
            raw = self._run_bd(["show", epic_id, "--children", "--json"])
            if isinstance(raw, dict):
                # Returns {epic_id: [children...]}
                children_raw = raw.get(epic_id, [])
                return [self._normalize_issue(r) for r in children_raw]
            if isinstance(raw, list):
                return [self._normalize_issue(r) for r in raw]
        except TrackerError:
            pass
        return []

    def fetch_all_issues_enriched(self) -> list[Issue]:
        """Fetch all issues with parent info from bd show --json."""
        all_issues = self.fetch_all_issues()
        # For each issue, we need parent info. bd show returns it.
        enriched: list[Issue] = []
        for issue in all_issues:
            try:
                raw = self._run_bd(["show", issue.id, "--json"])
                if isinstance(raw, list) and raw:
                    enriched.append(self._normalize_issue(raw[0]))
                elif isinstance(raw, dict):
                    enriched.append(self._normalize_issue(raw))
                else:
                    enriched.append(issue)
            except TrackerError:
                enriched.append(issue)
        return enriched

    def update_issue(self, identifier: str, **fields: str) -> None:
        """Update an issue's fields via bd update."""
        args = ["update", identifier]
        for key, value in fields.items():
            args.append(f"--{key}={value}")
        self._run_bd(args)

    def close_issue(self, identifier: str) -> None:
        """Close an issue via bd close."""
        self._run_bd(["close", identifier])

    def reopen_issue(self, identifier: str) -> None:
        """Reopen a closed issue by setting status to open."""
        self._run_bd(["update", identifier, "--status=open"])

    def fetch_issues_by_states(self, state_names: list[str]) -> list[Issue]:
        """Fetch issues in specified states (used for terminal cleanup)."""
        if not state_names:
            return []

        normalized = {s.strip().lower() for s in state_names}
        try:
            raw_list = self._run_bd(["list", "--json"])
        except TrackerError as exc:
            logger.warning("Failed to fetch issues by states: %s", exc)
            raise

        issues = []
        if isinstance(raw_list, list):
            for raw in raw_list:
                issue = self._normalize_issue(raw)
                if issue.state.strip().lower() in normalized:
                    issues.append(issue)

        return issues

    def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[Issue]:
        """Fetch current state for specific issue IDs."""
        issues: list[Issue] = []

        for issue_id in issue_ids:
            try:
                raw = self._run_bd(["show", issue_id, "--json"])
                if isinstance(raw, dict):
                    issues.append(self._normalize_issue(raw))
            except TrackerError as exc:
                logger.warning(
                    "Failed to fetch issue state issue_id=%s error=%s",
                    issue_id,
                    exc,
                )

        return issues

    def _run_bd(self, args: list[str]) -> dict | list:
        """Run a bd command and parse JSON output."""
        cmd = ["bd"] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.cwd,
            )
        except FileNotFoundError:
            raise TrackerError("bd command not found. Is beads installed?")
        except subprocess.TimeoutExpired:
            raise TrackerError(f"bd command timed out: {' '.join(cmd)}")

        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise TrackerError(
                f"bd command failed (exit {result.returncode}): {stderr}"
            )

        stdout = result.stdout.strip()
        if not stdout:
            return []

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise TrackerError(f"Failed to parse bd JSON output: {exc}")

    def _normalize_issue(self, raw: dict) -> Issue:
        """Normalize a raw beads issue dict to the Issue model."""
        # Handle various beads field names
        issue_id = str(raw.get("id", raw.get("issue_id", "")))
        identifier = str(raw.get("identifier", raw.get("id", "")))
        title = str(raw.get("title", ""))
        description = raw.get("description")
        state = str(raw.get("status", raw.get("state", "open")))

        # Priority: beads uses 0-4 integers
        priority = raw.get("priority")
        if priority is not None:
            try:
                priority = int(priority)
            except (ValueError, TypeError):
                priority = None

        # Labels
        labels_raw = raw.get("labels", [])
        if isinstance(labels_raw, list):
            labels = [str(l).lower() for l in labels_raw]
        else:
            labels = []

        # Blocked by
        blocked_by: list[BlockerRef] = []
        blockers_raw = raw.get("blocked_by", raw.get("dependencies", []))
        if isinstance(blockers_raw, list):
            for b in blockers_raw:
                if isinstance(b, dict):
                    blocked_by.append(
                        BlockerRef(
                            id=b.get("id"),
                            identifier=b.get("identifier"),
                            state=b.get("state", b.get("status")),
                        )
                    )
                elif isinstance(b, str):
                    blocked_by.append(BlockerRef(id=b, identifier=b))

        # Timestamps
        created_at = _parse_timestamp(raw.get("created_at"))
        updated_at = _parse_timestamp(raw.get("updated_at"))

        issue_type = str(raw.get("issue_type", raw.get("type", "task")))
        parent_id = raw.get("parent")

        return Issue(
            id=issue_id,
            identifier=identifier,
            title=title,
            description=description,
            priority=priority,
            state=state,
            issue_type=issue_type,
            parent_id=parent_id,
            branch_name=raw.get("branch_name"),
            url=raw.get("url"),
            labels=labels,
            blocked_by=blocked_by,
            created_at=created_at,
            updated_at=updated_at,
        )


def _parse_timestamp(value) -> datetime | None:
    """Parse an ISO-8601 timestamp string."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        s = str(value)
        # Handle various ISO formats
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
