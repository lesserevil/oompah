"""I/O collectors for immutable, project-scoped workflow evidence.

Pure evidence models live in :mod:`oompah.workflow_fact_model` and remain
re-exported here so existing callers keep the original import surface.
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from oompah.models import BlockerRef, Issue
from oompah.statuses import DONE, canonicalize_status
from oompah.tracker import TrackerProtocol
from oompah.workflow_fact_model import (
    LANDING_FACT_SCHEMA_VERSION,
    REQUIRED_FACT_DOMAINS,
    WORKFLOW_FACTS_SCHEMA_VERSION,
    CollectedValue,
    FactDomain,
    FactObservation,
    FactState,
    LandingFact,
    LandingProofKind,
    LandingRequest,
    LandingState,
    WorkflowFacts,
    _GIT_REVISION_RE,
    _now_iso,
    _optional_text,
    _parse_time,
    _render_time,
    _required_text,
)


@runtime_checkable
class IntegrationQueueProtocol(Protocol):
    """Narrow queue-store surface needed for integration fact overlay."""

    def get(self, project_id: str, task_id: str) -> Any | None:
        """Return one queue row or None if the task is not queued."""
        ...


def _git_error_code(stderr: str) -> str:
    text = stderr.lower()
    if "timed out" in text:
        return "git_observation_timed_out"
    if "not a git repository" in text or "repository unavailable" in text:
        return "git_repository_unavailable"
    if "permission denied" in text:
        return "git_permission_denied"
    return "git_observation_failed"


class GitLandingCollector:
    """Collect target-specific landing facts from real Git evidence."""

    def __init__(
        self,
        repo_path: str | os.PathLike[str],
        *,
        project_id: str,
        clock: Callable[[], datetime] | None = None,
        command_timeout_seconds: float = 30.0,
        target_refresher: Callable[[str], str | None] | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.project_id = _required_text(project_id, "project_id")
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.command_timeout_seconds = max(float(command_timeout_seconds), 0.1)
        self._target_refresher = target_refresher
        self._observation_state = threading.local()

    @contextmanager
    def observation_scope(self):
        """Share exact target observations within one reconciliation attempt.

        Runtime reconciliation evaluates tasks serially from one
        generation-bound tracker cut. Re-fetching the same remote target for
        every task adds latency without creating a more coherent authority
        cut. The cache is thread-local and scoped to one world attempt so
        concurrent workers and later reconciliations still refresh their own
        target evidence.
        """

        previous = getattr(self._observation_state, "target_evidence", None)
        self._observation_state.target_evidence = {}
        try:
            yield
        finally:
            if previous is None:
                try:
                    del self._observation_state.target_evidence
                except AttributeError:
                    pass
            else:
                self._observation_state.target_evidence = previous

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        command = ["git", *args]
        try:
            return subprocess.run(
                command,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.command_timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(
                command,
                124,
                stdout="",
                stderr="git observation timed out",
            )
        except OSError as exc:
            return subprocess.CompletedProcess(
                command,
                128,
                stdout="",
                stderr=f"git repository unavailable: {type(exc).__name__}",
            )

    def _resolve(self, ref: str) -> tuple[str | None, str | None]:
        candidates = (ref, f"refs/heads/{ref}", f"refs/remotes/origin/{ref}")
        last_error = ""
        for candidate in candidates:
            result = self._run("rev-parse", "--verify", f"{candidate}^{{commit}}")
            if result.returncode == 0:
                return result.stdout.strip().lower(), None
            last_error = result.stderr
        return None, _git_error_code(last_error)

    @staticmethod
    def _matching_prior(
        prior: LandingFact | None,
        *,
        source: str,
        target: str,
        revision: str | None,
        project_id: str,
    ) -> LandingFact | None:
        if (
            prior
            and prior.state is LandingState.LANDED
            and prior.durable
            and prior.source == source
            and prior.target == target
            and prior.project_id == project_id
            and (revision is None or prior.revision == revision)
        ):
            return prior
        return None

    def _prior_target_is_current(
        self,
        prior: LandingFact,
        *,
        target_revision: str | None,
    ) -> bool:
        """Return whether current target history still contains prior proof.

        A durable fact survives source-ref pruning and normal target advances;
        it is not permission to ignore a force-push that removed the landing.
        The target must remain observable: a missing target is
        indistinguishable from deletion during a rewrite and therefore fails
        closed until Git can prove the target history again.
        """

        if target_revision is None:
            return False
        proven_target = str(prior.proof.get("target_sha") or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{7,64}", proven_target):
            # External durable evidence may not expose a Git target SHA.  It
            # remains authoritative for a pruned immutable source; arbitrary
            # or malformed proof kinds do not receive that exception.
            return str(prior.proof.get("kind") or "") in {
                LandingProofKind.FORGE_MERGE.value,
                LandingProofKind.MERGE_COMMIT.value,
                LandingProofKind.TERMINAL_AUDIT.value,
            }
        if proven_target == target_revision:
            return True
        result = self._run(
            "merge-base", "--is-ancestor", proven_target, target_revision
        )
        return result.returncode == 0

    def collect_many(
        self, requests: Sequence[LandingRequest]
    ) -> tuple[LandingFact, ...]:
        """Collect a batch while refreshing each authoritative target once.

        Enforce-mode runtime wiring supplies ``target_refresher``.  A refresh
        failure is evidence unavailability, never permission to fall back to
        a possibly stale local target branch.  A ``None`` result deliberately
        means that authoritative refresh is disabled (off/shadow mode).
        """

        scoped_target_evidence = getattr(
            self._observation_state, "target_evidence", None
        )
        target_evidence: dict[str, tuple[str | None, str | None] | None] = {}
        for request in requests:
            if not request.authoritative_target or self._target_refresher is None:
                continue
            if request.target in target_evidence:
                continue
            if (
                scoped_target_evidence is not None
                and request.target in scoped_target_evidence
            ):
                target_evidence[request.target] = scoped_target_evidence[
                    request.target
                ]
                continue
            try:
                revision = self._target_refresher(request.target)
                if revision is None:
                    target_evidence[request.target] = None
                else:
                    normalized = str(revision).strip().lower()
                    if not _GIT_REVISION_RE.fullmatch(normalized):
                        raise ValueError(
                            "target refresh returned an invalid revision"
                        )
                    target_evidence[request.target] = (normalized, None)
            except Exception as exc:  # noqa: BLE001 - remote evidence boundary
                target_evidence[request.target] = (
                    None,
                    f"target_refresh_{type(exc).__name__.lower()}",
                )
            if scoped_target_evidence is not None:
                scoped_target_evidence[request.target] = target_evidence[
                    request.target
                ]
        return tuple(
            self._collect(request, target_evidence.get(request.target))
            for request in requests
        )

    def collect(self, request: LandingRequest) -> LandingFact:
        return self.collect_many((request,))[0]

    def _collect(
        self,
        request: LandingRequest,
        authoritative_target: tuple[str | None, str | None] | None = None,
    ) -> LandingFact:
        observed_at = _render_time(self._clock())
        source = _required_text(request.source, "source")
        target = _required_text(request.target, "target")
        requested_revision = _optional_text(request.revision)
        trusted_target_revision = _optional_text(request.trusted_target_revision)
        # Resolve the live ref first. Callers identify mutable epic sources
        # whose persisted review head is only fallback evidence after pruning;
        # exact child revisions keep their immutable requested identity.
        if request.prefer_live_source or requested_revision is None:
            live_revision, live_error = self._resolve(source)
        else:
            # An exact immutable revision is the requested authority and the
            # live mutable ref is deliberately ignored below. Avoid three
            # redundant rev-parse subprocesses before verifying that object.
            live_revision, live_error = None, None
        if request.prefer_live_source and live_revision is not None:
            source_revision = live_revision
            source_error = live_error
        elif requested_revision:
            source_result = self._run(
                "cat-file", "-e", f"{requested_revision}^{{commit}}"
            )
            source_revision = (
                requested_revision.lower() if source_result.returncode == 0 else None
            )
            source_error = _git_error_code(source_result.stderr)
        else:
            source_revision, source_error = live_revision, live_error
        if authoritative_target is None:
            target_revision, target_error = self._resolve(target)
        else:
            target_revision, target_error = authoritative_target
        # An epic's own mutable source opts into live-tip binding so an older
        # review cannot bless later commits.  Exact child revisions retain
        # their immutable identity even when a shared container ref advances.
        # An explicit immutable revision remains the authority fence even when
        # its object is not available locally yet.  Treating an unresolved
        # revision as ``None`` would make ``_matching_prior`` wildcard the
        # revision and could let an older durable landing authorize newer work.
        effective_revision = source_revision or requested_revision
        verified_trusted_target = None
        if target_revision is None and trusted_target_revision is not None:
            target_result = self._run(
                "cat-file", "-e", f"{trusted_target_revision}^{{commit}}"
            )
            if target_result.returncode == 0:
                verified_trusted_target = trusted_target_revision
        prior = self._matching_prior(
            request.prior,
            source=source,
            target=target,
            revision=effective_revision,
            project_id=self.project_id,
        )

        # A matching durable positive is historical evidence, not a cache of
        # the current ref layout.  Preserve it after source pruning and while
        # the target retains the proven history.  A target rewrite that drops
        # that history must invalidate the old proof.
        if prior is not None and self._prior_target_is_current(
            prior,
            target_revision=target_revision or verified_trusted_target,
        ):
            return LandingFact(
                source,
                target,
                prior.revision,
                prior.proof,
                observed_at,
                self.project_id,
                state=LandingState.LANDED,
                durable=True,
            )

        # A terminal parent can prune its mutable epic ref after its exact
        # accepted head becomes immutable lifecycle evidence.  When that
        # object is independently present, prove fresh ancestry or the full
        # patch set against it below.  Missing/malformed trusted objects still
        # fail closed, as do all requests without this explicit authority.
        if (
            request.authoritative_target
            and target_revision is None
            and verified_trusted_target is not None
        ):
            target_revision = verified_trusted_target
            target_error = None
        if authoritative_target is not None and target_revision is None:
            return LandingFact(
                source,
                target,
                source_revision or requested_revision,
                {"kind": LandingProofKind.TARGET_UNAVAILABLE.value},
                observed_at,
                self.project_id,
                state=LandingState.UNKNOWN,
                error_code=target_error or "target_refresh_failed",
            )

        if source_revision is None:
            return LandingFact(
                source,
                target,
                requested_revision,
                {"kind": LandingProofKind.SOURCE_UNAVAILABLE.value},
                observed_at,
                self.project_id,
                state=LandingState.UNKNOWN,
                error_code=source_error,
            )
        if target_revision is None:
            return LandingFact(
                source,
                target,
                source_revision,
                {"kind": LandingProofKind.TARGET_UNAVAILABLE.value},
                observed_at,
                self.project_id,
                state=LandingState.UNKNOWN,
                error_code=target_error,
            )

        result = self._run(
            "merge-base", "--is-ancestor", source_revision, target_revision
        )
        proof_base = {
            "source_sha": source_revision,
            "target_sha": target_revision,
        }
        if result.returncode == 0:
            return LandingFact(
                source,
                target,
                source_revision,
                {"kind": LandingProofKind.GIT_ANCESTRY.value, **proof_base},
                observed_at,
                self.project_id,
                state=LandingState.LANDED,
                durable=True,
            )
        if result.returncode == 1:
            # A rebase or squash changes ancestry while preserving the full
            # patch set.  ``git cherry`` emits one ``-`` line per source patch
            # that has an equivalent patch on the target; requiring every
            # source patch to match prevents a tip-only proof from hiding a
            # missing commit.  This is durable evidence and remains useful
            # after the source ref is pruned.
            equivalent = self._run("cherry", target_revision, source_revision)
            cherry_lines = [
                line.strip()
                for line in equivalent.stdout.splitlines()
                if line.strip()
            ]
            if (
                equivalent.returncode == 0
                and cherry_lines
                and all(line.startswith("- ") for line in cherry_lines)
            ):
                return LandingFact(
                    source,
                    target,
                    source_revision,
                    {
                        "kind": LandingProofKind.PATCH_ID.value,
                        **proof_base,
                        "patches": len(cherry_lines),
                    },
                    observed_at,
                    self.project_id,
                    state=LandingState.LANDED,
                    durable=True,
                )
            return LandingFact(
                source,
                target,
                source_revision,
                {"kind": LandingProofKind.NOT_ANCESTOR.value, **proof_base},
                observed_at,
                self.project_id,
                state=LandingState.NOT_LANDED,
            )
        return LandingFact(
            source,
            target,
            source_revision,
            {"kind": LandingProofKind.OBSERVATION_ERROR.value, **proof_base},
            observed_at,
            self.project_id,
            state=LandingState.UNKNOWN,
            error_code=_git_error_code(result.stderr),
        )


FactSource = Callable[[Issue], FactObservation | CollectedValue | Any]


def _owner_delivery_landings(
    observation: FactObservation,
    requests: Sequence[LandingRequest],
    *,
    project_id: str,
    task_id: str,
    observed_at: str,
) -> tuple[LandingFact, ...]:
    """Project one already-authorized exact delivery as a landing fact."""

    value = observation.value if observation.state is FactState.KNOWN else None
    if not isinstance(value, Mapping):
        return ()
    raw = value.get("owner_delivery")
    if not isinstance(raw, Mapping) or raw.get("schema_version") != 1:
        return ()
    if raw.get("project_id") != project_id or raw.get("task_id") != task_id:
        return ()
    revision = str(raw.get("revision") or "").strip().lower()
    source = str(raw.get("source") or "").strip()
    target = str(raw.get("target") or "").strip()
    override_id = str(raw.get("override_id") or "").strip()
    fingerprint = str(raw.get("evidence_fingerprint") or "").strip().lower()
    selected_ref = str(raw.get("selected_ref") or "").strip()
    authorized_by = str(raw.get("authorized_by") or "").strip()
    if (
        not _GIT_REVISION_RE.fullmatch(revision)
        or not source
        or not target
        or not override_id
        or not re.fullmatch(r"[0-9a-f]{64}", fingerprint)
        or not selected_ref
        or not authorized_by
    ):
        return ()
    matching = next(
        (
            request
            for request in requests
            if request.source == source
            and request.target == target
            and request.revision == revision
        ),
        None,
    )
    if matching is None:
        return ()
    return (
        LandingFact(
            matching.source,
            matching.target,
            matching.revision,
            {
                "kind": LandingProofKind.TERMINAL_AUDIT.value,
                "authority": "project_owner_delivery",
                "override_id": override_id,
                "evidence_fingerprint": fingerprint,
                "selected_ref": selected_ref,
                "authorized_by": authorized_by,
            },
            observed_at,
            project_id,
            state=LandingState.LANDED,
            durable=True,
        ),
    )


def _integration_value(issue: Issue) -> Any:
    integration = issue.integration
    if integration is None:
        return None
    if hasattr(integration, "to_dict"):
        value = integration.to_dict()
    elif isinstance(integration, Mapping):
        value = dict(integration)
    else:
        value = {
            key: getattr(integration, key, None)
            for key in (
                "version",
                "state",
                "attempts",
                "task_branch",
                "base_branch",
                "head_sha",
                "base_sha",
                "submitted_at",
            )
        }
    # Delivery mode is service authority, not caller-controlled tracker text.
    # Children normally use the ordered epic queue.  The service may reclassify
    # an exact child generation after its parent landed; that typed record is
    # standalone authority only while its explicit target matches its base.
    # Synthetic mappings cannot opt into this exception.
    parent_id = str(getattr(issue, "parent_id", "") or "").strip()
    carried_mode = str(getattr(integration, "mode", "") or "").strip().lower()
    carried_base = str(getattr(integration, "base_branch", "") or "").strip()
    explicit_target = str(getattr(issue, "target_branch", "") or "").strip()
    parent_standalone = bool(
        parent_id
        and carried_mode == "standalone"
        and str(
            getattr(integration, "post_landed_parent_id", "") or ""
        ).strip()
        == parent_id
        and explicit_target
        and carried_base == explicit_target
    )
    value["mode"] = (
        "queue"
        if parent_id and not parent_standalone
        else (
            carried_mode
            if carried_mode in {"queue", "standalone"}
            else "standalone"
        )
    )
    return value


def _task_value(
    issue: Issue,
    *,
    parent: Issue | None = None,
    parent_error: str | None = None,
) -> dict[str, Any]:
    value = {
        "id": issue.id,
        "identifier": issue.identifier,
        "status": canonicalize_status(issue.state),
        "issue_type": issue.issue_type,
        "parent_id": issue.parent_id,
        "project_id": issue.project_id,
        "work_branch": issue.work_branch,
        "target_branch": issue.target_branch,
        "assignment_id": issue.assignment_id,
        "head_sha": issue.head_sha,
        # Review metadata is part of the task authority snapshot.  Keeping it
        # in the facts (rather than consulting mutable tracker text during a
        # transition) is what lets a merged review be compared with the exact
        # head that was recorded when it was opened.
        "review_url": issue.review_url,
        "review_number": issue.review_number,
        "review_head": issue.review_head,
    }
    if parent is not None or parent_error is not None:
        value["parent_identifier"] = (
            str(getattr(parent, "identifier", "") or "").strip() or None
        )
        value["parent_status"] = (
            canonicalize_status(parent.state) if parent is not None else None
        )
        value["parent_issue_type"] = (
            str(getattr(parent, "issue_type", "") or "").strip() or None
        )
        value["parent_error"] = str(parent_error or "").strip() or None
    return value


class WorkflowFactCollector:
    """Collect one complete project-scoped snapshot without false empties."""

    _EXTERNAL_DOMAINS = (
        FactDomain.TERMINAL_AUDIT,
        FactDomain.REVIEW_CI,
        FactDomain.IMPLEMENTATION_AUTHORITY,
        FactDomain.DUPLICATE_INVESTIGATION,
        FactDomain.RETRY_BUDGET,
        FactDomain.CONFIG,
    )

    def __init__(
        self,
        *,
        project_id: str,
        tracker: TrackerProtocol,
        sources: Mapping[FactDomain | str, FactSource] | None = None,
        containment_source: FactSource | None = None,
        landing_collector: GitLandingCollector | None = None,
        integration_queue: IntegrationQueueProtocol | None = None,
        clock: Callable[[], datetime] | None = None,
        cooperative_checkpoint: Callable[[], None] | None = None,
    ) -> None:
        self.project_id = _required_text(project_id, "project_id")
        self.tracker = tracker
        self.sources = {
            FactDomain(domain): source for domain, source in (sources or {}).items()
        }
        forbidden = set(self.sources) & {
            FactDomain.TASK,
            FactDomain.DEPENDENCIES,
            FactDomain.CONTAINMENT,
            FactDomain.INTEGRATION,
            FactDomain.LANDING,
        }
        if forbidden:
            raise ValueError(
                f"built-in fact domains cannot be overridden: {sorted(item.value for item in forbidden)!r}"
            )
        # Epic workflows need richer, graph-wide containment facts than the
        # generic direct-child projection provides.  Keep that provider
        # explicit and scoped to containment so all other domains still share
        # the same normalization and error boundary.
        self.containment_source = containment_source
        self.landing_collector = landing_collector
        if (
            landing_collector is not None
            and landing_collector.project_id != self.project_id
        ):
            raise ValueError("landing collector project does not match fact collector")
        self.integration_queue = integration_queue
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.cooperative_checkpoint = cooperative_checkpoint

    def _now(self) -> tuple[datetime, str]:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("workflow fact collector clock must be timezone-aware")
        return now.astimezone(timezone.utc), _render_time(now)

    def _source_observation(
        self,
        domain: FactDomain,
        issue: Issue,
        *,
        now: datetime,
        now_iso: str,
    ) -> FactObservation:
        source = (
            self.containment_source
            if domain is FactDomain.CONTAINMENT and self.containment_source is not None
            else self.sources.get(domain)
        )
        if source is None:
            return FactObservation.missing(
                domain, observed_at=now_iso, source=f"{domain.value}:unconfigured"
            )
        try:
            raw = source(issue)
        except Exception as exc:  # noqa: BLE001 - evidence boundary
            return FactObservation.error(
                domain,
                observed_at=now_iso,
                source=f"{domain.value}:collector",
                error_code=f"{domain.value}_{type(exc).__name__.lower()}",
            )
        if isinstance(raw, FactObservation):
            if raw.domain is not domain:
                return FactObservation.error(
                    domain,
                    observed_at=now_iso,
                    source=f"{domain.value}:collector",
                    error_code="collector_domain_mismatch",
                )
            return raw
        if raw is None:
            return FactObservation.missing(
                domain, observed_at=now_iso, source=f"{domain.value}:collector"
            )
        try:
            if isinstance(raw, CollectedValue):
                observed = _parse_time(raw.observed_at, "observed_at")
                stale = (
                    raw.stale_after_seconds is not None
                    and (now - observed).total_seconds() > raw.stale_after_seconds
                )
                constructor = (
                    FactObservation.stale if stale else FactObservation.known
                )
                return constructor(
                    domain,
                    raw.value,
                    observed_at=raw.observed_at,
                    source=raw.source,
                )
            return FactObservation.known(
                domain,
                raw,
                observed_at=now_iso,
                source=f"{domain.value}:collector",
            )
        except Exception as exc:  # noqa: BLE001 - evidence normalization boundary
            return FactObservation.error(
                domain,
                observed_at=now_iso,
                source=f"{domain.value}:collector",
                error_code=f"{domain.value}_value_{type(exc).__name__.lower()}",
            )

    def _all_error(
        self,
        task_id: str,
        *,
        now_iso: str,
        error_code: str,
    ) -> WorkflowFacts:
        observations = {
            domain: FactObservation.error(
                domain,
                observed_at=now_iso,
                source="tracker",
                error_code=error_code,
            )
            for domain in REQUIRED_FACT_DOMAINS
        }
        return WorkflowFacts(
            self.project_id,
            task_id,
            now_iso,
            observations,
        )

    def _dependency_observation(
        self,
        issue: Issue,
        *,
        now_iso: str,
        authoritative_issues: Mapping[str, Issue] | None,
    ) -> FactObservation:
        """Resolve dependency state without inventing a Backlog default.

        Production full scans pass the already generation-bound project
        corpus.  Direct native detail reads carry statuses materialized under
        the tracker's repository lock.  In either case, an absent, malformed,
        or cross-project target is unavailable authority and fails closed.
        """

        error_codes: set[str] = set()

        def values(blockers: Sequence[BlockerRef]) -> list[dict[str, Any]]:
            resolved: list[dict[str, Any]] = []
            for blocker in blockers:
                identifier = str(
                    blocker.identifier or blocker.id or ""
                ).strip()
                if not identifier:
                    error_codes.add("dependency_reference_invalid")
                    continue
                status = blocker.state
                if authoritative_issues is not None:
                    # Runtime corpus indexes use the same case-insensitive ID
                    # semantics as the native tracker.  Retain a canonical-key
                    # fallback while accepting exact-key plain mappings in
                    # direct tests and adapter integrations.
                    target = authoritative_issues.get(identifier)
                    if target is None:
                        target = authoritative_issues.get(identifier.casefold())
                    if target is None:
                        # A supplied corpus is the sole authority for this
                        # observation.  Embedded ref state may be stale or may
                        # describe a foreign row filtered out by project scope.
                        error_codes.add("dependency_state_unavailable")
                        continue
                    target_project = str(target.project_id or "").strip()
                    if target_project and target_project != self.project_id:
                        error_codes.add("dependency_project_scope_mismatch")
                        continue
                    status = target.state
                if not str(status or "").strip():
                    error_codes.add("dependency_state_unavailable")
                    continue
                resolved.append(
                    {
                        "id": _optional_text(blocker.id),
                        "identifier": _optional_text(blocker.identifier),
                        "status": canonicalize_status(status),
                    }
                )
            return sorted(
                resolved,
                key=lambda item: item["identifier"] or item["id"] or "",
            )

        value = {
            "finish": values(issue.blocked_by),
            "hard_start": values(issue.start_blocked_by),
        }
        if error_codes:
            return FactObservation.error(
                FactDomain.DEPENDENCIES,
                observed_at=now_iso,
                source="tracker",
                error_code=sorted(error_codes)[0],
            )
        return FactObservation.known(
            FactDomain.DEPENDENCIES,
            value,
            observed_at=now_iso,
            source="tracker",
        )

    def _overlay_integration_queue(
        self,
        tracker_value: dict[str, Any] | None,
        issue: Issue,
        now_iso: str,
    ) -> dict[str, Any] | None:
        """Overlay exact-head durable queue state onto tracker integration."""

        if self.integration_queue is None:
            return tracker_value
        try:
            queue_row = self.integration_queue.get(self.project_id, issue.identifier)
        except Exception:  # noqa: BLE001 - queue evidence boundary
            return tracker_value
        if queue_row is None:
            return tracker_value

        tracker_head = None
        if isinstance(tracker_value, dict):
            tracker_head = tracker_value.get("head_sha")
        issue_head = getattr(issue, "head_sha", None)
        queue_head = getattr(queue_row, "head_sha", None)
        authoritative_head = tracker_head or issue_head
        if authoritative_head and queue_head and str(queue_head) != str(authoritative_head):
            return tracker_value
        if authoritative_head and not queue_head:
            return tracker_value

        base: dict[str, Any] = dict(tracker_value) if tracker_value is not None else {}
        queue_state = str(getattr(queue_row, "state", None) or "").strip()
        retry_forced = bool(getattr(queue_row, "retry_forced", False))
        prior_tracker_state = None
        if isinstance(tracker_value, dict):
            prior = tracker_value.get("state")
            prior_tracker_state = str(prior).strip() if prior else None

        lease_expires_at_raw = getattr(queue_row, "lease_expires_at", None)
        lease_owner_raw = getattr(queue_row, "lease_owner", None)
        lease_expires_dt: datetime | None = None
        if lease_expires_at_raw is not None:
            try:
                lease_expires_dt = datetime.fromtimestamp(
                    float(lease_expires_at_raw), tz=timezone.utc
                )
            except (TypeError, ValueError, OSError, OverflowError):
                lease_expires_dt = None

        if queue_state in ("integrating", "blocked"):
            base["state"] = queue_state
        if queue_state == "integrating":
            if lease_expires_dt is not None:
                base["lease_expires_at"] = _render_time(lease_expires_dt)
            if lease_owner_raw:
                base["lease_owner"] = str(lease_owner_raw)
            live_lease_valid = (
                lease_expires_dt is not None
                and lease_expires_dt > self._clock()
                and bool(lease_owner_raw)
            )
            if live_lease_valid and prior_tracker_state in {
                "ready",
                "queued",
                None,
                "",
            }:
                base["live_claim_precedes_history"] = True
        if queue_state == "blocked":
            last_error = getattr(queue_row, "last_error", None)
            if last_error:
                base["last_error"] = str(last_error)
            if retry_forced:
                base["retry_forced"] = True
        if retry_forced and "retry_forced" not in base:
            base["retry_forced"] = True
        # A ready child can be unclaimable when a dependency commit is absent
        # from its immediate epic target.  The old sweep detected that graph
        # condition and repaired it, but the durable evaluator previously had
        # no production fact capable of selecting its reconciliation action.
        # Derive the bounded exact-revision fact from accepted dependency
        # heads and the same Git landing collector used by integration.
        dependency_heads = base.get("dependency_heads")
        target = str(
            getattr(queue_row, "base_branch", None)
            or base.get("base_branch")
            or getattr(issue, "target_branch", None)
            or ""
        ).strip()
        if (
            queue_state == "ready"
            and isinstance(dependency_heads, Mapping)
            and dependency_heads
            and target
            and self.landing_collector is not None
        ):
            requests: list[LandingRequest] = []
            dependency_ids: list[str] = []
            for dependency_id, revision in sorted(dependency_heads.items()):
                identifier = str(dependency_id or "").strip()
                head = str(revision or "").strip().lower()
                if not identifier or not _GIT_REVISION_RE.fullmatch(head):
                    continue
                try:
                    requests.append(LandingRequest(identifier, target, head))
                except ValueError:
                    continue
                dependency_ids.append(identifier)
            if requests:
                landings = self.landing_collector.collect_many(requests)
                missing = [
                    dependency_id
                    for dependency_id, landing in zip(
                        dependency_ids, landings, strict=True
                    )
                    # Dependency readiness is an ancestry requirement: patch
                    # equivalence can prove that a change landed, but it does
                    # not make the accepted dependency commit reachable from
                    # the child's target branch.  UNKNOWN observations do not
                    # prove that the commit is absent and must not authorize a
                    # target repair; a later evidence refresh can classify
                    # them without mutating Git from a transport/object error.
                    if landing.state is LandingState.NOT_LANDED
                    or (
                        landing.state is LandingState.LANDED
                        and str(landing.proof.get("kind") or "")
                        != LandingProofKind.GIT_ANCESTRY.value
                    )
                ]
                if missing:
                    base["required_base_missing"] = missing
        return base

    def collect(
        self,
        task_id: str,
        *,
        landing_requests: Sequence[LandingRequest] = (),
        authoritative_issues: Mapping[str, Issue] | None = None,
        authoritative_children: Mapping[str, Sequence[Issue]] | None = None,
    ) -> WorkflowFacts:
        if self.cooperative_checkpoint is not None:
            self.cooperative_checkpoint()
        task_id = _required_text(task_id, "task_id")
        now, now_iso = self._now()
        if authoritative_issues is not None:
            issue = authoritative_issues.get(task_id)
            if issue is None:
                issue = authoritative_issues.get(task_id.casefold())
        else:
            try:
                issue = self.tracker.fetch_issue_detail(task_id)
            except Exception as exc:  # noqa: BLE001 - tracker evidence boundary
                return self._all_error(
                    task_id,
                    now_iso=now_iso,
                    error_code=f"tracker_{type(exc).__name__.lower()}",
                )
        if issue is None:
            observations = {
                domain: FactObservation.missing(
                    domain, observed_at=now_iso, source="tracker"
                )
                for domain in REQUIRED_FACT_DOMAINS
            }
            return WorkflowFacts(self.project_id, task_id, now_iso, observations)
        if issue.project_id and str(issue.project_id) != self.project_id:
            return self._all_error(
                task_id,
                now_iso=now_iso,
                error_code="project_scope_mismatch",
            )
        if not issue.project_id:
            # Native Markdown trackers are already project-bound and omit this
            # redundant field.  Normalize before hashing facts so controller,
            # handler revalidation, and transition CAS all observe one exact
            # authority generation.
            issue.project_id = self.project_id

        try:
            dependency_observation = self._dependency_observation(
                issue,
                now_iso=now_iso,
                authoritative_issues=authoritative_issues,
            )
        except Exception as exc:  # noqa: BLE001 - dependency authority boundary
            dependency_observation = FactObservation.error(
                FactDomain.DEPENDENCIES,
                observed_at=now_iso,
                source="tracker",
                error_code=f"dependency_{type(exc).__name__.lower()}",
            )

        parent = None
        parent_error = None
        parent_id = str(issue.parent_id or "").strip()
        needs_parent_terminal_authority = bool(
            parent_id
            and canonicalize_status(issue.state) == DONE
            and str(issue.issue_type or "task").strip().lower() != "epic"
        )
        if needs_parent_terminal_authority:
            try:
                if authoritative_issues is not None:
                    parent = authoritative_issues.get(
                        parent_id
                    ) or authoritative_issues.get(parent_id.casefold())
                else:
                    parent = self.tracker.fetch_issue_detail(parent_id)
            except Exception as exc:  # noqa: BLE001 - parent authority boundary
                parent_error = f"parent_{type(exc).__name__.lower()}"
            else:
                parent_identity = str(
                    getattr(parent, "identifier", "")
                    or getattr(parent, "id", "")
                    or ""
                ).strip()
                parent_project = str(
                    getattr(parent, "project_id", "") or ""
                ).strip()
                if parent is None:
                    parent_error = "parent_missing"
                elif parent_identity != parent_id:
                    parent = None
                    parent_error = "parent_identity_mismatch"
                elif parent_project and parent_project != self.project_id:
                    parent = None
                    parent_error = "parent_project_mismatch"

        observations: dict[FactDomain, FactObservation] = {
            FactDomain.TASK: FactObservation.known(
                FactDomain.TASK,
                _task_value(
                    issue,
                    parent=parent,
                    parent_error=parent_error,
                ),
                observed_at=now_iso,
                source="tracker",
            ),
            FactDomain.DEPENDENCIES: dependency_observation,
        }
        if self.containment_source is not None:
            observations[FactDomain.CONTAINMENT] = self._source_observation(
                FactDomain.CONTAINMENT,
                issue,
                now=now,
                now_iso=now_iso,
            )
        else:
            try:
                children = (
                    list(
                        authoritative_children.get(
                            issue.identifier.casefold(), ()
                        )
                    )
                    if authoritative_children is not None
                    else list(
                        {
                            child.identifier: child
                            for child in authoritative_issues.values()
                            if child.parent_id == issue.identifier
                        }.values()
                    )
                    if authoritative_issues is not None
                    else self.tracker.fetch_children(issue.identifier)
                )
            except Exception as exc:  # noqa: BLE001 - tracker evidence boundary
                observations[FactDomain.CONTAINMENT] = FactObservation.error(
                    FactDomain.CONTAINMENT,
                    observed_at=now_iso,
                    source="tracker",
                    error_code=f"children_{type(exc).__name__.lower()}",
                )
            else:
                observations[FactDomain.CONTAINMENT] = FactObservation.known(
                    FactDomain.CONTAINMENT,
                    {
                        "parent_id": issue.parent_id,
                        "children": sorted(
                            [
                                {
                                    "identifier": child.identifier,
                                    "status": canonicalize_status(child.state),
                                    "issue_type": child.issue_type,
                                }
                                for child in children
                                if not child.project_id
                                or str(child.project_id) == self.project_id
                            ],
                            key=lambda item: item["identifier"],
                        ),
                    },
                    observed_at=now_iso,
                    source="tracker",
                )
        integration = _integration_value(issue)
        integration = self._overlay_integration_queue(
            integration, issue, now_iso
        )
        observations[FactDomain.INTEGRATION] = (
            FactObservation.known(
                FactDomain.INTEGRATION,
                integration,
                observed_at=now_iso,
                source="tracker",
            )
            if integration is not None
            else FactObservation.missing(
                FactDomain.INTEGRATION, observed_at=now_iso, source="tracker"
            )
        )
        for domain in self._EXTERNAL_DOMAINS:
            observations[domain] = self._source_observation(
                domain, issue, now=now, now_iso=now_iso
            )

        owner_landings = _owner_delivery_landings(
            observations[FactDomain.TERMINAL_AUDIT],
            landing_requests,
            project_id=self.project_id,
            task_id=task_id,
            observed_at=now_iso,
        )
        owner_identities = {
            (item.source, item.target, item.revision) for item in owner_landings
        }
        unresolved_requests = tuple(
            request
            for request in landing_requests
            if (request.source, request.target, request.revision)
            not in owner_identities
        )
        landings: tuple[LandingFact, ...] = owner_landings
        if unresolved_requests and self.landing_collector is None:
            observations[FactDomain.LANDING] = FactObservation.error(
                FactDomain.LANDING,
                observed_at=now_iso,
                source="git",
                error_code="landing_collector_unavailable",
            )
        elif landing_requests:
            try:
                collect_many = getattr(self.landing_collector, "collect_many", None)
                collected = (
                    tuple(collect_many(unresolved_requests))
                    if unresolved_requests and callable(collect_many)
                    else tuple(
                        self.landing_collector.collect(request)
                        for request in unresolved_requests
                    )
                )
            except Exception as exc:  # noqa: BLE001 - landing evidence boundary
                observations[FactDomain.LANDING] = FactObservation.error(
                    FactDomain.LANDING,
                    observed_at=now_iso,
                    source="git",
                    error_code=f"landing_{type(exc).__name__.lower()}",
                )
            else:
                landings = (*owner_landings, *collected)
                observations[FactDomain.LANDING] = FactObservation.known(
                    FactDomain.LANDING,
                    {
                        "evidence_revisions": [
                            item.evidence_revision
                            for item in sorted(
                                landings,
                                key=lambda item: (
                                    item.source,
                                    item.target,
                                    item.revision or "",
                                ),
                            )
                        ]
                    },
                    observed_at=now_iso,
                    source="git",
                )
        else:
            observations[FactDomain.LANDING] = FactObservation.missing(
                FactDomain.LANDING, observed_at=now_iso, source="git"
            )

        return WorkflowFacts(
            self.project_id,
            task_id,
            now_iso,
            observations,
            landings=landings,
        )
